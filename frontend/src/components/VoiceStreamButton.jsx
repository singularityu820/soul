import { useEffect, useRef } from "react";
import { useVoiceStream } from "../hooks/useVoiceStream";
import "../styles.css";

/**
 * 实时语音流组件
 * 
 * 低延迟的语音对话,实时处理
 */
export default function VoiceStreamButton({ threadId, disabled }) {
  const {
    isConnected,
    isRecording,
    status,
    transcript,
    response,
    error,
    connect,
    disconnect,
    startRecording,
    stopRecording,
  } = useVoiceStream();
  
  const connectionAttemptedRef = useRef(false);
  const currentThreadIdRef = useRef(null);
  const initializedRef = useRef(false); // 防止 StrictMode 双重连接

  // 自动连接
  useEffect(() => {
    // 防止 StrictMode 重复连接
    if (initializedRef.current) {
      return () => {
        // 空的 cleanup
      };
    }
    
    // 只在 threadId 变化或首次渲染时连接
    if (threadId && !disabled) {
      initializedRef.current = true;
      currentThreadIdRef.current = threadId;
      connectionAttemptedRef.current = true;
      
      connect(threadId).catch((err) => {
        console.error("Failed to connect:", err);
        connectionAttemptedRef.current = false;
      });
    }
    
    return () => {
      // StrictMode 的测试卸载 - 不做任何清理
    };
  }, [threadId, disabled, connect]);

  const handleToggleRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const getStatusText = () => {
    if (!isConnected) return "连接中...";
    if (status === "transcribing") return "识别中...";
    if (status === "generating") return "思考中...";
    if (status === "synthesizing") return "合成中...";
    if (isRecording) return "聆听中...";
    return "就绪";
  };

  const getStatusColor = () => {
    if (!isConnected) return "#f59e0b";
    if (status !== "idle" && status !== "") return "#3b82f6";
    if (isRecording) return "#ef4444";
    return "#10b981";
  };

  return (
    <div className="voice-stream-controls-compact">
      <button
        className={`voice-stream-btn ${isRecording ? "recording" : ""} ${!isConnected ? "disabled" : ""}`}
        onClick={handleToggleRecording}
        disabled={!isConnected || disabled}
        title={isRecording ? "点击停止录音" : "点击开始语音对话"}
      >
        {isRecording ? (
          <>
            <span className="recording-indicator">🔴</span>
            <span>录音中</span>
          </>
        ) : (
          <>
            <span>🎤</span>
            <span>语音</span>
          </>
        )}
      </button>

      <div className="voice-stream-status-compact" style={{ color: getStatusColor() }}>
        <span className="status-dot" style={{ backgroundColor: getStatusColor() }}></span>
        {getStatusText()}
      </div>

      {error && (
        <div className="voice-stream-error-compact">
          ⚠️ {error}
        </div>
      )}
    </div>
  );
}
