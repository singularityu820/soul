import { useState, useRef, useCallback, useEffect } from 'react';

// Qwen Omni Realtime hook - 通过后端 WebSocket 代理连接
// 后端处理 DashScope API 认证和会话管理
// Input: PCM16 16k mono, Output: PCM24 24k mono (streamed as base64)

// 使用后端的 WebSocket 端点而不是直接连接 DashScope
const getRealtimeWsUrl = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.hostname;
  const port = import.meta.env.DEV ? '8000' : window.location.port;
  return `${protocol}//${host}:${port}/ws/voice-stream`;
};

const REALTIME_BASE = getRealtimeWsUrl();
const VOICE = 'Chelsie'; // can be Cherry/Ethan/Serena/Chelsie etc.

function pcm16ToBase64(float32, audioCtxSampleRate) {
  // Resample if needed (simplistic linear down/up sampling to 16k)
  const targetRate = 16000;
  const ratio = audioCtxSampleRate / targetRate;
  let samples;
  if (Math.abs(ratio - 1) < 1e-3) {
    samples = float32;
  } else {
    const newLen = Math.floor(float32.length / ratio);
    samples = new Float32Array(newLen);
    for (let i = 0; i < newLen; i++) {
      samples[i] = float32[Math.floor(i * ratio)];
    }
  }
  const pcm = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    let s = samples[i];
    if (s > 1) s = 1; else if (s < -1) s = -1;
    pcm[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  // Convert to binary string then base64
  let binary = '';
  const bytes = new Uint8Array(pcm.buffer);
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function decodePCM16MonoToFloat32(base64) {
  // PCM_24000HZ_MONO_16BIT little-endian (Qwen Omni 输出格式)
  try {
    const raw = atob(base64);
    const byteArray = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) byteArray[i] = raw.charCodeAt(i);
    const sampleCount = Math.floor(byteArray.length / 2); // 16-bit = 2 bytes per sample
    const out = new Float32Array(sampleCount);
    for (let i = 0; i < sampleCount; i++) {
      const i2 = i * 2;
      // 16-bit signed little endian
      let val = byteArray[i2] | (byteArray[i2 + 1] << 8);
      if (val & 0x8000) val |= 0xFFFF0000; // sign extend
      out[i] = val / 32768; // 2^15
    }
    return out;
  } catch (e) {
    console.warn('Failed to decode PCM16 chunk', e);
    return null;
  }
}

export function useQwenRealtime() {
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [status, setStatus] = useState('idle');
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState('');
  const [error, setError] = useState(null);
  const [isAudioPlaying, setIsAudioPlaying] = useState(false);
  const [audioQueueLength, setAudioQueueLength] = useState(0);
  const [currentAudio, setCurrentAudio] = useState(null);
  const [isResponseComplete, setIsResponseComplete] = useState(false);

  const wsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const micStreamRef = useRef(null);
  const workletNodeRef = useRef(null);
  const recordingRef = useRef(false);
  const isConnectedRef = useRef(false); // 同步状态标志，避免闭包陷阱
  const playQueueRef = useRef([]);
  const playingSourceRef = useRef(null);
  const sessionConfiguredRef = useRef(false);
  const isPlayingRef = useRef(false); // 同步状态标志，避免竞态

  const flushPlayQueue = useCallback(() => {
    // 使用 ref 进行同步检查，避免状态更新延迟导致的重复播放
    if (isPlayingRef.current) {
      console.log('[Qwen Omni] Already playing, skipping');
      return;
    }
    if (playQueueRef.current.length === 0) return;
    
    // 立即标记为播放中（同步）
    isPlayingRef.current = true;
    setIsAudioPlaying(true);
    setIsResponseComplete(false); // 开始播放时重置
    
    // 合并所有队列中的音频块为连续流
    const allChunks = playQueueRef.current.splice(0); // 清空队列
    const totalLength = allChunks.reduce((sum, chunk) => sum + chunk.data.length, 0);
    
    console.log('[Qwen Omni] Playing', allChunks.length, 'chunks,', totalLength, 'samples total');
    
    // 创建连续的音频缓冲区
    if (!audioCtxRef.current) audioCtxRef.current = new AudioContext({ sampleRate: 24000 });
    const ctx = audioCtxRef.current;
    const buffer = ctx.createBuffer(1, totalLength, 24000);
    const channelData = buffer.getChannelData(0);
    
    // 将所有块拼接到一起
    let offset = 0;
    for (const chunk of allChunks) {
      channelData.set(chunk.data, offset);
      offset += chunk.data.length;
    }
    
    setAudioQueueLength(0);
    setCurrentAudio({ segment_id: allChunks[0]?.segment_id });
    
    // 播放合并后的音频
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(ctx.destination);
    src.onended = () => {
      console.log('[Qwen Omni] Playback finished');
      isPlayingRef.current = false; // 立即标记为结束（同步）
      setIsAudioPlaying(false);
      setCurrentAudio(null);
      // 检查是否有新的音频块到达
      setTimeout(() => flushPlayQueue(), 0);
    };
    playingSourceRef.current = src;
    src.start();
  }, [isAudioPlaying]);

  // 定时检查音频队列，如果累积了足够的数据就开始播放
  useEffect(() => {
    const interval = setInterval(() => {
      // 使用 ref 进行同步检查
      if (!isPlayingRef.current && playQueueRef.current.length >= 5) {
        console.log('[Qwen Omni] Auto-playing queued audio (', playQueueRef.current.length, 'chunks)');
        flushPlayQueue();
      }
    }, 500);
    return () => clearInterval(interval);
  }, [flushPlayQueue]);

  const connect = useCallback(async () => {
    try {
      setError(null);
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;
      const ws = new WebSocket(REALTIME_BASE);
      wsRef.current = ws;

      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => { reject(new Error('连接超时')); }, 10000);
        ws.onopen = () => {
          console.log('[Qwen Omni] WebSocket connected to backend');
          isConnectedRef.current = true;
          setIsConnected(true);
          clearTimeout(timer);
          sessionConfiguredRef.current = true;
          resolve();
          // 后端已经配置好 Qwen Omni session，无需客户端发送 session.update
          // 等待后端发送 ready 消息
        };
        ws.onerror = (e) => {
          console.error('[Qwen Omni] WebSocket error:', e);
          clearTimeout(timer);
          reject(new Error('WebSocket错误'));
        };
        ws.onclose = (e) => {
          console.log('[Qwen Omni] WebSocket closed:', e.code, e.reason);
          clearTimeout(timer);
          isConnectedRef.current = false;
          setIsConnected(false);
          setStatus('idle');
        };
      });

      ws.onmessage = (evt) => {
        let data;
        try { data = JSON.parse(evt.data); } catch { return; }
        
        // 处理后端转发的 Qwen Omni 事件
        switch (data.type) {
          case 'ready':
            // 后端会话已就绪
            console.log('[Qwen Omni] Session ready:', data.session_id);
            break;
            
          case 'transcript':
            // 用户语音转录
            if (data.text) {
              if (data.is_final) {
                setTranscript(data.text);
              } else {
                // 增量转录
                setResponse(prev => prev + data.text);
              }
            }
            break;
            
          case 'audio':
            // AI 生成的音频（Base64 PCM16 24kHz）
            if (data.audio) {
              const floatChunk = decodePCM16MonoToFloat32(data.audio);
              if (floatChunk && floatChunk.length > 0) {
                console.log('[Qwen Omni] Received audio chunk:', floatChunk.length, 'samples');
                playQueueRef.current.push({ 
                  segment_id: data.segment_id || Date.now(), 
                  data: floatChunk 
                });
                setAudioQueueLength(playQueueRef.current.length);
                // 不立即播放，等待更多块累积（或 speech_stopped 事件）
              } else {
                console.warn('[Qwen Omni] Invalid audio chunk');
              }
            }
            break;
            
          case 'speech_started':
            setStatus('transcribing');
            break;
            
          case 'speech_stopped':
            setStatus('generating');
            // AI 开始生成回复，等待音频块累积
            break;
            
          case 'response_done':
            // 响应完成，开始播放累积的音频
            console.log('[Qwen Omni] Response done, queue length:', playQueueRef.current.length);
            setStatus('idle');
            setIsResponseComplete(true);
            // 使用 ref 进行同步检查
            if (!isPlayingRef.current && playQueueRef.current.length > 0) {
              console.log('[Qwen Omni] Starting playback after response done');
              flushPlayQueue();
            }
            break;
            
          case 'error':
            console.error('[Qwen Omni] Error:', data.message);
            setError(data.message);
            setStatus('idle');
            break;
            
          default:
            // 兼容旧的 DashScope 直连事件格式（如果有）
            if (data.type?.startsWith('response.')) {
              console.log('[Qwen Omni] Backend event:', data.type);
            }
            break;
        }
      };

    } catch (e) {
      setError(e.message);
      throw e;
    }
  }, [flushPlayQueue]);

  const sendAudioBase64 = useCallback((b64) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN || !sessionConfiguredRef.current) return;
    // 后端期望二进制音频数据，而不是 JSON 包装的事件
    // 将 Base64 转换回二进制并发送
    try {
      const binaryString = atob(b64);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      // 直接发送 ArrayBuffer
      wsRef.current.send(bytes);
    } catch (e) {
      console.error('[Qwen Omni] Failed to send audio:', e);
    }
  }, []);

  const startRecording = useCallback(async () => {
    if (!isConnected || recordingRef.current) {
      console.warn('[Qwen Omni] Cannot start recording:', { isConnected, isRecording: recordingRef.current });
      return;
    }
    try {
      console.log('[Qwen Omni] Starting recording...');
      setError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = stream;
      // 不指定采样率，使用设备默认值（通常 48kHz）
      // pcm16ToBase64 会负责重采样到 16kHz
      if (!audioCtxRef.current) audioCtxRef.current = new AudioContext();
      const ctx = audioCtxRef.current;
      console.log('[Qwen Omni] Recording AudioContext sample rate:', ctx.sampleRate);
      const source = ctx.createMediaStreamSource(stream);
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      let chunkCount = 0;
      processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0);
        const b64 = pcm16ToBase64(input, ctx.sampleRate);
        sendAudioBase64(b64);
        if (++chunkCount % 50 === 0) {
          console.log('[Qwen Omni] Sent', chunkCount, 'audio chunks');
        }
      };
      source.connect(processor);
      processor.connect(ctx.destination);
      workletNodeRef.current = processor;
      recordingRef.current = true;
      setIsRecording(true);
      console.log('[Qwen Omni] Recording started successfully');
    } catch (e) {
      console.error('[Qwen Omni] Failed to start recording:', e);
      setError(e.message || '无法访问麦克风');
    }
  }, [isConnected, sendAudioBase64]);

  const stopRecording = useCallback(() => {
    if (!recordingRef.current) return;
    recordingRef.current = false;
    setIsRecording(false);
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach(t => t.stop());
      micStreamRef.current = null;
    }
    if (workletNodeRef.current) {
      try { workletNodeRef.current.disconnect(); } catch {}
      workletNodeRef.current = null;
    }
  }, []);

  const disconnect = useCallback(() => {
    stopRecording();
    if (wsRef.current) {
      try { wsRef.current.close(); } catch {}
      wsRef.current = null;
    }
    isConnectedRef.current = false;
    setIsConnected(false);
    setStatus('idle');
    setIsResponseComplete(false);
    isPlayingRef.current = false; // 同步重置
    // 清空音频队列
    playQueueRef.current = [];
    setAudioQueueLength(0);
  }, [stopRecording]);

  const interrupt = useCallback(() => {
    // For server_vad mode we can optionally flush; no explicit interrupt event defined
    // Could send a session.update to force commit if needed
    setResponse('');
    playQueueRef.current = [];
    setAudioQueueLength(0);
    if (playingSourceRef.current) { try { playingSourceRef.current.stop(); } catch {} }
    isPlayingRef.current = false; // 同步重置
    setIsAudioPlaying(false);
  }, []);

  // Auto flush audio queue
  useEffect(() => { if (!isAudioPlaying) flushPlayQueue(); }, [isAudioPlaying, flushPlayQueue]);

  return {
    isConnected,
    isConnectedRef, // 导出 ref 供外部同步读取
    isRecording,
    recordingRef, // 导出 ref 供外部同步读取
    status,
    transcript,
    response,
    error,
    audioQueueLength,
    isAudioPlaying,
    currentAudio,
    isResponseComplete,
    connect,
    disconnect,
    startRecording,
    stopRecording,
    interrupt,
  };
}
