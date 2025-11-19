import React, { useState, useRef, useEffect, useCallback } from "react";
import "./styles/index.css";
import backgroundImg from "./styles/img/background.jpg";
import AudioRecordButton from "../../components/AudioRecordButton.jsx";
import EEGWaveformDisplay from "../../components/EEGWaveformDisplay.jsx";
import EEGDeviceControlPanel from "../../components/EEGDeviceControlPanel.jsx";
import ChatApp from "./ChatAppCopy.jsx";
import { v4 as uuidv4 } from "uuid";
import { resolveApiBaseUrl, resolveWebSocketUrl } from "../../utils/endpointResolver";
import { safelyCloseWebSocket } from "../../utils/websocketHelpers";

const API_PREFIX = resolveApiBaseUrl();
const PIPELINE_WS_OPTIONS = {
  envVar: "VITE_PIPELINE_WS_URL",
  windowKeys: [
    "pipelineWsUrl",
    "pipelineWSUrl",
    "pipelineWebsocketUrl",
    "pipelineSocketUrl",
    "pipelineStreamUrl",
  ],
};
const CHAT_WS_OPTIONS = {
  envVar: "VITE_CHAT_WS_URL",
  windowKeys: ["chatWsUrl", "chatSocketUrl", "chatWebsocketUrl"],
};

export default function ChatNew() {
  const [messages, setMessages] = useState([]);
  const [activeThreadId, setActiveThreadId] = useState(null);
  const [chatStatus, setChatStatus] = useState("idle");
  const [isEntering, setIsEntering] = useState(true);
  const [pipelineEvent, setPipelineEvent] = useState(null);
  const [showEEGControlPanel, setShowEEGControlPanel] = useState(false);
  const [useRealEEGData, setUseRealEEGData] = useState(false);
  
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const pipelineSocketRef = useRef(null);
  const pipelineReconnectTimerRef = useRef(null);
  const chatSocketRef = useRef(null);
  const messageIdsRef = useRef(new Set());
  
  // 入场动画
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsEntering(false);
    }, 100);
    return () => clearTimeout(timer);
  }, []);

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
        }
        return;
      }
      
      // 使用第一个thread
      const firstThread = data[0];
      setActiveThreadId((prev) => prev ?? firstThread?.thread_id ?? null);
    } catch (error) {
      console.error("Failed to initialize thread", error);
      // 如果API请求失败，创建一个默认的thread ID，以便模拟对话功能可以正常工作
      const defaultThreadId = `default-${uuidv4()}`;
      setActiveThreadId(defaultThreadId);
    }
  }, []);

  // 初始化thread
  useEffect(() => {
    initializeThread();
  }, [initializeThread]);

  // Pipeline WebSocket 连接 - 接收情绪和脑电波数据
  useEffect(() => {
    let shouldReconnect = true;

    const connect = () => {
      const url = resolveWebSocketUrl("/ws/pipeline", PIPELINE_WS_OPTIONS);
      const socket = new WebSocket(url);
      pipelineSocketRef.current = socket;

      socket.onmessage = (message) => {
        try {
          const payload = JSON.parse(message.data);
          setPipelineEvent(payload);
        } catch (error) {
          console.error("Failed to parse pipeline event", error);
        }
      };

      socket.onerror = (event) => {
        console.error("Pipeline socket error", event);
      };

      socket.onclose = () => {
        pipelineSocketRef.current = null;
        if (!shouldReconnect) return;
        pipelineReconnectTimerRef.current = window.setTimeout(connect, 2000);
      };
    };

    connect();

    return () => {
      shouldReconnect = false;
      if (pipelineReconnectTimerRef.current) {
        clearTimeout(pipelineReconnectTimerRef.current);
        pipelineReconnectTimerRef.current = null;
      }
      safelyCloseWebSocket(pipelineSocketRef.current, "ChatNew pipeline cleanup");
      pipelineSocketRef.current = null;
    };
  }, []);

  // WebSocket连接 - 接收消息
  useEffect(() => {
    if (!activeThreadId) return;

    setMessages([]);
    messageIdsRef.current = new Set();

    // 如果是模拟模式，不需要建立WebSocket连接
    if (activeThreadId.startsWith('default-')) {
      setChatStatus("connected");
      return;
    }

    const url = resolveWebSocketUrl(`/ws/chat?thread_id=${activeThreadId}`, CHAT_WS_OPTIONS);
    const socket = new WebSocket(url);
    chatSocketRef.current = socket;

    socket.onopen = () => {
      setChatStatus("connected");
    };
    socket.onclose = () => {
      setChatStatus("disconnected");
    };
    socket.onerror = () => {
      setChatStatus("error");
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

  // 处理语音响应
  const handleAudioResponse = useCallback((result) => {
    console.log("Audio response received:", result);
    // ChatWindow会通过WebSocket接收消息，这里不需要手动添加
  }, []);

  return (
    <div className={`chatnew-root${isEntering ? ' is-entering' : ''}`}>
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
        {/* 左侧聊天与情绪检测区域 */}
        <div className="chatnew-video-container">
          <div className="chatnew-video-frame">
            <ChatApp />
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
        />
      </div>
      
    </div>
  );
}

