import React, { useState, useRef, useEffect, useCallback } from "react";
import "./styles/index.css";
import backgroundImg from "./styles/img/background.jpg";
import AudioRecordButton from "../../components/AudioRecordButton.jsx";
import EEGWaveformDisplay from "../../components/EEGWaveformDisplay.jsx";
import EEGDeviceControlPanel from "../../components/EEGDeviceControlPanel.jsx";
import ChatApp from "./ChatAppCopy.jsx";
import { useWebRTC } from "../../hooks/useWebRTC.js";
import { v4 as uuidv4 } from "uuid";

const API_PREFIX = "http://localhost:8000";

const makeWsUrl = (path) => {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  // 使用后端的 WebSocket 地址
  const host = window.location.hostname;
  const port = 8000;  // 后端端口
  return `${protocol}://${host}:${port}${path}`;
};

// 获取 API 前缀（用于 HTTP 请求）
const getApiPrefix = () => {
  const hostname = window.location.hostname;
  if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
    return `http://${hostname}:8000`;
  }
  return "http://localhost:8000";
};

export default function ChatNew() {
  const [messages, setMessages] = useState([]);
  const [activeThreadId, setActiveThreadId] = useState(null);
  const [chatStatus, setChatStatus] = useState("idle");
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [isEntering, setIsEntering] = useState(true);
  const [isHangingUp, setIsHangingUp] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [callStatus, setCallStatus] = useState(null);
  const [activeCallRoomId, setActiveCallRoomId] = useState(null);
  const [pipelineStatus, setPipelineStatus] = useState("connecting");
  const [pipelineEvent, setPipelineEvent] = useState(null);
  const [showVideoPlaceholder, setShowVideoPlaceholder] = useState(true);
  const [activeThread, setActiveThread] = useState(null);
  const [showEEGControlPanel, setShowEEGControlPanel] = useState(false);
  const [useRealEEGData, setUseRealEEGData] = useState(false);
  
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const chatSocketRef = useRef(null);
  const messageIdsRef = useRef(new Set());
  const remoteAudioRef = useRef(null);

  // WebRTC hook - 参照ChatApp.jsx
  const {
    startCall,
    stopCall,
    connectionState,
    isConnecting,
    remoteAudioRef: webrtcAudioRef,
  } = useWebRTC(
    activeCallRoomId,
    (remoteStream, streamType) => {
      console.log("Remote stream received", streamType || "audio", remoteStream);
      if (streamType === 'video') {
        // 视频流处理在ChatWindow中
        console.log("Video stream received");
      } else {
        // 处理音频流
        if (remoteAudioRef.current) {
          remoteAudioRef.current.srcObject = remoteStream;
        }
      }
    },
    (error) => {
      console.error("WebRTC error:", error);
      setCallStatus((prev) => prev ? { ...prev, message: `连接失败: ${error.message}` } : null);
    }
  );
  
  // 入场动画
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsEntering(false);
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  // 处理通话操作 - 参照ChatApp.jsx
  const handleCallAction = useCallback(
    async (mode) => {
      if (!activeThreadId) {
        setCallStatus({ mode, message: "请选择会话后再发起通话" });
        return;
      }

      const roomId = `${activeThreadId}-${mode}`;

      // 如果已有通话，先停止
      if (activeCallRoomId) {
        stopCall();
        setActiveCallRoomId(null);
        setCallStatus(null);
        setShowVideoPlaceholder(true);
        return;
      }

      // 启动新通话
      setActiveCallRoomId(roomId);
      setCallStatus({ mode, message: "正在建立连接…" });
      // 先不隐藏占位符，等连接成功后再隐藏

      try {
        await startCall({ roomId, mode });
        setCallStatus({ mode, message: "通话已建立" });
        // 连接建立后，等待一下再隐藏占位符，让视频流有时间加载
        if (mode === 'video') {
          setTimeout(() => {
            setShowVideoPlaceholder(false);
          }, 500);
        }
      } catch (error) {
        console.error("Failed to start call", error);
        setCallStatus({ mode, message: "连接失败，请重试" });
        setActiveCallRoomId(null);
        setShowVideoPlaceholder(true);
      }
    },
    [activeThreadId, activeCallRoomId, startCall, stopCall]
  );

  // 监听连接状态变化 - 参照ChatApp.jsx
  useEffect(() => {
    if (connectionState === "connected") {
      setCallStatus((prev) => {
        if (prev && prev.mode === 'video') {
          // 连接成功后，隐藏占位符
          setShowVideoPlaceholder(false);
          return { ...prev, message: "通话中" };
        }
        return prev;
      });
    } else if (connectionState === "failed") {
      setCallStatus((prev) => prev ? { ...prev, message: "连接失败" } : null);
      setActiveCallRoomId(null);
      setShowVideoPlaceholder(true);
    } else if (connectionState === "closed") {
      setCallStatus(null);
      setActiveCallRoomId(null);
      setShowVideoPlaceholder(true);
    }
  }, [connectionState]);

  // 挂断处理
  const handleHangup = () => {
    // 停止通话
    if (activeCallRoomId) {
      stopCall();
      setActiveCallRoomId(null);
      setCallStatus(null);
      setShowVideoPlaceholder(true);
    }

    setIsHangingUp(true);
    setIsTransitioning(true);
    // 转场动画完成后，导航回星空页面
    setTimeout(() => {
      if (window.navigate) {
        window.navigate("#/");
      } else {
        window.location.hash = "#/";
      }
    }, 1500);
  };
  
  // 启动视频通话 - 参照ChatApp.jsx
  const startVideoCall = useCallback(() => {
    if (!activeThreadId || !activeThread) {
      setCallStatus({ mode: 'video', message: "请等待会话初始化..." });
      return;
    }
    // 直接调用handleCallAction启动视频通话
    handleCallAction('video');
  }, [activeThreadId, activeThread, handleCallAction]);
  
  // 进入页面1秒后自动启动视频通话
  useEffect(() => {
    if (!activeCallRoomId && !isHangingUp && activeThreadId) {
      const timer = setTimeout(() => {
        startVideoCall();
      }, 1000); // 1秒后触发
      return () => clearTimeout(timer);
    }
  }, [activeCallRoomId, isHangingUp, activeThreadId, startVideoCall]);


  // 自动滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 初始化或获取thread（与ChatApp保持一致）
  const initializeThread = useCallback(async () => {
    try {
      const response = await fetch(`${API_PREFIX}/chat/threads`);
      if (!response.ok) throw new Error("failed to fetch threads");
      const data = await response.json();
      
      if (data.length === 0) {
        // 如果没有thread，创建一个新的
        const created = await fetch(`${API_PREFIX}/chat/threads`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: "新对话", participants: ["me", "agent"] }),
        });
      if (created.ok) {
        const thread = await created.json();
        setActiveThreadId(thread.thread_id);
        setActiveThread(thread);
        }
        return;
      }
      
      // 使用第一个thread
      const firstThread = data[0];
      setActiveThreadId((prev) => prev ?? firstThread?.thread_id ?? null);
      if (firstThread && !activeThread) {
        setActiveThread(firstThread);
      }
    } catch (error) {
      console.error("Failed to initialize thread", error);
      // 如果API请求失败，创建一个默认的thread ID，以便模拟对话功能可以正常工作
      const defaultThreadId = `default-${uuidv4()}`;
      setActiveThreadId(defaultThreadId);
      setActiveThread({
        thread_id: defaultThreadId,
        title: "对话",
        participants: ["me", "agent"]
      });
    }
  }, []);

  // 初始化thread
  useEffect(() => {
    initializeThread();
  }, [initializeThread]);

  // 获取情绪对应的脑电波形数据 - 参照ChatApp.jsx
  const fetchEEGWaveform = useCallback(async (emotion) => {
    if (!emotion) return;

    try {
      const response = await fetch(`${API_PREFIX}/eeg/face-waveform/${emotion}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const waveformData = await response.json();
        console.log('EEG waveform data:', waveformData);

        // 更新脑电波形数据
        setPipelineEvent(prev => ({
          ...prev,
          eeg_waveform: {
            waveform: waveformData,
            emotion: emotion
          }
        }));
      }
    } catch (error) {
      console.error('Error fetching EEG waveform:', error);
    }
  }, []);

  // 处理情绪检测结果 - 参照ChatApp.jsx
  const handleEmotionUpdate = useCallback((emotionData) => {
    // 更新当前情绪状态
    if (emotionData.type === 'eeg_waveform') {
      // 处理脑电波形数据
      setPipelineEvent(prev => ({
        ...prev,
        eeg_waveform: {
          waveform: emotionData.waveform,
          emotion: emotionData.emotion
        }
      }));
    } else if (emotionData.type === 'face_emotion') {
      // 处理面部情绪数据
      setPipelineEvent(prev => ({
        ...prev,
        face_emotion: {
          label: emotionData.emotion || emotionData.label,
          confidence: emotionData.confidence,
          face_position: emotionData.face_position
        }
      }));

      // 同时更新emotion状态，确保情绪雷达能接收到数据
      setPipelineEvent(prev => ({
        ...prev,
        emotion: emotionData.emotion || emotionData.label
      }));

      // 当检测到面部情绪时，获取对应的脑电波形数据
      // 这样可以确保脑电波形数据只在需要时获取，而不是每3秒获取一次
      fetchEEGWaveform(emotionData.emotion || emotionData.label);
    }
  }, [fetchEEGWaveform]);

  // Pipeline WebSocket 连接 - 接收情绪和脑电波数据
  useEffect(() => {
    const url = makeWsUrl("/ws/pipeline");
    const socket = new WebSocket(url);

    socket.onopen = () => setPipelineStatus("connected");
    socket.onclose = () => setPipelineStatus("disconnected");
    socket.onerror = () => setPipelineStatus("error");
    socket.onmessage = (message) => {
      try {
        const payload = JSON.parse(message.data);
        setPipelineEvent(payload);
      } catch (error) {
        console.error("Failed to parse pipeline event", error);
      }
    };

    return () => socket.close();
  }, []);

  // WebSocket连接 - 接收消息
  useEffect(() => {
    if (!activeThreadId) return;

    setMessages([]);
    messageIdsRef.current = new Set();
    setMessagesLoading(true);

    // 如果是模拟模式，不需要建立WebSocket连接
    if (activeThreadId.startsWith('default-')) {
      setChatStatus("connected");
      setMessagesLoading(false);
      return;
    }

    const url = makeWsUrl(`/ws/chat?thread_id=${activeThreadId}`);
    const socket = new WebSocket(url);
    chatSocketRef.current = socket;

    socket.onopen = () => {
      setChatStatus("connected");
      setMessagesLoading(false);
    };
    socket.onclose = () => {
      setChatStatus("disconnected");
    };
    socket.onerror = () => {
      setChatStatus("error");
      setMessagesLoading(false);
    };
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type !== "message") return;
        const { message } = payload;
        if (message.thread_id !== activeThreadId) return;
        if (messageIdsRef.current.has(message.message_id)) return;
        messageIdsRef.current.add(message.message_id);
        
        // 直接使用后端消息格式，ChatWindow会处理
        setMessages((prev) => 
          [...prev, message].sort((a, b) => 
            new Date(a.created_at) - new Date(b.created_at)
          )
        );
      } catch (error) {
        console.error("Failed to parse chat event", error);
      } finally {
        setMessagesLoading(false);
      }
    };

    return () => {
      socket.close();
      chatSocketRef.current = null;
    };
  }, [activeThreadId]);

  const addSelfMessage = (text) => {
    const message = {
      message_id: uuidv4(),
      thread_id: activeThreadId,
      sender: "me",
      text: text.trim(),
      created_at: new Date().toISOString(),
    };
    console.log("Add self message:", message);
    setMessages((prev) => [...prev, message]);
  }

  const addAiMessage = (text) => {
    const message = {
      message_id: uuidv4(),
      thread_id: activeThreadId,
      sender: "ai",
      text: text.trim(),
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, message]);
  }

  // 发送消息
  const handleSend = useCallback(async (text) => {
    if (!text || !text.trim() || !activeThreadId) return;

    try {
      await fetch(`${API_PREFIX}/chat/threads/${activeThreadId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim() }),
      });
    } catch (error) {
      console.error("Failed to send chat message", error);
    }
  }, [activeThreadId]);

  // 处理语音响应
  const handleAudioResponse = useCallback((result) => {
    console.log("Audio response received:", result);
    // ChatWindow会通过WebSocket接收消息，这里不需要手动添加
  }, []);

  return (
    <div className={`chatnew-root${isEntering ? ' is-entering' : ''}${isTransitioning ? ' is-transitioning' : ''}`}>
      <div 
        className="chatnew-background" 
        style={{ backgroundImage: `url('${backgroundImg}')` }}
        aria-hidden="true"
      />
      
      {/* 右上角脑电波面板 */}
      <div className="chatnew-eeg-panel">
        <div className="eeg-panel-header">
          <h3>脑电波监测</h3>
          <div className="eeg-panel-controls">
            <button 
              className={`eeg-mode-toggle ${useRealEEGData ? 'real-mode' : 'sim-mode'}`}
              onClick={() => setUseRealEEGData(!useRealEEGData)}
              title={useRealEEGData ? "切换到模拟数据" : "切换到真实设备"}
            >
              {useRealEEGData ? "真实设备" : "模拟数据"}
            </button>
            <button 
              className="eeg-panel-toggle"
              onClick={() => setShowEEGControlPanel(!showEEGControlPanel)}
              title="显示/隐藏设备控制面板"
            >
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 15.5A3.5 3.5 0 0 1 8.5 12A3.5 3.5 0 0 1 12 8.5a3.5 3.5 0 0 1 3.5 3.5a3.5 3.5 0 0 1-3.5 3.5m7.43-2.53c.04-.32.07-.64.07-.97c0-.33-.03-.66-.07-1l2.11-1.63c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.3-.61-.22l-2.49 1c-.52-.39-1.08-.73-1.69-.98l-.37-2.65A.506.506 0 0 0 14 2h-4c-.25 0-.46.18-.5.42l-.37 2.65c-.63.25-1.17.59-1.69.98l-2.49-1c-.22-.08-.49 0-.61.22l-2 3.46c-.13.22-.07.49.12.64L4.57 11c-.04.34-.07.67-.07 1c0 .33.03.65.07.97l-2.11 1.66c-.19.15-.25.42-.12.64l2 3.46c.12.22.39.3.61.22l2.49-1.01c.52.4 1.06.74 1.69.99l.37 2.65c.04.24.25.42.5.42h4c.25 0 .46-.18.5-.42l.37-2.65c.63-.26 1.17-.59 1.69-.99l2.49 1.01c.22.08.49 0 .61-.22l2-3.46c.12-.22.07-.49-.12-.64l-2.11-1.66Z" fill="currentColor"/>
              </svg>
            </button>
          </div>
        </div>
        <EEGWaveformDisplay
          faceEmotion={pipelineEvent?.face_emotion}
          eegWaveform={pipelineEvent?.eeg_waveform}
          useRealData={useRealEEGData}
        />
        {showEEGControlPanel && (
          <div className="eeg-control-panel-container">
            <EEGDeviceControlPanel />
          </div>
        )}
      </div>

      <div className="chatnew-content">
        {/* 左侧视频通话区域 */}
        <div className="chatnew-video-container">
          <div className={`chatnew-video-frame${callStatus && callStatus.mode === 'video' ? ' has-video-stream' : ''}`}>
            {/*{showVideoPlaceholder && (!callStatus || callStatus.mode !== 'video') ? (*/}
            {/*  <div className="chatnew-video-placeholder">*/}
            {/*    <div className="chatnew-video-placeholder-icon">*/}
            {/*      <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">*/}
            {/*        <path d="M17 10.5V7C17 6.45 16.55 6 16 6H4C3.45 6 3 6.45 3 7V17C3 17.55 3.45 18 4 18H16C16.55 18 17 17.55 17 17V13.5L21 17.5V6.5L17 10.5Z" fill="rgba(255, 255, 255, 0.6)"/>*/}
            {/*      </svg>*/}
            {/*    </div>*/}
            {/*    <p className="chatnew-video-placeholder-text">视频通话</p>*/}
            {/*    <p className="chatnew-video-placeholder-subtitle">*/}
            {/*      {callStatus?.message || "等待连接..."}*/}
            {/*    </p>*/}
            {/*  </div>*/}
            {/*) : activeThread ? (*/}
              {/* <div className="chatnew-chatwindow-wrapper">
                
                {callStatus && callStatus.mode === 'video' && (
                  <button 
                    className={`chatnew-hangup-btn${isHangingUp ? ' is-hanging-up' : ''}`}
                    aria-label="挂断"
                    onClick={handleHangup}
                  >
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M19 6.41L17.59 5L12 10.59L6.41 5L5 6.41L10.59 12L5 17.59L6.41 19L12 13.41L17.59 19L19 17.59L13.41 12L19 6.41Z" fill="white"/>
                    </svg>
                  </button>
                )}
              </div> */}
              <ChatApp handleHangup={handleHangup} />
            {/*) : null}*/}
          </div>
        </div>

        {/* 右侧消息区域 - 暂时保留，但ChatWindow会处理消息显示 */}
        <div className="chatnew-messages-wrapper">
          <div className="chatnew-messages" ref={messagesContainerRef}>
            {messages.length === 0 ? (
              <div className="chatnew-empty">
                <p>开始一段对话吧...</p>
              </div>
            ) : (
              messages.map((message) => (
                <div 
                  key={message.message_id || message.id} 
                  className={`chatnew-message ${message.sender === 'me' || message.speaker === 'me' || message.role === 'user' ? 'chatnew-message--user' : 'chatnew-message--ai'}`}
                >
                  <div className="chatnew-message-content">
                    {message.content || message.text}
                  </div>
                  <div className="chatnew-message-time">
                    {new Date(message.created_at || Date.now()).toLocaleTimeString("zh-CN", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>
      </div>
      
      {/* 语音录制按钮区域 - 单独一行 */}
      <div className="chatnew-audio-record-container">
        <AudioRecordButton
          threadId={activeThreadId}
          onResponse={handleAudioResponse}
          disabled={!activeThreadId || chatStatus !== "connected"}
          addSelfMessage={addSelfMessage}
          addAiMessage={addAiMessage}
          simulateMode={true}
        />
      </div>
      
      {/* 隐藏的音频元素用于播放远端音频 - 参照ChatApp.jsx */}
      <audio ref={remoteAudioRef} autoPlay style={{ display: "none" }} />
      <audio ref={webrtcAudioRef} autoPlay style={{ display: "none" }} />
    </div>
  );
}

