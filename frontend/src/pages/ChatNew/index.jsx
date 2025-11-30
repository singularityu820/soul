import React, { useState, useRef, useEffect, useCallback } from "react";
import "./styles/index.css";
// 导入新的资源图片
import backgroundImg from "../../assets/newChat/背景图片.jpg";
import leftBottomBoxImg from "../../assets/newChat/左下角框.png";
import hangupBtnImg from "../../assets/newChat/挂断按键.png";
import playBtnImg from "../../assets/newChat/播放按键.png";
import pauseBtnImg from "../../assets/newChat/暂停按键.png";
import resumeBtnImg from "../../assets/newChat/继续按键.png";
import microphoneBtnImg from "../../assets/newChat/麦克风按键.png";
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

export default function ChatNew() {
  const [activeThreadId, setActiveThreadId] = useState(null);
  const [isEntering, setIsEntering] = useState(true);
  const [pipelineEvent, setPipelineEvent] = useState(null);
  const [showEEGControlPanel, setShowEEGControlPanel] = useState(false);
  const [useRealEEGData, setUseRealEEGData] = useState(false);
  
  const pipelineSocketRef = useRef(null);
  const pipelineReconnectTimerRef = useRef(null);
  const [voiceTranscript, setVoiceTranscript] = useState(null);
  const [voiceResponse, setVoiceResponse] = useState(null);
  const live2dRef = useRef(null);
  
  // 入场动画
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsEntering(false);
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  // 初始化或获取thread
  const initializeThread = useCallback(async () => {
    try {
      const response = await fetch(`${API_PREFIX}/chat/threads`);
      if (!response.ok) throw new Error("failed to fetch threads");
      const data = await response.json();
      
      if (data.length === 0) {
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
      const firstThread = data[0];
      setActiveThreadId((prev) => prev ?? firstThread?.thread_id ?? null);
    } catch (error) {
      console.error("Failed to initialize thread", error);
      const defaultThreadId = `default-${uuidv4()}`;
      setActiveThreadId(defaultThreadId);
    }
  }, []);

  useEffect(() => {
    initializeThread();
  }, [initializeThread]);

  // 订阅 voice call store
  useEffect(() => {
    const unsub = subscribeVoiceCall((d) => {
      setVoiceTranscript(d.transcript || null);
      setVoiceResponse(d.response || null);
    });
    const current = getVoiceCallData();
    setVoiceTranscript(current.transcript || null);
    setVoiceResponse(current.response || null);
    return () => unsub();
  }, []);

  // Pipeline WebSocket 连接
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
      socket.onclose = () => {
        pipelineSocketRef.current = null;
        if (shouldReconnect) {
          pipelineReconnectTimerRef.current = window.setTimeout(connect, 2000);
        }
      };
    };
    connect();
    return () => {
      shouldReconnect = false;
      if (pipelineReconnectTimerRef.current) clearTimeout(pipelineReconnectTimerRef.current);
      safelyCloseWebSocket(pipelineSocketRef.current, "ChatNew pipeline cleanup");
    };
  }, []);

  const addSelfMessage = async (text) => { if (!activeThreadId) return; };
  const addAiMessage = async (text) => { if (!activeThreadId) return; };
  const handleAudioResponse = useCallback((result) => {}, []);
  const handleHangup = useCallback(() => {}, []);

  // --- 样式定义 ---
  const styles = {
    layoutContainer: {
      display: 'flex',
      width: '100%',
      height: '100%',
      padding: '40px 40px 100px 40px',
      gap: '24px',
      boxSizing: 'border-box',
      zIndex: 1,
      position: 'relative'
    },
    columnLeft: {
      flex: '0 0 38%',
      display: 'flex',
      flexDirection: 'column',
      gap: '24px',
      height: '100%'
    },
    columnRight: {
      flex: '1',
      height: '100%',
      position: 'relative'
    },
    card: {
      background: 'rgba(20, 20, 20, 0.6)',
      backdropFilter: 'blur(20px)',
      borderRadius: '32px',
      overflow: 'hidden',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
      position: 'relative' // 确保内部绝对定位相对于卡片
    },
    cardVideo: {
      flex: '1',
      minHeight: '0'
    },
    cardEEG: {
      height: '240px',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      background: '#0a0a0a'
    },
    cardCharacter: {
      height: '100%',
      background: 'rgba(255, 180, 150, 0.1)'
    }
  };

  // ... inside ChatNew component ...

  return (
    <div className={`chatnew-root${isEntering ? ' is-entering' : ''}`}>
      <div 
        className="chatnew-background" 
        style={{ backgroundImage: `url('${backgroundImg}')` }}
        aria-hidden="true"
      />
      
      {/* 使用新的 CSS 类名布局 */}
      <div className="chatnew-layout-container">
        
        {/* 左侧列 */}
        <div className="chatnew-column-left">
          {/* 视频卡片 */}
          <div className="chatnew-card chatnew-card-video chatnew-video-frame-override">
            <ChatApp />
          </div>
          {/* EEG 卡片 */}
          <div className="chatnew-card chatnew-card-eeg">
             <div className="chatnew-eeg-container">
               {/* 开关按钮 (可选) */}
               <div style={{ position: 'absolute', top: 12, right: 12, zIndex: 20 }}>
                  <button 
                    onClick={() => setUseRealEEGData(!useRealEEGData)}
                    style={{ fontSize: '10px', padding: '4px 8px', background: 'rgba(255,255,255,0.15)', border:'none', color:'rgba(255,255,255,0.6)', borderRadius:'4px', cursor:'pointer' }}
                  >
                    {useRealEEGData ? "Real" : "Sim"}
                  </button>
               </div>
               <EEGWaveformDisplay
                faceEmotion={pipelineEvent?.face_emotion}
                eegWaveform={pipelineEvent?.emotion}
                useRealData={useRealEEGData}
               />
            </div>
            {showEEGControlPanel && (
              <div className="eeg-control-panel-container">
                <EEGDeviceControlPanel />
              </div>
            )}
          </div>
        </div>

        {/* 右侧列 */}
        <div className="chatnew-column-right">
          <div className="chatnew-card chatnew-card-character">
             
             {/* 聊天气泡包裹层 */}
             <div className="voice-call-chatbox-wrapper">
                <VoiceCallChatBox 
                  transcript={voiceTranscript} 
                  response={voiceResponse} 
                  className="voice-call-chatbox-embedded" 
                />
             </div>
          </div>
        </div>

      </div>
      
      {/* 底部控制栏 */}
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
    </div>
  );
}