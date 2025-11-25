import PropTypes from "prop-types";
import { useCallback, useEffect, useRef, useState } from "react";
import MessageComposer from "./MessageComposer.jsx";
import VideoDisplay from "../VideoDisplay.jsx";

export default function ChatWindow({
  thread,
  onSend,
  emotionData,
  onEmotionUpdate,
}) {
  const [emotionState, setEmotionState] = useState(emotionData);
  const [emotionDetectionEnabled, setEmotionDetectionEnabled] = useState(true);
  const [emotionDetectionStream, setEmotionDetectionStream] = useState(null);
  const [cameraError, setCameraError] = useState(null);
  const streamRef = useRef(null);

  // 注册全局控制接口，允许页面外部停止/查询流状态
  useEffect(() => {
    // 停止摄像头流（可由外部调用）
    window.__stopEmotionStream = () => {
      try {
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
        }
        setEmotionDetectionStream(null);
        setCameraError(null);
        console.log('[ChatWindow] __stopEmotionStream called - stream stopped');
      } catch (e) {
        console.warn('[ChatWindow] __stopEmotionStream error', e);
      }
    };

    // 只注册，不自动启动
    return () => {
      try {
        if (window.__stopEmotionStream) delete window.__stopEmotionStream;
      } catch (e) {}
    };
  }, []);

  useEffect(() => {
    setEmotionState(emotionData);
  }, [emotionData]);

  useEffect(() => {
    if (!thread) {
      // 无会话时释放资源
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
      setEmotionDetectionStream(null);
      return;
    }

    // 如果页面层面明确禁用了情绪检测（例如在 ChatNew 中隐藏了视频），则不要请求摄像头
    if (window.__EMOTION_DETECTION_DISABLED) {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
      setEmotionDetectionStream(null);
      return;
    }

    if (!emotionDetectionEnabled) {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
      setEmotionDetectionStream(null);
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setCameraError("浏览器不支持摄像头访问");
      setEmotionDetectionStream(null);
      return;
    }

    const isSecureContext =
      window.isSecureContext ||
      location.protocol === "https:" ||
      location.hostname === "localhost" ||
      location.hostname === "127.0.0.1";

    if (!isSecureContext) {
      setCameraError("摄像头访问需要安全连接(HTTPS)，请使用https://localhost或部署到HTTPS服务器");
      setEmotionDetectionStream(null);
      return;
    }

    let cancelled = false;

    navigator.mediaDevices
      .getUserMedia({ video: true, audio: false })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => track.stop());
        }

        streamRef.current = stream;
        setEmotionDetectionStream(stream);
        setCameraError(null);
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }

        const friendlyMessage = (() => {
          if (err.name === "NotAllowedError") {
            return "摄像头权限被拒绝，请在浏览器设置中允许访问摄像头";
          }
          if (err.name === "NotFoundError") {
            return "未找到摄像头设备";
          }
          if (err.name === "NotReadableError") {
            return "摄像头已被其他应用程序占用";
          }
          if (err.name === "OverconstrainedError") {
            return "摄像头不满足要求";
          }
          if (err.name === "SecurityError") {
            return "安全限制阻止访问摄像头，可能需要HTTPS连接";
          }
          return err.message || "无法访问摄像头";
        })();

        setCameraError(friendlyMessage);
        setEmotionDetectionStream(null);
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
        }
      });

    return () => {
      cancelled = true;
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
    };
  }, [thread, emotionDetectionEnabled]);

  const handleEmotionDetected = useCallback(
    (detectedEmotion) => {
      setEmotionState(detectedEmotion);

      if (onEmotionUpdate) {
        onEmotionUpdate({
          ...detectedEmotion,
          type: detectedEmotion?.type || "face_emotion",
        });
      }
    },
    [onEmotionUpdate]
  );

  const toggleEmotionDetection = () => {
    setEmotionDetectionEnabled((prev) => !prev);
    setCameraError(null);
  };

  if (!thread) {
    return <div className="chat-window__placeholder">请选择或创建一个会话。</div>;
  }

  return (
    <div className="chat-window">
      <div className="emotion-detection-container">
        <div className="emotion-detection-header">
          <h3>情绪检测</h3>
          <button
            type="button"
            className={`emotion-toggle-btn ${emotionDetectionEnabled ? "emotion-toggle-btn--on" : "emotion-toggle-btn--off"}`}
            onClick={toggleEmotionDetection}
          >
            {emotionDetectionEnabled ? "关闭" : "开启"}
          </button>
        </div>

        {emotionDetectionEnabled && emotionDetectionStream && (
          <VideoDisplay
            stream={emotionDetectionStream}
            emotionData={emotionState}
            isActive={true}
            roomId={thread.thread_id}
            onEmotionDetected={handleEmotionDetected}
            emotionDetectionEnabled={emotionDetectionEnabled}
          />
        )}

        {emotionDetectionEnabled && !emotionDetectionStream && !cameraError && (
          <div className="emotion-detection-loading">正在初始化摄像头...</div>
        )}

        {cameraError && (
          <div className="emotion-detection-error">
            <strong>摄像头错误：</strong> {cameraError}
            <div className="emotion-detection-error-tips">
              请确保：
              <ul>
                <li>摄像头已连接并正常工作</li>
                <li>浏览器已获得摄像头访问权限</li>
                <li>没有其他应用正在使用摄像头</li>
                <li>如果是HTTPS限制，请尝试在localhost环境下使用</li>
              </ul>
            </div>
          </div>
        )}
      </div>

      {/* 已移除聊天记录渲染：消息由上层统一管理并显示，避免重复 */}
      <div className="chat-window__composer">
        <MessageComposer onSend={onSend} disabled={!thread} />
      </div>
    </div>
  );
}

ChatWindow.propTypes = {
  thread: PropTypes.shape({
    thread_id: PropTypes.string,
    title: PropTypes.string,
    participants: PropTypes.arrayOf(PropTypes.string),
  }),
  onSend: PropTypes.func,
  emotionData: PropTypes.object,
  onEmotionUpdate: PropTypes.func,
};
