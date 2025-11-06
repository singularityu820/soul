import { useState, useRef, useCallback, useEffect } from "react";

/**
 * 实时语音流 Hook
 * 
 * 使用 WebSocket 实现低延迟的语音对话:
 * - 实时音频采集和发送
 * - 实时接收 ASR 转录
 * - 实时接收 LLM 响应
 * - 实时播放 TTS 音频
 */
export function useVoiceStream() {
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [status, setStatus] = useState("idle"); // idle | transcribing | generating | synthesizing
  const [transcript, setTranscript] = useState("");
  const [response, setResponse] = useState("");
  const [error, setError] = useState(null);

  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const streamRef = useRef(null);
  const workletNodeRef = useRef(null);
  const sessionIdRef = useRef(null);
  const cleanupInitializedRef = useRef(false); // 防止 StrictMode 清理

  /**
   * 连接到 WebSocket 服务器
   */
  const connect = useCallback(async (threadId = null) => {
    try {
      setError(null);
      
      // 如果已经有活动连接，先关闭
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        console.log('WebSocket already connected, reusing existing connection');
        return;
      }

      // 创建 WebSocket 连接
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.hostname;
      const port = 8000; // 后端端口
      const wsUrl = `${protocol}//${host}:${port}/ws/voice-stream`;
      
      console.log('Connecting to WebSocket:', wsUrl);
      console.log('Location:', { protocol: window.location.protocol, hostname: window.location.hostname });
      
      const ws = new WebSocket(wsUrl);

      ws.binaryType = "arraybuffer";
      
      // 保存 ws 引用以便后续使用
      wsRef.current = ws;

      // 等待连接建立和 ready 消息
      await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          console.log('WebSocket connection timeout');
          ws.close();
          reject(new Error("连接超时"));
        }, 10000); // 增加到 10 秒
        
        let isReady = false;

        ws.onopen = () => {
          console.log("Voice stream WebSocket connected");
          
          // 发送 start 消息
          const sessionId = `session_${Date.now()}`;
          sessionIdRef.current = sessionId;
          
          try {
            ws.send(JSON.stringify({
              type: "start",
              session_id: sessionId,
              thread_id: threadId,
            }));
          } catch (err) {
            clearTimeout(timeout);
            reject(new Error("发送 start 消息失败: " + err.message));
          }
        };

        ws.onmessage = async (event) => {
          // 处理 ready 消息
          if (!isReady && typeof event.data === "string") {
            try {
              const message = JSON.parse(event.data);
              if (message.type === "ready") {
                clearTimeout(timeout);
                isReady = true;
                setIsConnected(true);
                console.log("Voice stream ready:", message);
                resolve();
                return;
              }
            } catch (e) {
              // 不是 JSON 消息，继续处理
            }
          }
          
          // 连接建立后的正常消息处理
          if (isReady) {
            if (event.data instanceof ArrayBuffer) {
              // 二进制音频数据 - 播放
              try {
                if (!audioContextRef.current) {
                  audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
                }
                const audioContext = audioContextRef.current;
                const audioBuffer = await audioContext.decodeAudioData(event.data);
                const source = audioContext.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(audioContext.destination);
                source.start();
                console.log("Playing audio response");
              } catch (err) {
                console.error("Failed to play audio:", err);
              }
            } else {
              // JSON 消息
              try {
                const message = JSON.parse(event.data);
                console.log("Server message:", message);
                
                switch (message.type) {
                  case "transcript":
                    setTranscript(message.text);
                    break;
                  
                  case "response":
                    setResponse(message.text);
                    break;
                  
                  case "response_chunk":
                    setResponse((prev) => prev + message.text);
                    break;
                  
                  case "status":
                    setStatus(message.status);
                    break;
                  
                  case "error":
                    setError(message.message);
                    setStatus("idle");
                    break;
                  
                  default:
                    console.log("Unknown message type:", message.type);
                }
              } catch (e) {
                console.warn("Failed to parse message:", e);
              }
            }
          }
        };

        ws.onerror = (error) => {
          console.error("WebSocket error:", error);
          clearTimeout(timeout);
          if (!isReady) {
            reject(new Error("WebSocket 连接错误"));
          } else {
            setError("连接错误");
          }
        };

        ws.onclose = () => {
          console.log("Voice stream WebSocket closed");
          clearTimeout(timeout);
          setIsConnected(false);
          setIsRecording(false);
          if (!isReady) {
            reject(new Error("WebSocket 连接意外关闭"));
          }
        };
      });

    } catch (err) {
      console.error("Failed to connect:", err);
      setError(err.message || "连接失败");
      // 清理
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      throw err;
    }
  }, []);

  /**
   * 处理服务器消息
   */
  const handleServerMessage = useCallback((message) => {
    console.log("Server message:", message);

    switch (message.type) {
      case "transcript":
        setTranscript(message.text);
        break;
      
      case "response":
        setResponse(message.text);
        break;
      
      case "response_chunk":
        // 流式响应片段，追加到现有响应
        setResponse((prev) => prev + message.text);
        break;
      
      case "status":
        setStatus(message.status);
        break;
      
      case "error":
        setError(message.message);
        setStatus("idle");
        break;
      
      default:
        console.log("Unknown message type:", message.type);
    }
  }, []);

  /**
   * 播放音频
   */
  const playAudio = useCallback(async (audioData) => {
    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      }

      const audioContext = audioContextRef.current;
      const audioBuffer = await audioContext.decodeAudioData(audioData);
      
      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContext.destination);
      source.start();

      console.log("Playing audio response");
    } catch (err) {
      console.error("Failed to play audio:", err);
    }
  }, []);

  /**
   * 开始录音并发送音频流
   */
  const startRecording = useCallback(async () => {
    if (!isConnected || isRecording) return;

    try {
      setError(null);
      // 清空之前的转录和响应
      setTranscript("");
      setResponse("");

      // 请求麦克风权限
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      streamRef.current = stream;

      // 创建 AudioContext
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({
          sampleRate: 16000,
        });
      }

      const audioContext = audioContextRef.current;
      const source = audioContext.createMediaStreamSource(stream);

      // 加载 AudioWorklet 处理器
      try {
        await audioContext.audioWorklet.addModule('/audio-processor.js');
      } catch (err) {
        console.warn('Failed to load AudioWorklet, falling back to ScriptProcessor', err);
        // 如果 AudioWorklet 不可用，降级到 ScriptProcessor
        return startRecordingWithScriptProcessor(stream, audioContext, source);
      }

      // 创建 AudioWorkletNode
      const workletNode = new AudioWorkletNode(audioContext, 'audio-capture-processor');
      
      // 监听音频数据
      workletNode.port.onmessage = (event) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
          return;
        }

        // 发送音频数据
        try {
          wsRef.current.send(event.data);
        } catch (err) {
          console.error("Failed to send audio data:", err);
        }
      };

      source.connect(workletNode);
      workletNode.connect(audioContext.destination);

      workletNodeRef.current = workletNode;
      setIsRecording(true);

      console.log("Started recording and streaming audio (AudioWorklet)");
    } catch (err) {
      console.error("Failed to start recording:", err);
      setError(err.message || "无法访问麦克风");
    }
  }, [isConnected, isRecording]);

  /**
   * 降级方案: 使用 ScriptProcessor (用于不支持 AudioWorklet 的浏览器)
   */
  const startRecordingWithScriptProcessor = useCallback((stream, audioContext, source) => {
    try {
      // 创建 ScriptProcessor 来捕获音频数据
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      
      processor.onaudioprocess = (e) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
          return;
        }

        // 获取音频数据
        const inputData = e.inputBuffer.getChannelData(0);
        
        // 转换为 Int16Array (PCM 16bit)
        const pcmData = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]));
          pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }

        // 发送音频数据
        try {
          wsRef.current.send(pcmData.buffer);
        } catch (err) {
          console.error("Failed to send audio data:", err);
        }
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      workletNodeRef.current = processor;
      setIsRecording(true);

      console.log("Started recording and streaming audio (ScriptProcessor fallback)");
    } catch (err) {
      console.error("Failed to start recording with ScriptProcessor:", err);
      setError(err.message || "无法访问麦克风");
    }
  }, [isRecording]);

  /**
   * 停止录音
   */
  const stopRecording = useCallback(() => {
    if (!isRecording) return;

    // 停止音频流
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    // 断开处理器
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }

    setIsRecording(false);
    console.log("Stopped recording");
  }, [isRecording]);

  /**
   * 断开连接
   */
  const disconnect = useCallback(() => {
    // 停止录音
    stopRecording();

    // 关闭 WebSocket
    if (wsRef.current) {
      try {
        if (wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: "stop" }));
        }
      } catch (e) {
        console.warn("Failed to send stop message (ignored):", e);
      } finally {
        try {
          // 即使在 CONNECTING 状态也可以直接关闭
          wsRef.current.close();
        } catch (e) {
          // 忽略关闭中的异常
        }
      }
      wsRef.current = null;
    }

    // 关闭 AudioContext
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    setIsConnected(false);
    sessionIdRef.current = null;
    console.log("Disconnected from voice stream");
  }, [stopRecording]);

  // 清理：仅在组件卸载时运行一次，避免因函数引用变化触发意外断开
  useEffect(() => {
    // 防止 StrictMode 清理
    if (cleanupInitializedRef.current) {
      return () => {
        // 空的 cleanup
      };
    }
    
    cleanupInitializedRef.current = true;
    
    return () => {
      // StrictMode 的测试卸载 - 不做任何清理
    };
  }, []);

  return {
    // 状态
    isConnected,
    isRecording,
    status,
    transcript,
    response,
    error,

    // 操作
    connect,
    disconnect,
    startRecording,
    stopRecording,
  };
}
