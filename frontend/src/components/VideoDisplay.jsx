import React, { useEffect, useRef, useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import './VideoDisplay.css';
import eegEventBus from '../utils/eegEventBus';

// 获取当前API地址前缀
const getApiPrefix = () => {
  // 如果通过 IP 访问页面,则使用该 IP 作为 API 地址
  const hostname = window.location.hostname;
  if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
    return `http://${hostname}:8000`;
  }
  // 默认使用 localhost (仅用于开发)
  return "http://localhost:8000";
};

export default function VideoDisplay({ stream, emotionData, isActive, roomId, onEmotionDetected, emotionDetectionEnabled = true }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [videoDimensions, setVideoDimensions] = useState({ width: 640, height: 480 });
  const animationFrameRef = useRef(null);
  const emotionDetectionIntervalRef = useRef(null);
  const lastEmotionDetectionRef = useRef(0);

  // Set up video stream when component mounts or stream changes
  useEffect(() => {
    if (videoRef.current && stream) {
      try {
        videoRef.current.srcObject = stream;
        console.log("Video stream set to video element:", stream.id);
        
        // Add event listeners to debug video loading
        videoRef.current.onloadedmetadata = () => {
          console.log("Video metadata loaded, playing video");
          // 确保视频播放
          const playPromise = videoRef.current.play();
          if (playPromise !== undefined) {
            playPromise.catch(err => {
              console.error("Error playing video:", err);
              // 尝试手动播放
              videoRef.current.play().catch(e => console.error("Manual play failed:", e));
            });
          }
        };
        
        videoRef.current.onerror = (err) => {
          console.error("Video error:", err);
        };
      } catch (error) {
        console.error("Error setting video stream:", error);
      }
    } else if (videoRef.current && !stream) {
      // Clear video stream when stream is null
      videoRef.current.srcObject = null;
    }
  }, [stream]);

  // Set up canvas for emotion detection overlay
  useEffect(() => {
    if (!canvasRef.current || !videoRef.current) return;
    
    const canvas = canvasRef.current;
    const video = videoRef.current;
    
    // Set canvas size to match video dimensions
    const updateCanvasSize = () => {
      if (video.videoWidth && video.videoHeight) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        console.log(`Canvas size set to ${canvas.width}x${canvas.height}`);
      }
    };
    
    // Update canvas size when video metadata is loaded
    video.addEventListener('loadedmetadata', updateCanvasSize);
    
    // Initial canvas size
    updateCanvasSize();
    
    return () => {
      video.removeEventListener('loadedmetadata', updateCanvasSize);
    };
  }, []);

  // 获取视频尺寸
  const handleVideoLoadedMetadata = () => {
    if (videoRef.current) {
      setVideoDimensions({
        width: videoRef.current.videoWidth,
        height: videoRef.current.videoHeight
      });
    }
  };

  // 捕获视频帧并发送到后端进行情绪检测
  const captureAndDetectEmotion = useCallback(async () => {
    if (!videoRef.current || !isActive) return;
    
    // 移除频率限制，实现连续检测
    const now = Date.now();
    // 注释掉原来的频率限制
    // if (now - lastEmotionDetectionRef.current < 3000) return;
    lastEmotionDetectionRef.current = now;
    
    try {
      // 创建临时canvas来捕获视频帧
      const tempCanvas = document.createElement('canvas');
      tempCanvas.width = videoRef.current.videoWidth;
      tempCanvas.height = videoRef.current.videoHeight;
      const tempCtx = tempCanvas.getContext('2d');
      tempCtx.drawImage(videoRef.current, 0, 0, tempCanvas.width, tempCanvas.height);
      
      // 将canvas转换为blob
      tempCanvas.toBlob(async (blob) => {
        if (!blob) return;
        
        // 创建FormData并发送到后端
        const formData = new FormData();
        formData.append('frame', blob, 'frame.jpg');
        // 使用roomId或者默认值
        const roomIdToUse = roomId || 'emotion-detection';
        formData.append('room_id', roomIdToUse);
        
        console.log('Sending emotion detection request to backend with roomId:', roomIdToUse);
        
        try {
          const apiPrefix = getApiPrefix();
          const response = await fetch(`${apiPrefix}/video/emotion`, {
            method: 'POST',
            body: formData
          });
          
          if (response.ok) {
            const result = await response.json();
            console.log('Emotion detection result:', result);
            
            // 确保face_position数据存在
            if (!result.face_position || result.face_position.length === 0) {
              // 如果没有人脸位置数据，创建默认位置
              // 使用视频原始尺寸的比例，而不是画布尺寸
              const videoWidth = videoRef.current.videoWidth;
              const videoHeight = videoRef.current.videoHeight;
              result.face_position = [{
                x: videoWidth * 0.3,
                y: videoHeight * 0.2,
                width: videoWidth * 0.4,
                height: videoHeight * 0.5,
                isDefault: true  // 添加标记表示这是默认位置
              }];
              console.log('Created default face position based on video dimensions:', result.face_position[0]);
            }
            
            // 通知父组件有新的情绪检测结果
            if (onEmotionDetected) {
              onEmotionDetected({
                ...result,
                type: 'face_emotion'
              });
            }
          } else {
            console.error('Emotion detection API error:', response.status, response.statusText);
          }
        } catch (error) {
          console.error('Error detecting emotion:', error);
        }
      }, 'image/jpeg', 0.8);
    } catch (error) {
      console.error('Error capturing frame:', error);
    }
  }, [isActive, roomId, onEmotionDetected]);

  // 获取情绪对应的脑电波形数据
  const fetchEEGWaveform = useCallback(async (emotion) => {
    if (!emotion) return;
    
    try {
      const apiPrefix = getApiPrefix();
      const response = await fetch(`${apiPrefix}/eeg/waveform/${emotion}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const waveformData = await response.json();
        console.log('EEG waveform data:', waveformData);
        
        // 通知父组件有新的脑电波形数据
        if (onEmotionDetected) {
          onEmotionDetected({
            emotion: emotion,
            waveform: waveformData,
            type: 'eeg_waveform'
          });
        }
        
        // 将脑电波数据缓存到事件总线，延长显示时间
        eegEventBus.cacheWaveformData({
          emotion: emotion,
          waveform: waveformData,
          type: 'eeg_waveform'
        }, 15000); // 显示15秒
      }
    } catch (error) {
      console.error('Error fetching EEG waveform:', error);
    }
  }, [onEmotionDetected]);

  // 启动或停止情绪检测
  useEffect(() => {
    if (isActive && stream && emotionDetectionEnabled) {
      console.log('Starting emotion detection with stream:', stream.id);
      // 立即执行一次检测
      captureAndDetectEmotion();
      
      // 设置定时检测，每1秒一次
      emotionDetectionIntervalRef.current = setInterval(captureAndDetectEmotion, 500);
      console.log('Emotion detection interval set to 1 second');
    } else {
      // 清除定时器
      if (emotionDetectionIntervalRef.current) {
        clearInterval(emotionDetectionIntervalRef.current);
        emotionDetectionIntervalRef.current = null;
        console.log('Emotion detection interval cleared');
      }
    }
    
    return () => {
      if (emotionDetectionIntervalRef.current) {
        clearInterval(emotionDetectionIntervalRef.current);
      }
    };
  }, [isActive, stream, emotionDetectionEnabled, captureAndDetectEmotion]);

  // 当检测到面部情绪时，获取对应的脑电波形数据
  useEffect(() => {
    if (emotionData && emotionData.type === 'face_emotion' && emotionData.emotion) {
      console.log('Detected face emotion, fetching EEG waveform:', emotionData.emotion);
      // 获取脑电波形数据
      fetchEEGWaveform(emotionData.emotion);
    }
  }, [emotionData, fetchEEGWaveform]);

  // 绘制人脸检测框和情绪标签
  const drawFaceDetection = useCallback(() => {
    if (!canvasRef.current || !videoRef.current) return;
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    // 清除画布
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // 只有在有有效的情绪数据且人脸位置数据有效时才绘制
    if (emotionData && 
        emotionData.face_position && 
        emotionData.face_position.length > 0 &&
        emotionData.emotion && 
        emotionData.confidence > 0.3 &&  // 只有置信度大于30%时才绘制
        !emotionData.face_position[0].isDefault) {  // 不绘制默认人脸位置
      
      const facePos = emotionData.face_position[0];
      
      // 检查人脸位置是否有效（不是默认值或异常值）
      const video = videoRef.current;
      const videoWidth = video.videoWidth;
      const videoHeight = video.videoHeight;
      
      // 计算人脸框面积比例，如果面积超过视频面积的70%，认为是无效数据
      const faceAreaRatio = (facePos.width * facePos.height) / (videoWidth * videoHeight);
      
      if (faceAreaRatio > 0.7) {
        console.log('Face box too large, skipping drawing:', faceAreaRatio);
        // 继续下一帧但不绘制
        animationFrameRef.current = requestAnimationFrame(drawFaceDetection);
        return;
      }
      
      console.log('Drawing face detection with facePos:', facePos);
      console.log('Video dimensions:', videoWidth, 'x', videoHeight);
      console.log('Canvas dimensions:', canvas.width, 'x', canvas.height);
      
      // 获取视频元素的实际显示尺寸和位置
      const videoRect = video.getBoundingClientRect();
      const canvasRect = canvas.getBoundingClientRect();
      
      // 计算视频在画布中的实际显示区域
      // 由于使用了object-fit: 'cover'，视频可能会被裁剪以填充整个容器
      const videoAspectRatio = videoWidth / videoHeight;
      const containerAspectRatio = videoRect.width / videoRect.height;
      
      let actualVideoWidth, actualVideoHeight, offsetX, offsetY;
      
      if (videoAspectRatio > containerAspectRatio) {
        // 视频更宽，高度会填满容器，宽度会被裁剪
        actualVideoHeight = videoRect.height;
        actualVideoWidth = actualVideoHeight * videoAspectRatio;
        offsetX = (videoRect.width - actualVideoWidth) / 2;
        offsetY = 0;
      } else {
        // 视频更高，宽度会填满容器，高度会被裁剪
        actualVideoWidth = videoRect.width;
        actualVideoHeight = actualVideoWidth / videoAspectRatio;
        offsetX = 0;
        offsetY = (videoRect.height - actualVideoHeight) / 2;
      }
      
      // 计算缩放比例
      const scaleX = actualVideoWidth / videoWidth;
      const scaleY = actualVideoHeight / videoHeight;
      
      // 转换人脸坐标到画布坐标系
      const x = facePos.x * scaleX + offsetX;
      const y = facePos.y * scaleY + offsetY;
      const width = facePos.width * scaleX;
      const height = facePos.height * scaleY;
      
      console.log('Transformed face box:', x, ',', y, ',', width, ',', height);
      
      // 绘制人脸框
      ctx.strokeStyle = '#00ff00';
      ctx.lineWidth = 3;
      ctx.strokeRect(x, y, width, height);
      
      // 绘制情绪标签背景
      const emotion = emotionData.emotion || 'unknown';
      const confidence = emotionData.confidence || 0;
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
      ctx.fillRect(x, y - 30, 150, 30);
      
      // 绘制情绪标签文本
      ctx.fillStyle = '#ffffff';
      ctx.font = '16px Arial';
      ctx.fillText(`${emotion} (${(confidence * 100).toFixed(1)}%)`, x + 5, y - 10);
    } else {
      console.log('No valid face position data available or default face position, skipping drawing');
    }
    
    // 继续下一帧
    animationFrameRef.current = requestAnimationFrame(drawFaceDetection);
  }, [emotionData]);

  // 开始或停止绘制人脸框
  useEffect(() => {
    if (isActive && emotionData && canvasRef.current && videoRef.current) {
      // 设置canvas尺寸与视频显示区域一致
      const video = videoRef.current;
      const canvas = canvasRef.current;
      
      // 获取视频实际显示尺寸
      const videoRect = video.getBoundingClientRect();
      canvas.width = videoRect.width;
      canvas.height = videoRect.height;
      
      console.log('Canvas setup for face detection:', canvas.width, 'x', canvas.height);
      console.log('Video client dimensions:', video.clientWidth, 'x', video.clientHeight);
      console.log('Video natural dimensions:', video.videoWidth, 'x', video.videoHeight);
      console.log('Video bounding rect:', videoRect.width, 'x', videoRect.height);
      
      // 绘制人脸框
      drawFaceDetection();
    } else {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (canvasRef.current) {
        const ctx = canvasRef.current.getContext('2d');
        ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
      }
    }
    
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isActive, emotionData, drawFaceDetection]);

  if (!stream) {
    return (
      <div className="video-display-placeholder" style={{ 
        backgroundColor: '#000', 
        color: '#fff', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        height: '200px'
      }}>
        <p>视频未连接</p>
      </div>
    );
  }

  return (
  <div className="video-display-container">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        onLoadedMetadata={handleVideoLoadedMetadata}
        className="video-element"
        style={{ 
          width: '100%', 
          height: '100%',
          backgroundColor: '#000',
          objectFit: 'cover'
        }}
      />
      <canvas
        ref={canvasRef}
        className="video-overlay"
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none'
        }}
      />
       {/* {emotionData && isActive && (
        <div className="emotion-indicator">
          <div className="emotion-label">当前情绪: {emotionData.emotion || emotionData.label}</div>
          <div className="emotion-confidence">
            置信度: {(emotionData.confidence * 100).toFixed(1)}%
          </div>
        </div>
      )}  */}
    </div>
  );
}

VideoDisplay.propTypes = {
  stream: PropTypes.object,
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
  isActive: PropTypes.bool,
  roomId: PropTypes.string,
  onEmotionDetected: PropTypes.func,
  emotionDetectionEnabled: PropTypes.bool
};