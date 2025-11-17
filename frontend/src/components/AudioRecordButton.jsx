import { useEffect, useState } from "react";
import { useAudioRecorder } from "../hooks/useAudioRecorder";
import "../styles.css";
import testAudio from "./test.wav"; // 导入音频文件

/**
 * 录音按钮组件 - 支持模拟对话模式
 * 
 * 替代 WebRTC 的简单音频录制方案
 */
export default function AudioRecordButton({ threadId, onResponse, disabled, addSelfMessage, addAiMessage, simulateMode = true }) {
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
  const [messageIndex, setMessageIndex] = useState(0);

  // 预设的模拟对话内容
  const simulatedConversations = [
    {
      user: "今天好累，但也特别开心，因为项目终于完成啦",
      ai: "忙了这么久，终于可以松一口气呀，你为这个项目付出的努力，我都记着呢。现在你该放松放松了，放下手机去感受自己的本心。让自己开心起来",
      audioFile: testAudio // 使用导入的音频文件
    },
    {
      user: "最近总是失眠，晚上翻来覆去睡不着",
      ai: "失眠确实让人很困扰。你有没有尝试过睡前做一些放松的活动？比如听一些轻音乐或者冥想。我建议你试试深呼吸练习，这有助于放松身心，更容易入睡。",
      audioFile: testAudio // 使用导入的音频文件
    },
    {
      user: "今天和朋友吵架了，心情很糟糕",
      ai: "和朋友吵架确实会影响心情。也许你们都需要一些时间冷静一下。等情绪平复后，可以试着和朋友坦诚地沟通，表达你的感受。真正的友谊是能够经受住这些考验的。",
      audioFile: testAudio // 使用导入的音频文件
    }
  ];

  // 格式化时长
  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // 处理模拟对话
  const handleSimulatedConversation = () => {
    if (disabled || isProcessing) return;

    const currentConversation = simulatedConversations[messageIndex % simulatedConversations.length];
    
    // 添加用户消息
    addSelfMessage(currentConversation.user);
    setTranscript(currentConversation.user);
    
    // 延迟添加AI回复，模拟处理时间
    setTimeout(() => {
      addAiMessage(currentConversation.ai);
      setResponseText(currentConversation.ai);
      
      // 播放AI回复的音频
      if (currentConversation.audioFile) {
        const audio = new Audio(currentConversation.audioFile);
        audio.play().catch((err) => {
          console.error("Failed to play simulated audio:", err);
        });
      }
      
      // 更新消息索引
      setMessageIndex(prev => prev + 1);
      
      // 回调通知父组件
      if (onResponse) {
        onResponse({
          transcript: currentConversation.user,
          response_text: currentConversation.ai,
          simulated: true,
          audio_file: currentConversation.audioFile
        });
      }
    }, 1000); // 1秒延迟，模拟处理时间
  };

  // 处理录音/上传
  const handleClick = async () => {
    if (simulateMode) {
      // 模拟对话模式
      handleSimulatedConversation();
      return;
    }

    // 原有的录音逻辑
    if (disabled || isProcessing) return;

    try {
      const result = await recordAndUpload(threadId);
      console.log("Record and upload result:", result);
      
      
      if (result) {
        // 处理响应
        setTranscript(result.transcript);
        setResponseText(result.response_text);

        addSelfMessage(result.transcript);
        addAiMessage(result.response_text);
        
        // 播放响应音频
        if (result.audio_reference) {
          // 如果是 URL,直接使用
          if (result.audio_reference.startsWith("http")) {
            setResponseAudio(result.audio_reference);
          } else {
            // 如果是本地引用,通过下载接口获取
            const audioUrl = `http://localhost:8000/audio/download?reference=${encodeURIComponent(result.audio_reference)}`;
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
      // 检查是否是占位符URL
      if (responseAudio.startsWith("sandbox://") || 
          responseAudio.startsWith("empty://") || 
          responseAudio.startsWith("error://") || 
          responseAudio.startsWith("missing-key://")) {
        console.log("Skipping playback for placeholder audio URL:", responseAudio);
        return;
      }
      
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
        disabled={(!simulateMode && disabled) || isProcessing}
        title={simulateMode ? "点击模拟对话" : (isRecording ? "点击停止录音并发送" : "点击开始录音")}
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
            <span>{simulateMode ? "💬" : "🎤"}</span>
            <span>{simulateMode ? "对话" : "按住说话"}</span>
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

      {/* {transcript && (
        <div className="audio-transcript">
          <strong>你说:</strong> {transcript}
        </div>
      )}

      {responseText && (
        <div className="audio-response">
          <strong>AI:</strong> {responseText}
        </div>
      )} */}
    </div>
  );
}
