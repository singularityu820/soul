import { useEffect, useState } from "react";
import { useAudioRecorder } from "../hooks/useAudioRecorder";
import "../styles.css";

/**
 * 录音按钮组件
 * 
 * 替代 WebRTC 的简单音频录制方案
 */
export default function AudioRecordButton({ threadId, onResponse, disabled }) {
  const {
    isRecording,
    isProcessing,
    duration,
    error,
    recordAndUpload,
    cancelRecording,
  } = useAudioRecorder();

  const [responseAudio, setResponseAudio] = useState(null);
  const [transcript, setTranscript] = useState("");
  const [responseText, setResponseText] = useState("");

  // 格式化时长
  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // 处理录音/上传
  const handleClick = async () => {
    if (disabled || isProcessing) return;

    try {
      const result = await recordAndUpload(threadId);
      
      if (result) {
        // 处理响应
        setTranscript(result.transcript);
        setResponseText(result.response_text);
        
        // 播放响应音频
        if (result.audio_reference) {
          // 如果是 URL,直接使用
          if (result.audio_reference.startsWith("http")) {
            setResponseAudio(result.audio_reference);
          } else {
            // 如果是本地引用,通过下载接口获取
            const audioUrl = `/api/audio/download?reference=${encodeURIComponent(result.audio_reference)}`;
            setResponseAudio(audioUrl);
          }
        }

        // 回调通知父组件
        if (onResponse) {
          onResponse(result);
        }
      }
    } catch (err) {
      console.error("Record and upload failed:", err);
    }
  };

  // 自动播放响应音频
  useEffect(() => {
    if (responseAudio) {
      const audio = new Audio(responseAudio);
      audio.play().catch((err) => {
        console.error("Failed to play response audio:", err);
      });
    }
  }, [responseAudio]);

  return (
    <div className="audio-record-container">
      <button
        className={`audio-record-btn ${isRecording ? "recording" : ""} ${isProcessing ? "processing" : ""}`}
        onClick={handleClick}
        disabled={disabled || isProcessing}
        title={isRecording ? "点击停止录音并发送" : "点击开始录音"}
      >
        {isProcessing ? (
          <>
            <span className="spinner">⏳</span>
            <span>处理中...</span>
          </>
        ) : isRecording ? (
          <>
            <span className="recording-indicator">🔴</span>
            <span>{formatDuration(duration)}</span>
          </>
        ) : (
          <>
            <span>🎤</span>
            <span>按住说话</span>
          </>
        )}
      </button>

      {isRecording && (
        <button
          className="audio-cancel-btn"
          onClick={cancelRecording}
          title="取消录音"
        >
          ✕
        </button>
      )}

      {error && <div className="audio-error">{error}</div>}

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
