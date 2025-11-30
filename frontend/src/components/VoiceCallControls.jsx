import { useEffect, useState } from "react";
import { useQwenRealtime } from "../hooks/useQwenRealtime";
import { setVoiceCallData } from "../utils/voiceCallStore";
import "./VoiceCallControls.css";
import hangupBtnImg from "../assets/newChat/挂断按键.png";
import playBtnImg from "../assets/newChat/播放按键.png";
import pauseBtnImg from "../assets/newChat/暂停按键.png";
import resumeBtnImg from "../assets/newChat/继续按键.png";
import microphoneBtnImg from "../assets/newChat/麦克风按键.png";

/**
 * 语音通话控制组件
 * 
 * 四个按钮：
 * 1. 开始实时语音通话
 * 2. 暂停实时语音通话
 * 3. 挂断语音通话（返回用户界面）
 * 4. 发送语音消息（非实时，仅在暂停时可用）
 */
export default function VoiceCallControls({
  threadId,
  onResponse,
  disabled = false,
  addSelfMessage,
  addAiMessage,
  onHangup, // 挂断回调
}) {
  const [isPaused, setIsPaused] = useState(false);
  const [callState, setCallState] = useState("idle"); // idle, connecting, active, paused
  
  const {
    isConnected,
    isConnectedRef, // 用于同步读取连接状态
    isRecording,
    recordingRef, // 用于同步读取录音状态
    status,
    transcript: streamTranscript,
    response: streamResponse,
    error: streamError,
    isAudioPlaying,
    connect,
    disconnect,
    startRecording,
    stopRecording,
    interrupt,
  } = useQwenRealtime();

  // 监听连接状态 - 使用 isPaused 作为主要判断
  useEffect(() => {
    console.log("[VoiceCallControls] State check:", { isConnected, isRecording, isPaused, callState });
    
    // 只在连接断开时重置为 idle，其他状态由按钮处理器显式管理
    if (!isConnected && callState !== "idle" && callState !== "connecting") {
      console.log("[VoiceCallControls] Connection lost, resetting to idle");
      setCallState("idle");
      setIsPaused(false);
    }
  }, [isConnected, callState]);

  // 实时更新转录文本
  useEffect(() => {
    // 更新共享 store，页面层组件可订阅以显示聊天框
    setVoiceCallData({ transcript: streamTranscript });
    if (streamTranscript && streamTranscript.trim()) {
      console.log("[VoiceCallControls] Transcript:", streamTranscript);
    }
  }, [streamTranscript]);

  // 实时更新响应文本
  useEffect(() => {
    // 更新共享 store，页面层组件可订阅以显示聊天框
    setVoiceCallData({ response: streamResponse });
    if (streamResponse && streamResponse.trim()) {
      console.log("[VoiceCallControls] Response:", streamResponse);
    }
  }, [streamResponse]);

  // 通话完成后添加到消息列表
  useEffect(() => {
    if (!isRecording && streamTranscript && streamResponse) {
      if (status === "idle") {
        console.log("[VoiceCallControls] Call completed, adding messages");
        
        if (addSelfMessage && streamTranscript) {
          addSelfMessage(streamTranscript);
        }
        
        if (addAiMessage && streamResponse) {
          addAiMessage(streamResponse);
        }
        
        if (onResponse) {
          onResponse({
            transcript: streamTranscript,
            response_text: streamResponse,
            simulated: false,
          });
        }
      }
    }
  }, [isRecording, streamTranscript, streamResponse, status, addSelfMessage, addAiMessage, onResponse]);

  // 1. 开始实时语音通话
  const handleStartCall = async () => {
    if (!threadId || disabled) {
      console.warn("[VoiceCallControls] Cannot start call:", { threadId, disabled });
      return;
    }
    
    try {
      console.log("[VoiceCallControls] Starting call...");
      setCallState("connecting");
      setIsPaused(false); // 先重置暂停状态
      
      console.log("[VoiceCallControls] Connecting to thread:", threadId);
      await connect(threadId);
      console.log("[VoiceCallControls] Connected successfully");
      
      // 使用 ref 轮询检查 isConnected，最多等待 2 秒
      let retries = 20;
      while (!isConnectedRef.current && retries > 0) {
        await new Promise(resolve => setTimeout(resolve, 100));
        retries--;
        console.log('[VoiceCallControls] Waiting for connection...', { 
          isConnectedRef: isConnectedRef.current, 
          isConnected, 
          retries 
        });
      }
      
      if (!isConnectedRef.current) {
        console.error('[VoiceCallControls] Connection timeout');
        setCallState("idle");
        return;
      }
      
      console.log("[VoiceCallControls] Starting recording...");
      await startRecording();
      console.log("[VoiceCallControls] Recording API called");
      
      // 使用 ref 轮询检查 isRecording，最多等待 1 秒
      retries = 10;
      while (!recordingRef.current && retries > 0) {
        await new Promise(resolve => setTimeout(resolve, 100));
        retries--;
        console.log('[VoiceCallControls] Waiting for recording...', { 
          recordingRef: recordingRef.current,
          isRecording, 
          retries 
        });
      }
      
      if (recordingRef.current) {
        setCallState("active");
        console.log("[VoiceCallControls] Call is now active");
      } else {
        console.error('[VoiceCallControls] Recording failed to start');
        setCallState("idle");
      }
    } catch (error) {
      console.error("[VoiceCallControls] Failed to start call:", error);
      setCallState("idle");
      setIsPaused(false);
    }
  };

  // 2. 暂停实时语音通话
  const handlePauseCall = () => {
    if (isRecording) {
      stopRecording();
      setIsPaused(true);
      setCallState("paused");
      console.log("[VoiceCallControls] Call paused");
    }
  };

  // 2b. 恢复实时语音通话
  const handleResumeCall = async () => {
    if (!isRecording && isConnected) {
      try {
        await startRecording();
        setIsPaused(false);
        setCallState("active");
        console.log("[VoiceCallControls] Call resumed");
      } catch (error) {
        console.error("[VoiceCallControls] Failed to resume call:", error);
      }
    }
  };

  // 3. 挂断语音通话
  const handleHangup = () => {
    if (isRecording) {
      stopRecording();
    }
    disconnect();
    setIsPaused(false);
    setCallState("idle");
    console.log("[VoiceCallControls] Call ended");
    
    if (onHangup) {
      onHangup();
    }
  };

  // 4. 发送语音消息（非实时，仅在暂停时）
  const handleSendVoiceMessage = async () => {
    if (!isPaused || !isConnected) {
      console.warn("[VoiceCallControls] Can only send voice message when paused");
      return;
    }
    
    try {
      console.log("[VoiceCallControls] Sending voice message...");
      // 开始短暂录音
      await startRecording();
      
      // 录音3秒后自动停止
      setTimeout(() => {
        stopRecording();
        console.log("[VoiceCallControls] Voice message sent");
      }, 3000);
    } catch (error) {
      console.error("[VoiceCallControls] Failed to send voice message:", error);
    }
  };

  // 获取状态文本
  const getStatusText = () => {
    if (callState === "connecting") return "连接中...";
    if (callState === "active") {
      if (status === "transcribing") return "识别中...";
      if (status === "generating") return "思考中...";
      if (isAudioPlaying) return "播放中...";
      return "通话中";
    }
    if (callState === "paused") return "已暂停";
    return "待机";
  };

  // 获取错误提示
  const getErrorMessage = () => {
    if (streamError) return streamError;
    if (!threadId) return "未选择对话";
    if (disabled) return "通话功能已禁用";
    return null;
  };

  const errorMessage = getErrorMessage();

  return (
    <div className="voice-call-controls">
      {/* 状态显示 */}
      <div className="voice-call-status">
        <div className={`status-indicator status-${callState}`}>
          <span className="status-dot"></span>
          <span className="status-text">{getStatusText()}</span>
        </div>
        
        {/* 转录和响应显示已提升到页面级 VoiceCallChatBox 组件 */}
        
        {errorMessage && (
          <div className="voice-call-error">
            <span className="error-icon">⚠️</span>
            {errorMessage}
          </div>
        )}
      </div>

      {/* 控制按钮 */}
      <div className="voice-call-buttons">
        {/* 1. 开始通话按钮 */}
        <button
          className="voice-call-btn voice-call-btn-start"
          onClick={handleStartCall}
          disabled={disabled || !threadId || callState !== "idle"}
          title="开始实时语音通话"
        >
          <img src={microphoneBtnImg} alt="开始通话" style={{ width: '28px', height: '28px' }} />
          <span className="btn-label">开始通话</span>
        </button>

        {/* 2. 暂停/恢复按钮 */}
        <button
          className={`voice-call-btn voice-call-btn-pause ${isPaused ? 'paused' : ''}`}
          onClick={isPaused ? handleResumeCall : handlePauseCall}
          disabled={!isConnected || callState === "idle" || callState === "connecting"}
          title={isPaused ? "恢复通话" : "暂停通话"}
        >
          {isPaused ? (
            <>
              <img src={resumeBtnImg} alt="恢复通话" style={{ width: '28px', height: '28px' }} />
              <span className="btn-label">恢复</span>
            </>
          ) : (
            <>
              <img src={pauseBtnImg} alt="暂停通话" style={{ width: '28px', height: '28px' }} />
              <span className="btn-label">暂停</span>
            </>
          )}
        </button>

        {/* 3. 挂断按钮 */}
        <button
          className="voice-call-btn voice-call-btn-hangup"
          onClick={handleHangup}
          disabled={callState === "idle"}
          title="挂断通话"
        >
          <img src={hangupBtnImg} alt="挂断通话" style={{ width: '28px', height: '28px' }} />
          <span className="btn-label">挂断</span>
        </button>

        {/* 4. 发送语音消息按钮（仅在暂停时可用）*/}
        <button
          className="voice-call-btn voice-call-btn-send"
          onClick={handleSendVoiceMessage}
          disabled={callState !== "paused" || !isPaused || !isConnected}
          title="发送语音消息（非实时）"
        >
          <img src={microphoneBtnImg} alt="发送语音消息" style={{ width: '28px', height: '28px' }} />
          <span className="btn-label">语音消息</span>
        </button>
      </div>
    </div>
  );
}