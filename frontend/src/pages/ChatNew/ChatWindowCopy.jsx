import PropTypes from "prop-types";
import { useCallback, useEffect, useState } from "react";
import CallControls from "../../components/chat/CallControls.jsx";
import MessageList from "../../components/chat/MessageList.jsx";
import MessageComposer from "../../components/chat/MessageComposer.jsx";
import VideoDisplay from "../../components/VideoDisplay.jsx";
import { useWebRTC } from "../../hooks/useWebRTC.js";
import "./styles/index.css";

export default function ChatWindow({
  thread,
  messages,
  loading,
  onSend,
  callStatus,
  onCallAction,
  emotionData,
  onEmotionUpdate,
  handleHangup
}) {
  const [localStream, setLocalStream] = useState(null);
  const [remoteStream, setRemoteStream] = useState(null);
  const [emotionState, setEmotionState] = useState(emotionData);
  const [emotionDetectionStream, setEmotionDetectionStream] = useState(null); // 用于情绪检测的视频流
  const [emotionDetectionEnabled, setEmotionDetectionEnabled] = useState(true); // 控制情绪检测视频的开关状态
  const [cameraError, setCameraError] = useState(null); // 摄像头错误状态
  const [isHangingUp, setIsHangingUp] = useState(false);
  
  // 使用WebRTC hook获取视频流
  const {
    startCall,
    stopCall,
    connectionState,
    isConnecting,
    remoteAudioRef,
  } = useWebRTC(
    null, // roomId将在handleCallAction中设置
    (remoteStream, streamType) => {
      console.log("Remote stream received", streamType || "audio", remoteStream);
      if (streamType === 'video') {
        // 处理视频流
        setRemoteStream(remoteStream);
      } else {
        // 处理音频流
        if (remoteAudioRef.current) {
          remoteAudioRef.current.srcObject = remoteStream;
          remoteAudioRef.current.play().catch((err) => {
            console.error("Failed to play remote audio:", err);
          });
        }
      }
    },
    (error) => {
      console.error("WebRTC error:", error);
    }
  );

  const [roomId, setRoomId] = useState(null);

  // 初始化情绪检测视频流
  useEffect(() => {
    // 只在没有视频通话时获取情绪检测的视频流
    if (!callStatus || callStatus.mode !== "video") {
      // 检查浏览器是否支持getUserMedia
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        console.error("Browser does not support getUserMedia");
        setCameraError("浏览器不支持摄像头访问");
        return;
      }
      
      // 检查当前页面是否通过HTTPS访问
      const isSecureContext = window.isSecureContext || location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
      if (!isSecureContext) {
        console.error("Camera access requires secure context (HTTPS)");
        setCameraError("摄像头访问需要安全连接(HTTPS)，请使用https://localhost或部署到HTTPS服务器");
        return;
      }
      
      navigator.mediaDevices.getUserMedia({ video: true, audio: false })
        .then(stream => {
          setEmotionDetectionStream(stream);
          setCameraError(null); // 清除之前的错误
          console.log("Emotion detection stream initialized");
        })
        .catch(err => {
          console.error("Error accessing camera for emotion detection:", err);
          // 添加用户友好的错误提示
          let errorMessage = "无法访问摄像头";
          if (err.name === 'NotAllowedError') {
            errorMessage = "摄像头权限被拒绝，请在浏览器设置中允许访问摄像头";
          } else if (err.name === 'NotFoundError') {
            errorMessage = "未找到摄像头设备";
          } else if (err.name === 'NotReadableError') {
            errorMessage = "摄像头已被其他应用程序占用";
          } else if (err.name === 'OverconstrainedError') {
            errorMessage = "摄像头不满足要求";
          } else if (err.name === 'SecurityError') {
            errorMessage = "安全限制阻止访问摄像头，可能需要HTTPS连接";
          }
          setCameraError(errorMessage);
        });
    }
    
    return () => {
      // 组件卸载时释放情绪检测视频流
      if (emotionDetectionStream) {
        emotionDetectionStream.getTracks().forEach(track => track.stop());
      }
    };
  }, [callStatus]);

  // 清理函数
  useEffect(() => {
    return () => {
      if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
      }
      if (remoteStream) {
        remoteStream.getTracks().forEach(track => track.stop());
      }
      // 确保在组件卸载时清理所有流
      if (emotionDetectionStream) {
        emotionDetectionStream.getTracks().forEach(track => track.stop());
      }
    };
  }, [localStream, remoteStream, emotionDetectionStream]);

  // 处理通话操作
  const handleCallAction = useCallback(async (mode) => {
    if (!thread) {
      onCallAction({ mode, message: "请选择会话后再发起通话" });
      return;
    }

    const newRoomId = `${thread.thread_id}-${mode}`;

    // 如果已有通话，先停止
    if (callStatus && callStatus.mode === mode) {
      stopCall();
      setLocalStream(null);
      setRemoteStream(null);
      setRoomId(null);
      onCallAction(null);
      
      // 重新初始化情绪检测视频流
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        // 检查当前页面是否通过HTTPS访问
        const isSecureContext = window.isSecureContext || location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
        if (!isSecureContext) {
          setCameraError("摄像头访问需要安全连接(HTTPS)，请使用https://localhost或部署到HTTPS服务器");
          return;
        }
        
        navigator.mediaDevices.getUserMedia({ video: true, audio: false })
          .then(stream => {
            setEmotionDetectionStream(stream);
            setCameraError(null); // 清除之前的错误
          })
          .catch(err => {
            console.error("Error accessing camera for emotion detection:", err);
            let errorMessage = "无法访问摄像头";
            if (err.name === 'NotAllowedError') {
              errorMessage = "摄像头权限被拒绝，请在浏览器设置中允许访问摄像头";
            } else if (err.name === 'NotFoundError') {
              errorMessage = "未找到摄像头设备";
            } else if (err.name === 'NotReadableError') {
              errorMessage = "摄像头已被其他应用程序占用";
            } else if (err.name === 'OverconstrainedError') {
              errorMessage = "摄像头不满足要求";
            } else if (err.name === 'SecurityError') {
              errorMessage = "安全限制阻止访问摄像头，可能需要HTTPS连接";
            }
            setCameraError(errorMessage);
          });
      } else {
        setCameraError("浏览器不支持摄像头访问");
      }
      
      return;
    }

    // 启动新通话
    onCallAction({ mode, message: "正在建立连接…" });

    try {
      // 检查浏览器是否支持getUserMedia
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        onCallAction({ mode, message: "浏览器不支持摄像头访问" });
        return;
      }
      
      // 检查当前页面是否通过HTTPS访问
      const isSecureContext = window.isSecureContext || location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
      if (!isSecureContext && mode === "video") {
        onCallAction({ mode, message: "视频通话需要安全连接(HTTPS)，请使用https://localhost或部署到HTTPS服务器" });
        return;
      }
      
      // 获取本地流
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: mode === "video",
      });
      setLocalStream(stream);
      setRoomId(newRoomId);

      // 如果是视频通话，将本地流也设置为情绪检测流
      if (mode === "video") {
        setEmotionDetectionStream(stream);
        setCameraError(null); // 清除之前的摄像头错误
      }

      // 启动WebRTC通话
      await startCall({ roomId: newRoomId, mode });
      onCallAction({ mode, message: "通话已建立" });
    } catch (error) {
      console.error("Failed to start call", error);
      let errorMessage = "连接失败，请重试";
      if (error.name === 'NotAllowedError') {
        errorMessage = "摄像头/麦克风权限被拒绝，请在浏览器设置中允许访问";
      } else if (error.name === 'NotFoundError') {
        errorMessage = "未找到摄像头或麦克风设备";
      } else if (error.name === 'NotReadableError') {
        errorMessage = "摄像头或麦克风已被其他应用程序占用";
      } else if (error.name === 'OverconstrainedError') {
        errorMessage = "设备不满足要求";
      } else if (error.name === 'SecurityError') {
        errorMessage = "安全限制阻止访问设备，可能需要HTTPS连接";
      }
      
      onCallAction({ mode, message: errorMessage });
      setLocalStream(null);
      setRoomId(null);
    }
  }, [thread, callStatus, onCallAction, startCall, stopCall]);

  // 处理情绪检测结果
  const handleEmotionDetected = useCallback((emotionData) => {
    // 更新本地情绪状态
    setEmotionState(emotionData);
    
    // 调用父组件的情绪更新回调
    if (onEmotionUpdate) {
      // 确保传递正确的数据类型
      onEmotionUpdate({
        ...emotionData,
        type: 'face_emotion'
      });
    }
    
    // 根据数据类型进行不同处理
    if (emotionData.type === 'face_emotion') {
      console.log('面部情绪检测结果:', emotionData);
      // 这里可以添加面部情绪检测特有的处理逻辑
    } else if (emotionData.type === 'eeg_waveform') {
      console.log('脑电波形数据:', emotionData);
      // 这里可以添加脑电波形数据特有的处理逻辑
    }
  }, [onEmotionUpdate]);

  // 切换情绪检测视频的开关状态
  const toggleEmotionDetection = useCallback(() => {
    setEmotionDetectionEnabled(prev => !prev);
    setCameraError(null); // 重置错误状态
    
    // 如果关闭情绪检测，释放视频流
    if (emotionDetectionEnabled && emotionDetectionStream) {
      emotionDetectionStream.getTracks().forEach(track => track.stop());
      setEmotionDetectionStream(null);
    } 
    // 如果开启情绪检测且没有视频流，则获取新的视频流
    else if (!emotionDetectionEnabled && (!callStatus || callStatus.mode !== "video")) {
      // 检查浏览器是否支持getUserMedia
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setCameraError("浏览器不支持摄像头访问");
        return;
      }
      
      // 检查当前页面是否通过HTTPS访问
      const isSecureContext = window.isSecureContext || location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
      if (!isSecureContext) {
        setCameraError("摄像头访问需要安全连接(HTTPS)，请使用https://localhost或部署到HTTPS服务器");
        return;
      }
      
      navigator.mediaDevices.getUserMedia({ video: true, audio: false })
        .then(stream => {
          setEmotionDetectionStream(stream);
          console.log("Emotion detection stream re-initialized");
        })
        .catch(err => {
          console.error("Error accessing camera for emotion detection:", err);
          // 添加用户友好的错误提示
          let errorMessage = "无法访问摄像头";
          if (err.name === 'NotAllowedError') {
            errorMessage = "摄像头权限被拒绝，请在浏览器设置中允许访问摄像头";
          } else if (err.name === 'NotFoundError') {
            errorMessage = "未找到摄像头设备";
          } else if (err.name === 'NotReadableError') {
            errorMessage = "摄像头已被其他应用程序占用";
          } else if (err.name === 'OverconstrainedError') {
            errorMessage = "摄像头不满足要求";
          } else if (err.name === 'SecurityError') {
            errorMessage = "安全限制阻止访问摄像头，可能需要HTTPS连接";
          }
          setCameraError(errorMessage);
        });
    }
    setIsHangingUp(true);
    handleHangup();
  }, [emotionDetectionEnabled, emotionDetectionStream, callStatus]);

  if (!thread) {
    return <div className="chat-window__placeholder">请选择或创建一个会话。</div>;
  }

  return (
    <div style={{ height: '100%' }}>
      {/* 情绪检测视频区域 - 仅在非视频通话时显示 */}
      {(!callStatus || callStatus.mode !== "video") && (
        <div style={{ 
          height: '100%', 
          position: 'relative',
          isolation: 'isolate' /* 创建新的堆叠上下文 */
        }}>  
          {/* <div className="emotion-detection-header">
            <h3>情绪检测</h3>
            <button
              type="button"
              className={`emotion-toggle-btn ${emotionDetectionEnabled ? 'emotion-toggle-btn--on' : 'emotion-toggle-btn--off'}`}
              onClick={toggleEmotionDetection}
            >
              {emotionDetectionEnabled ? '关闭' : '开启'}
            </button>
          </div> */}
          
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
          <button 
            className={`chatnew-hangup-btn${isHangingUp ? ' is-hanging-up' : ''}`}
            aria-label="挂断"
            onClick={toggleEmotionDetection}
          >
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M19 6.41L17.59 5L12 10.59L6.41 5L5 6.41L10.59 12L5 17.59L6.41 19L12 13.41L17.59 19L19 17.59L13.41 12L19 6.41Z" fill="white"/>
            </svg>
          </button>
          
          {emotionDetectionEnabled && !emotionDetectionStream && !cameraError && (
            <div className="emotion-detection-loading">
              正在初始化摄像头...
            </div>
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
      )}
      
      {/* 视频通话区域 - 仅在视频通话时显示 */}
      {/*{callStatus && callStatus.mode === "video" && (*/}
      {/*  <div className="video-container">*/}
      {/*    <div className="video-grid">*/}
      {/*      <div className="video-item">*/}
      {/*        <h3>你</h3>*/}
      {/*        <VideoDisplay */}
      {/*          stream={localStream} */}
      {/*          emotionData={emotionState} */}
      {/*          isActive={true}*/}
      {/*          roomId={roomId}*/}
      {/*          onEmotionDetected={handleEmotionDetected}*/}
      {/*        />*/}
      {/*      </div>*/}
      {/*      <div className="video-item">*/}
      {/*        <h3>对方</h3>*/}
      {/*        <VideoDisplay */}
      {/*          stream={remoteStream} */}
      {/*          emotionData={null} */}
      {/*          isActive={true}*/}
      {/*        />*/}
      {/*      </div>*/}
      {/*    </div>*/}
      {/*  </div>*/}
      {/*)}*/}
      
      {/*<MessageList messages={messages} loading={loading} />*/}
      {/*<MessageComposer onSend={onSend} disabled={!thread} />*/}
    </div>
  );
}

ChatWindow.propTypes = {
  thread: PropTypes.shape({
    thread_id: PropTypes.string,
    title: PropTypes.string,
    participants: PropTypes.arrayOf(PropTypes.string),
  }),
  messages: PropTypes.arrayOf(PropTypes.object).isRequired,
  loading: PropTypes.bool,
  onSend: PropTypes.func.isRequired,
  callStatus: PropTypes.shape({
    mode: PropTypes.string,
    message: PropTypes.string,
  }),
  onCallAction: PropTypes.func.isRequired,
  onEmotionUpdate: PropTypes.func,
  emotionData: PropTypes.shape({
    label: PropTypes.string,
    confidence: PropTypes.number,
    face_position: PropTypes.arrayOf(
      PropTypes.shape({
        x: PropTypes.number,
        y: PropTypes.number,
        width: PropTypes.number,
        height: PropTypes.number
      })
    )
  }),
};

