import { useEffect, useState } from "react";
import { useQwenRealtime } from "../hooks/useQwenRealtime";
import { setVoiceCallData } from "../utils/voiceCallStore";
import "./VoiceCallControls.css";

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
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M20.01 15.38c-1.23 0-2.42-.2-3.53-.56a.977.977 0 0 0-1.01.24l-1.57 1.97c-2.83-1.35-5.48-3.9-6.89-6.83l1.95-1.66c.27-.28.35-.67.24-1.02-.37-1.11-.56-2.3-.56-3.53 0-.54-.45-.99-.99-.99H4.19C3.65 3 3 3.24 3 3.99 3 13.28 10.73 21 20.01 21c.71 0 .99-.63.99-1.18v-3.45c0-.54-.45-.99-.99-.99z" fill="currentColor"/>
          </svg>
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
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M8 5v14l11-7z" fill="currentColor"/>
              </svg>
                <span className="btn-label">恢复</span>
            </>
          ) : (
            <>
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" fill="currentColor"/>
              </svg>
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
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 9c-1.6 0-3.15.25-4.6.72v3.1c0 .39-.23.74-.56.9-.98.49-1.87 1.12-2.66 1.85-.18.18-.43.28-.7.28-.28 0-.53-.11-.71-.29L.29 13.08a.956.956 0 0 1-.29-.7c0-.28.11-.53.29-.71C3.34 8.78 7.46 7 12 7s8.66 1.78 11.71 4.67c.18.18.29.43.29.71 0 .28-.11.52-.29.7l-2.48 2.48c-.18.18-.43.29-.71.29-.27 0-.52-.11-.7-.28a11.27 11.27 0 0 0-2.67-1.85.996.996 0 0 1-.56-.9v-3.1C15.15 9.25 13.6 9 12 9z" fill="currentColor"/>
          </svg>
          <span className="btn-label">挂断</span>
        </button>

        {/* 4. 发送语音消息按钮（仅在暂停时可用）*/}
        <button
          className="voice-call-btn voice-call-btn-send"
          onClick={handleSendVoiceMessage}
          disabled={callState !== "paused" || !isPaused || !isConnected}
          title="发送语音消息（非实时）"
        >
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" fill="currentColor"/>
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" fill="currentColor"/>
          </svg>
          <span className="btn-label">语音消息</span>
        </button>
      </div>
    </div>
  );
}
