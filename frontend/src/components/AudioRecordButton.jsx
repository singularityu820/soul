import { useEffect, useMemo, useRef, useState } from "react";
import { useVoiceStream } from "../hooks/useVoiceStream";
import "../styles.css";

/**
 * 录音按钮组件
 *
 * 默认通过 WebSocket 实时语音管道(useVoiceStream) 与后端交互，
 * 也保留模拟对话模式以便在后台不可用时做演示。
 */
export default function AudioRecordButton({
  threadId,
  onResponse,
  disabled,
  addSelfMessage,
  addAiMessage,
  simulateMode = false,
}) {
  const [transcript, setTranscript] = useState("");
  const [responseText, setResponseText] = useState("");
  const [messageIndex, setMessageIndex] = useState(0);
  const [connectionError, setConnectionError] = useState(null);
  const [autoStreaming, setAutoStreaming] = useState(!simulateMode);
  const lastHandledResponseRef = useRef("");

  const {
    isConnected,
    isRecording,
    status,
    transcript: streamTranscript,
    response: streamResponse,
    error: streamError,
    connect,
    disconnect,
    startRecording,
    stopRecording,
    interrupt,
  } = useVoiceStream();

  // 建立/释放 WebSocket 语音流连接
  useEffect(() => {
    setAutoStreaming(!simulateMode);
  }, [simulateMode]);

  useEffect(() => {
    if (simulateMode || !threadId || disabled || !autoStreaming) {
      stopRecording();
      disconnect();
      return;
    }

    let cancelled = false;

    connect(threadId)
      .then(() => {
        if (!cancelled) {
          setConnectionError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setConnectionError(err.message || "连接失败");
        }
      });

    return () => {
      cancelled = true;
      stopRecording();
      disconnect();
    };
  }, [simulateMode, autoStreaming, threadId, disabled, connect, disconnect, stopRecording]);

  useEffect(() => {
    if (simulateMode || !autoStreaming || disabled) return;
    if (!threadId) return;
    if (!isConnected || isRecording) return;

    startRecording().catch((err) => {
      console.error("Auto start recording failed", err);
      setConnectionError(err.message || "无法开始语音");
    });
  }, [simulateMode, autoStreaming, disabled, threadId, isConnected, isRecording, startRecording]);

  // 实时展示后端推送的结果
  useEffect(() => {
    if (simulateMode) return;
    setTranscript(streamTranscript || "");
  }, [simulateMode, streamTranscript]);

  useEffect(() => {
    if (simulateMode) return;
    setResponseText(streamResponse || "");
  }, [simulateMode, streamResponse]);

  // 语音流完成后追加到聊天面板并触发外部回调
  useEffect(() => {
    if (simulateMode) return;
    if (!streamResponse || streamResponse.trim().length === 0) return;
    if (isRecording) return;
    if (status && status !== "idle") return;

    const snapshot = `${streamTranscript || ""}||${streamResponse}`;
    if (snapshot === lastHandledResponseRef.current) {
      return;
    }
    lastHandledResponseRef.current = snapshot;

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
  }, [simulateMode, streamResponse, streamTranscript, status, isRecording, addAiMessage, addSelfMessage, onResponse]);

  const handleSimulatedConversation = () => {
    if (disabled) return;

    const current = simulatedConversations[messageIndex % simulatedConversations.length];

    addSelfMessage?.(current.user);
    setTranscript(current.user);

    setTimeout(() => {
      addAiMessage?.(current.ai);
      setResponseText(current.ai);
      setMessageIndex((prev) => prev + 1);

      onResponse?.({
        transcript: current.user,
        response_text: current.ai,
        simulated: true,
      });
    }, 1000);
  };

  const getStatusText = () => {
    if (!isConnected) return "连接中...";
    if (status === "transcribing") return "识别中...";
    if (status === "generating") return "思考中...";
    if (status === "synthesizing") return "合成中...";
    if (isRecording) return "聆听中...";
    return "就绪";
  };

  const handleVoiceStreamToggle = async () => {
    if (simulateMode) {
      handleSimulatedConversation();
      return;
    }

    if (disabled || !threadId) {
      return;
    }

    if (autoStreaming) {
      setAutoStreaming(false);
      interrupt();
      stopRecording();
    } else {
      lastHandledResponseRef.current = "";
      setTranscript("");
      setResponseText("");
      setAutoStreaming(true);
    }
  };

  const activeError = simulateMode ? null : streamError || connectionError;
  const isActionDisabled = disabled || (!simulateMode && !threadId);

  return (
    <div className="audio-record-container">
      <button
        className={`audio-record-btn ${isRecording ? "recording" : ""}`}
        onClick={handleVoiceStreamToggle}
        disabled={isActionDisabled}
        title={simulateMode ? "点击模拟对话" : isRecording ? "点击停止录音" : "点击开始语音对话"}
      >
        {simulateMode ? (
          <>
            <span>💬</span>
            <span>对话</span>
          </>
        ) : !isConnected ? (
          <>
            <span className="spinner">⏳</span>
            <span>连接中</span>
          </>
        ) : autoStreaming ? (
          <>
            <span className={isRecording ? "recording-indicator" : ""}>{isRecording ? "🔴" : "🔊"}</span>
            <span>{isRecording ? "实时语音" : "待命"}</span>
          </>
        ) : (
          <>
            <span>▶️</span>
            <span>恢复</span>
          </>
        )}
      </button>

      {!simulateMode && (
        <div className="voice-stream-status-compact" style={{ color: isRecording ? "#ef4444" : "#10b981" }}>
          <span className="status-dot" style={{ backgroundColor: isRecording ? "#ef4444" : "#10b981" }}></span>
          {autoStreaming ? getStatusText() : "已暂停"}
        </div>
      )}

      {activeError && <div className="audio-error">⚠️ {activeError}</div>}

      {transcript && (
        <div className="audio-transcript">
          <strong>你说:</strong> {transcript}
        </div>
      )}

      {responseText && (
        <div className="audio-response">
          <strong>AI:</strong> {responseText}
        </div>
      )}
    </div>
  );
}
