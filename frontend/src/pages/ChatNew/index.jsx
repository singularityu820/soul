import React, { useState, useRef, useEffect, useCallback } from "react";
import "./styles/index.css";
import backgroundImg from "../../../img/background_chat.jpg";
import VoiceCallControls from "../../components/VoiceCallControls.jsx";
import EEGWaveformDisplay from "../../components/EEGWaveformDisplay.jsx";
import EEGDeviceControlPanel from "../../components/EEGDeviceControlPanel.jsx";
import ChatApp from "./ChatAppCopy.jsx";
import VoiceCallChatBox from "../../components/VoiceCallChatBox.jsx";
import { subscribeVoiceCall, getVoiceCallData } from "../../utils/voiceCallStore";
import { v4 as uuidv4 } from "uuid";
import { resolveApiBaseUrl, resolveWebSocketUrl } from "../../utils/endpointResolver";
import { safelyCloseWebSocket } from "../../utils/websocketHelpers";
import ReactLive2d from "../../Live2D/src/index.jsx";

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
  const [voiceTranscript, setVoiceTranscript] = useState(null);
  const [voiceResponse, setVoiceResponse] = useState(null);
  const messageIdsRef = useRef(new Set());
  const live2dRef = useRef(null);
  
  // 入场动画
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsEntering(false);
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  // （消息显示由左侧 ChatApp 处理，避免右侧重复展示）

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

  // 如果视频区域被样式隐藏（例如临时 CSS 隐藏），则尽快停止摄像头采集以释放设备
  useEffect(() => {
    try {
      const el = document.querySelector('.chatnew-video-frame');
      if (el) {
        const style = window.getComputedStyle(el);
        if (style && style.display === 'none') {
          // 设置全局标志，避免子组件再次尝试打开摄像头
          window.__EMOTION_DETECTION_DISABLED = true;
          // 调用全局停止接口（ChatWindow 在 mount 时会注册该函数）
          if (typeof window.__stopEmotionStream === 'function') {
            try { window.__stopEmotionStream(); } catch (e) { console.warn('Failed to call __stopEmotionStream', e); }
          }
          console.log('[ChatNew] Video frame hidden via CSS, emotion detection disabled temporarily');
        }
      }
    } catch (e) {
      console.warn('[ChatNew] Error checking video frame visibility', e);
    }
  }, []);

  // 订阅 voice call store（用于将聊天框提升到页面级别）
  useEffect(() => {
    const unsub = subscribeVoiceCall((d) => {
      setVoiceTranscript(d.transcript || null);
      setVoiceResponse(d.response || null);
    });
    // initialize with current data
    const current = getVoiceCallData();
    setVoiceTranscript(current.transcript || null);
    setVoiceResponse(current.response || null);
    return () => unsub();
  }, []);

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

  // Chat messages 由左侧 ChatApp（ChatAppCopy）通过其自己的 WebSocket 管理并显示。
  // 这里不再在右侧重复建立 WebSocket 或本地消息状态，避免重复渲染与刷新。

  // 将语音通话产生的消息发送到后端，由后端广播并由 ChatApp 的 WebSocket 接收显示
  const addSelfMessage = async (text) => {
    // 全模态实时通话为主：不再把实时语音消息写入旧的 chat threads API。
    if (!activeThreadId) return;
    console.debug('[ChatNew] addSelfMessage skipped (all-modal realtime mode):', text.slice(0, 80));
  };

  const addAiMessage = async (text) => {
    // 同上：不再写入 chat threads API
    if (!activeThreadId) return;
    console.debug('[ChatNew] addAiMessage skipped (all-modal realtime mode):', text.slice(0, 80));
  };

  // 处理语音响应
  const handleAudioResponse = useCallback((result) => {
    console.log("Audio response received:", result);
    // ChatWindow会通过WebSocket接收消息，这里不需要手动添加
  }, []);

  // 处理挂断通话（返回用户界面）
  const handleHangup = useCallback(() => {
    console.log("Call ended, returning to chat interface");
    // 可以添加导航逻辑或状态重置
    // 例如：navigate('/') 或重置消息列表
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
          eegWaveform={pipelineEvent?.emotion}
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

        {/* 右侧消息区域已移除，消息显示由左侧 ChatApp（ChatWindow）负责，避免重复 */}
        {/* 全局语音通话小聊天框（页面级） */}
        <VoiceCallChatBox transcript={voiceTranscript} response={voiceResponse} className="voice-call-chatbox-page" />
      </div>
      
      {/* 语音通话控制区域 - 四个按钮 */}
      <div className="chatnew-voice-controls-container">
        <VoiceCallControls
          threadId={activeThreadId}
          onResponse={handleAudioResponse}
          disabled={!activeThreadId}
          addSelfMessage={addSelfMessage}
          addAiMessage={addAiMessage}
          onHangup={handleHangup}
        />
      </div>
      
      <ReactLive2d
        ref={live2dRef}
        width="300"
        height="500"
      />
    </div>
  );
}

