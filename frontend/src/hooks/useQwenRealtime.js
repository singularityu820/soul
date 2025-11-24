import { useState, useRef, useCallback, useEffect } from 'react';

// Qwen Omni Realtime hook (minimal integration)
// Model: qwen-omni-turbo-realtime (text+audio) using server VAD
// Input: PCM16 16k mono, Output: PCM24 24k mono (streamed as base64)

const REALTIME_BASE = 'wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=qwen-omni-turbo-realtime';
const API_KEY = import.meta.env.VITE_DASHSCOPE_API_KEY || window.DASHSCOPE_API_KEY;
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

function decodePCM24MonoToFloat32(base64) {
  // PCM_24000HZ_MONO_24BIT little-endian
  try {
    const raw = atob(base64);
    const byteArray = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) byteArray[i] = raw.charCodeAt(i);
    const sampleCount = Math.floor(byteArray.length / 3);
    const out = new Float32Array(sampleCount);
    for (let i = 0; i < sampleCount; i++) {
      const i3 = i * 3;
      // 24-bit signed little endian
      let val = (byteArray[i3]) | (byteArray[i3 + 1] << 8) | (byteArray[i3 + 2] << 16);
      if (val & 0x800000) val |= 0xFF000000; // sign extend
      out[i] = val / 8388608; // 2^23
    }
    return out;
  } catch (e) {
    console.warn('Failed to decode PCM24 chunk', e);
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

  const wsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const micStreamRef = useRef(null);
  const workletNodeRef = useRef(null);
  const recordingRef = useRef(false);
  const playQueueRef = useRef([]);
  const playingSourceRef = useRef(null);
  const sessionConfiguredRef = useRef(false);

  const flushPlayQueue = useCallback(() => {
    if (isAudioPlaying) return;
    const next = playQueueRef.current.shift();
    setAudioQueueLength(playQueueRef.current.length);
    if (!next) return;
    setIsAudioPlaying(true);
    setCurrentAudio({ segment_id: next.segment_id });
    // Convert Float32Array to AudioBuffer
    if (!audioCtxRef.current) audioCtxRef.current = new AudioContext({ sampleRate: 24000 });
    const ctx = audioCtxRef.current;
    const buffer = ctx.createBuffer(1, next.data.length, 24000);
    buffer.getChannelData(0).set(next.data);
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(ctx.destination);
    src.onended = () => {
      setIsAudioPlaying(false);
      setCurrentAudio(null);
      flushPlayQueue();
    };
    playingSourceRef.current = src;
    src.start();
  }, [isAudioPlaying]);

  useEffect(() => { if (!isAudioPlaying) flushPlayQueue(); }, [isAudioPlaying, flushPlayQueue]);

  const connect = useCallback(async () => {
    try {
      setError(null);
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;
      const ws = new WebSocket(REALTIME_BASE);
      wsRef.current = ws;

      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => { reject(new Error('连接超时')); }, 10000);
        ws.onopen = () => {
          setIsConnected(true);
          clearTimeout(timer);
          // Send session.update to configure modalities
          const sessionUpdate = {
            event_id: 'evt_' + Date.now(),
            type: 'session.update',
            session: {
              modalities: ['text','audio'],
              voice: VOICE,
              input_audio_format: 'pcm16',
              output_audio_format: 'pcm24',
              instructions: '你是一个友好、简洁、专业的中文语音助手。',
              turn_detection: { type: 'server_vad', threshold: 0.5, silence_duration_ms: 800 }
            }
          };
          ws.send(JSON.stringify(sessionUpdate));
          sessionConfiguredRef.current = true;
          resolve();
        };
        ws.onerror = (e) => {
          clearTimeout(timer);
          reject(new Error('WebSocket错误'));
        };
        ws.onclose = () => {
          clearTimeout(timer);
          setIsConnected(false);
          setStatus('idle');
        };
      });

      ws.onmessage = (evt) => {
        let data;
        try { data = JSON.parse(evt.data); } catch { return; }
        // Handle response events
        switch (data.type) {
          case 'response.audio_transcript.delta':
          case 'response.text.delta':
            setResponse(prev => prev + (data.delta || ''));
            break;
          case 'response.audio_transcript.done':
          case 'response.text.done':
            // final text
            break;
          case 'response.audio.delta': {
            // streaming audio chunk (base64)
            if (data.audio) {
              const floatChunk = decodePCM24MonoToFloat32(data.audio);
              if (floatChunk) {
                playQueueRef.current.push({ segment_id: data.output_item_id || Date.now(), data: floatChunk });
                setAudioQueueLength(playQueueRef.current.length);
                flushPlayQueue();
              }
            }
            break; }
          case 'response.audio.done':
            break;
          case 'conversation.item.created':
            // user item created after VAD commit; could extract transcript
            if (data.item && data.item.content) {
              const textParts = data.item.content.filter(p => p.type === 'input_text');
              if (textParts.length) setTranscript(textParts.map(p => p.text).join('\n'));
            }
            break;
          case 'input_audio_buffer.speech_started':
            setStatus('transcribing');
            break;
          case 'input_audio_buffer.speech_stopped':
            setStatus('generating');
            break;
          case 'response.done':
            setStatus('idle');
            break;
          default:
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
    const evt = {
      event_id: 'aud_' + Date.now(),
      type: 'input_audio_buffer.append',
      audio: b64,
    };
    wsRef.current.send(JSON.stringify(evt));
  }, []);

  const startRecording = useCallback(async () => {
    if (!isConnected || recordingRef.current) return;
    try {
      setError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = stream;
      if (!audioCtxRef.current) audioCtxRef.current = new AudioContext();
      const ctx = audioCtxRef.current;
      const source = ctx.createMediaStreamSource(stream);
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0);
        const b64 = pcm16ToBase64(input, ctx.sampleRate);
        sendAudioBase64(b64);
      };
      source.connect(processor);
      processor.connect(ctx.destination);
      workletNodeRef.current = processor;
      recordingRef.current = true;
      setIsRecording(true);
    } catch (e) {
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
    setIsConnected(false);
    setStatus('idle');
  }, [stopRecording]);

  const interrupt = useCallback(() => {
    // For server_vad mode we can optionally flush; no explicit interrupt event defined
    // Could send a session.update to force commit if needed
    setResponse('');
    playQueueRef.current = [];
    setAudioQueueLength(0);
    if (playingSourceRef.current) { try { playingSourceRef.current.stop(); } catch {} }
    setIsAudioPlaying(false);
  }, []);

  // Auto flush audio queue
  useEffect(() => { if (!isAudioPlaying) flushPlayQueue(); }, [isAudioPlaying, flushPlayQueue]);

  return {
    isConnected,
    isRecording,
    status,
    transcript,
    response,
    error,
    audioQueueLength,
    isAudioPlaying,
    currentAudio,
    connect,
    disconnect,
    startRecording,
    stopRecording,
    interrupt,
  };
}
