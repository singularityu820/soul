import React, { useState, useEffect } from "react";
import "./styles/index.css";
import Modal from "../../components/ui/Modal.jsx";
import Diary from "./components/Diary";
import LoginModal from "../LoginModal";
import { checkLoginStatus } from "../../auth.js";
import bgVideo from "./styles/img/background.mp4";
import starImg from "./styles/img/star.png";
import moonImg from "./styles/img/moon.png";
import princeTurnVideo from "./styles/img/prince-turn.mp4";
import callGateImg from "./styles/img/call-gate.jpg";
import diaryGateImg from "./styles/img/diary-gate.jpg";

export default function StarPortal() {
  // 状态
  // 星星列表
  const [stars, setStars] = useState([]);
  // 场景状态
  const [sceneStatus, setSceneStatus] = useState(0);
  // 玫瑰状态
  const [roseStatus, setRoseStatus] = useState(0);
  // 玫瑰生长进度
  const [roseGrowthProgress, setRoseGrowthProgress] = useState(0);
  // 当前激活的星星（弹出组件）
  const [activeStarId, setActiveStarId] = useState(null);
  // 弹层开启动画状态
  const [modalOpen, setModalOpen] = useState(false);
  // 登录状态管理 - 不再需要直接管理模态框显示
  // 背景视频是否循环
  const [loopVideo, setLoopVideo] = useState(true);
  // 王子视频引用
  const princeVideoRef = React.useRef(null);
  // 王子视频播放状态：'idle' | 'playing' | 'ended'
  const [princeVideoState, setPrinceVideoState] = useState('idle');
  // 背景视频引用
  const bgVideoRef = React.useRef(null);
  // 王子和月亮是否已放大
  const [isEnlarged, setIsEnlarged] = useState(false);
  // 转场动画状态
  const [isTransitioning, setIsTransitioning] = useState(false);
  // 转场到视频通话的状态
  const [isTransitioningToChat, setIsTransitioningToChat] = useState(false);
  // Canvas 引用，用于去除白色背景
  const canvasRef = React.useRef(null);
  const canvasAnimationRef = React.useRef(null);
  // 存储 Canvas 绘制函数的 ref
  const drawVideoToCanvasRef = React.useRef(null);

  const components = {
    2: <Diary />,
  }

  // 根据星星ID获取对应的图片
  const getStarImage = (starId) => {
    switch (starId) {
      case 1:
        return callGateImg;
      case 2:
        return diaryGateImg;
      default:
        return starImg;
    }
  }

  // 函数
  // 查询星星列表
  const queryStars = async () => {
    // const response = await fetch("/api/stars");
    // const data = await response.json();
    const data = [
      { id: 2, name: "日记" },
      { id: 1, name: "小游戏" },
    ];
    setStars(data);
  };

  // 查询玫瑰生长进度
  const getRoseGrowthProgress = async () => {
    // const response = await fetch("/api/rose-growth-progress");
    // const data = await response.json();
    const data = 0.5;
    setRoseGrowthProgress(data);
  };

  // 初始化
  useEffect(() => {
    queryStars();
    getRoseGrowthProgress();
    
    // 检查登录状态，如果未登录则重定向到登录页面
    const isLoggedIn = checkLoginStatus();
    if (!isLoggedIn) {
      window.navigate("#/login");
    }
    // 移除自动跳转逻辑，让已登录用户也能访问星空首页

    // 检测URL查询参数，自动打开日记模态框
    const urlParams = new URLSearchParams(window.location.search);
    const openParam = urlParams.get('open');
    if (openParam === 'diary') {
      // 延迟执行，确保组件已完全渲染
      setTimeout(() => {
        setActiveStarId(2);
        setModalOpen(true);
        // 清除URL参数，避免刷新页面时再次打开
        window.history.replaceState({}, document.title, window.location.pathname + window.location.hash);
      }, 500);
    }

    // 初始化视频：停留在第一帧
    const video = princeVideoRef.current;
    const canvas = canvasRef.current;

    if (video && canvas) {
      const drawVideoToCanvas = () => {
        if (!video || !canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // 确保 Canvas 尺寸与视频一致
        const videoWidth = video.videoWidth || canvas.clientWidth;
        const videoHeight = video.videoHeight || canvas.clientHeight;

        if (videoWidth > 0 && videoHeight > 0) {
          // 设置 Canvas 内部尺寸
          if (canvas.width !== videoWidth || canvas.height !== videoHeight) {
            canvas.width = videoWidth;
            canvas.height = videoHeight;
          }

          // 清空 Canvas
          ctx.clearRect(0, 0, canvas.width, canvas.height);

          // 绘制视频到 canvas
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

          // 获取图像数据
          const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
          const data = imageData.data;

          // 去除白色背景（使用更精确的算法，避免影响人物）
          // 检测是否为最后一帧（currentTime 接近 duration）
          const isLastFrame = video.duration && Math.abs(video.currentTime - video.duration) < 0.1;

          // 平衡阈值：去除白色背景，同时保护人物区域
          const threshold = isLastFrame ? 227 : 229; // 主要白色阈值（平衡值）
          const edgeThreshold = 207; // 边缘处理阈值（稍微降低以更好去除白边）
          const minBrightness = isLastFrame ? 217 : 219; // 最低亮度阈值
          const maxSaturation = isLastFrame ? 32 : 30; // 最大饱和度阈值（稍微放宽以更好识别白色背景）

          for (let i = 0; i < data.length; i += 4) {
            const r = data[i];
            const g = data[i + 1];
            const b = data[i + 2];
            const a = data[i + 3];

            // 计算亮度（使用标准亮度公式）
            const brightness = (r * 0.299 + g * 0.587 + b * 0.114);
            // 计算平均颜色值
            const avgColor = (r + g + b) / 3;

            // 计算饱和度（用于区分白色背景和人物）
            const max = Math.max(r, g, b);
            const min = Math.min(r, g, b);
            const saturation = max === 0 ? 0 : ((max - min) / max) * 255;

            // 检测是否接近白色：RGB值都高于阈值，亮度高于最小值，且饱和度很低
            const isWhite = r > threshold && g > threshold && b > threshold &&
                           brightness > minBrightness && saturation < maxSaturation;

            // 如果接近白色，设为完全透明
            if (isWhite) {
              data[i + 3] = 0; // alpha = 0 (透明)
            } else if (avgColor > edgeThreshold && saturation < maxSaturation) {
              // 对于边缘区域：必须是高亮度且低饱和度，才进行渐变处理
              // 更激进地去除白色边缘，但对人物区域保持保护
              const normalizedWhiteness = Math.min(1, (avgColor - edgeThreshold) / (threshold - edgeThreshold));

              // 根据颜色值决定处理方式
              if (avgColor > threshold - 5) {
                // 非常接近白色，几乎完全透明
                const opacity = Math.max(0.02, 1 - normalizedWhiteness * 0.98);
                data[i + 3] = Math.floor(a * opacity);
              } else if (avgColor > threshold - 15) {
                // 接近白色区域，激进去除，但保持最低不透明度防止人物透光
                const opacity = Math.max(0.15, 1 - normalizedWhiteness * 0.85);
                data[i + 3] = Math.floor(a * opacity);
              } else {
                // 边缘区域：中等处理，去除白边但保护人物
                const opacity = isLastFrame
                  ? Math.max(0.25, 1 - normalizedWhiteness * 0.75) // 最后一帧：保持25-75%透明度
                  : Math.max(0.3, 1 - normalizedWhiteness * 0.7); // 正常帧：保持30-70%透明度
                data[i + 3] = Math.floor(a * opacity);
              }
            }
            // 对于其他像素（包括有颜色的人物），保持原样
          }

          // 将处理后的数据写回 canvas
          ctx.putImageData(imageData, 0, 0);
        }
      };

      // 存储函数引用，供倒放逻辑使用
      drawVideoToCanvasRef.current = drawVideoToCanvas;

      const initVideo = () => {
        video.currentTime = 0;
        video.pause();
        // 绘制第一帧
        setTimeout(() => drawVideoToCanvas(), 100); // 延迟以确保视频已加载
      };

      const animateCanvas = () => {
        // 确保视频已准备好
        if (video.readyState >= 2) {
          drawVideoToCanvas();
        }
        // 只在播放状态时继续动画
        if (princeVideoState === 'playing') {
          canvasAnimationRef.current = requestAnimationFrame(animateCanvas);
        }
      };

      // 监听视频播放以更新 Canvas
      const handleVideoPlay = () => {
        if (!canvasAnimationRef.current) {
          animateCanvas();
        }
      };

      const handleVideoPause = () => {
        drawVideoToCanvas(); // 绘制当前帧
      };

      // 使用 requestVideoFrameCallback（如果支持）以获得更精确的帧同步
      let videoFrameCallbackId = null;
      const cleanupVideoFrameCallback = () => {
        if (video.cancelVideoFrameCallback && videoFrameCallbackId) {
          video.cancelVideoFrameCallback(videoFrameCallbackId);
          videoFrameCallbackId = null;
        }
      };

      if (video.requestVideoFrameCallback) {
        const videoFrameCallback = () => {
          if (princeVideoState === 'playing') {
            drawVideoToCanvas();
            videoFrameCallbackId = video.requestVideoFrameCallback(videoFrameCallback);
          } else {
            cleanupVideoFrameCallback();
          }
        };

        const startVideoFrameCallback = () => {
          if (!videoFrameCallbackId) {
            videoFrameCallbackId = video.requestVideoFrameCallback(videoFrameCallback);
          }
        };

        video.addEventListener('play', startVideoFrameCallback);
      }

      video.addEventListener('play', handleVideoPlay);
      video.addEventListener('pause', handleVideoPause);
      video.addEventListener('seeked', drawVideoToCanvas);
      video.addEventListener('timeupdate', drawVideoToCanvas);

      if (video.readyState >= 2) {
        // 视频元数据已加载
        initVideo();
      } else {
        // 等待元数据加载
        video.addEventListener('loadedmetadata', initVideo, { once: true });
      }

      // 初始绘制
      video.addEventListener('loadeddata', drawVideoToCanvas, { once: true });

      return () => {
        // 清理
        if (canvasAnimationRef.current) {
          cancelAnimationFrame(canvasAnimationRef.current);
        }
        // 取消 videoFrameCallback（如果支持）
        cleanupVideoFrameCallback();
        video.removeEventListener('play', handleVideoPlay);
        video.removeEventListener('pause', handleVideoPause);
        video.removeEventListener('seeked', drawVideoToCanvas);
        video.removeEventListener('timeupdate', drawVideoToCanvas);
      };
    }

    return () => {
      // 清理 Canvas 动画
      if (canvasAnimationRef.current) {
        cancelAnimationFrame(canvasAnimationRef.current);
      }
    };
  }, [princeVideoState]);

  // 切换播放
  const togglePlayback = () => {
    const video = princeVideoRef.current;
    if (!video || !video.duration) return;

    if (princeVideoState === 'idle' || princeVideoState === 'ended') {
      // 从第一帧开始播放
      video.currentTime = 0;
      setPrinceVideoState('playing');
      video.play().catch(console.error);

      // 同步背景视频的移动动画时长
      if (bgVideoRef.current) {
        const duration = video.duration || 3; // 默认3秒
        bgVideoRef.current.style.setProperty('--video-duration', `${duration}s`);
        bgVideoRef.current.style.transition = `object-position ${duration}s ease`;
      }
    } else if (princeVideoState === 'playing') {
      // 播放中点击：暂停播放（可选）
      // 当前实现：让视频正常播放完毕
    }
  };

  // 点击处理函数
  const handlePrinceVideoClick = () => {
    if (!isEnlarged) {
      // 如果未放大，先放大
      setIsEnlarged(true);
    }
    // 移除二次点击播放的逻辑，改为在动画结束后自动播放
  };

  // 处理放大动画结束
  const handleEnlargeEnd = (e) => {
    // 确保是 transform 属性的过渡结束，并且目标元素是正确的
    if (e.propertyName === 'transform' && e.target.classList.contains('portal-moon-prince-wrapper')) {
      // 检查是否已经放大（通过检查类名）
      if (e.target.classList.contains('is-enlarged')) {
        // 放大动画结束后自动播放视频
        setTimeout(() => {
          togglePlayback();
        }, 100); // 稍微延迟确保状态已更新
      }
    }
  };

  // 当放大完成时自动播放视频
  useEffect(() => {
    if (isEnlarged) {
      // 等待动画完成（1秒）后播放视频
      const timer = setTimeout(() => {
        togglePlayback();
      }, 1100); // 比动画时间长100ms，确保动画完成

      return () => clearTimeout(timer);
    }
  }, [isEnlarged]);

  // 处理视频播放结束
  const handlePrinceVideoEnded = () => {
    setPrinceVideoState('ended');
    const video = princeVideoRef.current;
    if (video && video.duration) {
      // 确保停留在最后一帧
      video.pause();
      // 设置到最后一帧（稍微提前一点，避免边界问题）
      const lastFrameTime = Math.max(0, video.duration - 0.05);
      video.currentTime = lastFrameTime;

      // 背景视频保持在右侧位置，不移回左侧
      // is-panning 类会保留，因为 princeVideoState 仍然是 'ended'
      // 需要在 CSS 中确保 ended 状态也保持右侧位置

      // 强制重新绘制最后一帧，确保白边被去除
      const drawLastFrame = () => {
        if (drawVideoToCanvasRef.current) {
          // 多次绘制以确保处理完成（最后一帧需要更彻底的处理）
          const drawMultiple = (count) => {
            if (count > 0 && drawVideoToCanvasRef.current) {
              requestAnimationFrame(() => {
                if (drawVideoToCanvasRef.current) {
                  drawVideoToCanvasRef.current();
                  // 递归绘制，确保多次处理
                  drawMultiple(count - 1);
                }
              });
            }
          };
          // 绘制3次，确保白斑被彻底去除
          drawMultiple(3);
        }
      };

      video.addEventListener('seeked', drawLastFrame, { once: true });
      // 立即尝试绘制（如果已经 seeked）
      drawLastFrame();
    }

    // 延迟启动转场动画，给用户一点时间看到最后一帧
    setTimeout(() => {
      setIsTransitioning(true);
      // 转场动画持续1.5秒后跳转
      setTimeout(() => {
        if (window.navigate) {
          window.navigate("#/kawaiichat");
        } else {
          window.location.hash = "#/kawaiichat";
        }
      }, 1500);
    }, 500);
  };

  const handleClose = () => setModalOpen(false);
  const handleAfterClose = () => setActiveStarId(null);
  
  // 登录成功处理 - 只关闭模态框，不跳转
  const handleLoginSuccess = () => {
    setShowLoginModal(false);
  };

  return (
    <div className={`portal-root${isTransitioning || isTransitioningToChat ? ' is-transitioning' : ''}`}>
      <div className="portal-transition-overlay" />
      <video
        ref={bgVideoRef}
        className={`portal-bg-video${princeVideoState === 'playing' || princeVideoState === 'ended' ? ' is-panning' : ''}`}
        src={bgVideo}
        autoPlay
        muted
        loop={loopVideo}
        playsInline
        aria-hidden="true"
      />

      <div className="portal-content">
        <div className="portal-header-slot" role="group" aria-label="导航按钮区域">
          {stars.map((star) => (
            star.id === 2 ? (
              <div key={star.id} className="portal-star-wrapper portal-star-wrapper--diamond">
                <svg className="portal-star-border-svg" viewBox="0 0 180 180" preserveAspectRatio="none">
                  <polygon
                    points="90,18 162,90 90,162 54,90"
                    fill="none"
                    stroke="rgba(255, 255, 255, 0.3)"
                    strokeWidth="2"
                    className="portal-star-border-path"
                  />
                </svg>
                <img
                  className="portal-star portal-star--diamond"
                  src={getStarImage(star.id)}
                  alt={star.name}
                  onClick={() => {
                    setActiveStarId(star.id);
                    // 下一帧开启以确保内容已挂载
                    requestAnimationFrame(() => setModalOpen(true));
                  }}
                />
              </div>
            ) : (
              <img
                className="portal-star"
                key={star.id}
                src={getStarImage(star.id)}
                alt={star.name}
                onClick={() => {
                  // id: 1 点击后跳转到视频通话页面，使用转场动画
                  setIsTransitioningToChat(true);
                  setTimeout(() => {
                    if (window.navigate) {
                      window.navigate("#/kawaiichat");
                    } else {
                      window.location.hash = "#/kawaiichat";
                    }
                  }, 1500);
                }}
              />
            )
          ))}
        </div>

        <div
          className={`portal-moon-prince-wrapper${isEnlarged ? ' is-enlarged' : ''}`}
          onTransitionEnd={handleEnlargeEnd}
        >
          <div className="portal-planet-slot" role="img" aria-label="星球容器">
            <img
              className="portal-moon"
              src={moonImg}
              alt="月亮"
            />
          </div>

          <div className="portal-prince-container">
            <video
              ref={princeVideoRef}
              className="portal-prince-video"
              src={princeTurnVideo}
              muted
              playsInline
              preload="metadata"
              onClick={handlePrinceVideoClick}
              onEnded={handlePrinceVideoEnded}
              aria-label="王子转身动画"
              style={{ display: 'none' }}
            />
            <canvas
              ref={canvasRef}
              className="portal-prince-canvas"
              onClick={handlePrinceVideoClick}
              aria-label="王子转身动画"
            />
          </div>
        </div>
      </div>

      <Modal open={modalOpen} onClose={handleClose} afterClose={handleAfterClose} isFullscreen={true}>
        {components[activeStarId] || <div style={{ padding: 16 }}>敬请期待</div>}
      </Modal>
      
      {/* 登录模态框已移除，改为单独的登录页面 #/login */}
    </div>
  );
}





