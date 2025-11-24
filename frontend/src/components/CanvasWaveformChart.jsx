import PropTypes from "prop-types";
import { useEffect, useRef, useState, useCallback } from "react";

function CanvasWaveformChart({ waveform, transparent = false }) {
  const canvasRef = useRef(null);
  const animationFrameId = useRef(null);
  const dataBuffer = useRef(new Array(200).fill(0));
  const updateIntervalRef = useRef(null);
  const [isInitialized, setIsInitialized] = useState(false);
  
  // 缓冲区大小 - 控制显示的数据点数量
  const BUFFER_SIZE = 400;
  
  // 合并四个通道的数据为一个通道
  const mergeChannels = useCallback((channels) => {
    const mergedData = [];
    const maxLength = Math.max(...channels.map(channel => 
      Array.isArray(channel) ? channel.length : 0
    ));
    
    for (let i = 0; i < maxLength; i++) {
      let sum = 0;
      let count = 0;
      
      channels.forEach(channel => {
        if (Array.isArray(channel) && channel[i] !== undefined) {
          sum += channel[i];
          count++;
        }
      });
      
      // 计算平均值
      mergedData.push(count > 0 ? sum / count : 0);
    }
    
    return mergedData;
  }, []);
  
  // 更新数据缓冲区 - 新数据入队，旧数据出队
  const updateBuffer = useCallback((newData) => {
    const buffer = dataBuffer.current;
    
    // 将新数据添加到缓冲区末尾
    if (Array.isArray(newData)) {
      // 如果新数据是数组，逐个添加
      newData.forEach(value => {
        buffer.push(value || 0);
        // 如果缓冲区超过大小，移除最旧的数据
        if (buffer.length > BUFFER_SIZE) {
          buffer.shift();
        }
      });
    } else {
      // 如果新数据是单个值
      buffer.push(newData || 0);
      // 如果缓冲区超过大小，移除最旧的数据
      if (buffer.length > BUFFER_SIZE) {
        buffer.shift();
      }
    }
    
    return buffer;
  }, []);
  
  // 绘制波形
  const drawWaveform = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const buffer = dataBuffer.current;
    
    if (!buffer || buffer.length === 0) return;
    
    // 根据 transparent 参数决定是否绘制背景
    if (!transparent) {
      // 设置深色背景
      ctx.fillStyle = '#0a0a0a';
      ctx.fillRect(0, 0, width, height);
      
      // 添加微妙的网格背景
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.03)';
      ctx.lineWidth = 0.5;
      for (let i = 0; i < width; i += 20) {
        ctx.beginPath();
        ctx.moveTo(i, 0);
        ctx.lineTo(i, height);
        ctx.stroke();
      }
      for (let i = 0; i < height; i += 20) {
        ctx.beginPath();
        ctx.moveTo(0, i);
        ctx.lineTo(width, i);
        ctx.stroke();
      }
    } else {
      // 透明背景：清除画布
      ctx.clearRect(0, 0, width, height);
    }
    
    // 创建径向渐变，从中心向两侧渐变
    const centerX = width / 2;
    const gradient = ctx.createLinearGradient(0, 0, width, 0);
    gradient.addColorStop(0, '#00d4ff');      // 青色
    gradient.addColorStop(0.2, '#06d6a0');    // 绿色
    gradient.addColorStop(0.4, '#7209b7');    // 紫色
    gradient.addColorStop(0.6, '#f72585');    // 粉色
    gradient.addColorStop(0.8, '#ffbe0b');    // 黄色
    gradient.addColorStop(1, '#fb5607');      // 橙色
    
    // 设置主线条样式
    ctx.strokeStyle = gradient;
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    
    // 添加发光效果
    ctx.shadowColor = '#06d6a0';
    ctx.shadowBlur = 15;
    ctx.shadowOffsetX = 0;
    ctx.shadowOffsetY = 0;
    
    // 绘制主波形
    ctx.beginPath();
    buffer.forEach((value, index) => {
      const x = (index / (BUFFER_SIZE - 1)) * width;
      // 归一化处理，确保值在0-height范围内
      let normalized;
      if (typeof value === 'number') {
        // 假设值范围在-100到100之间
        normalized = (value + 100) / 200;
      } else {
        normalized = 0.5; // 默认中间位置
      }
      const y = height - Math.min(Math.max(normalized, 0), 1) * height;
      
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();
    
    // 添加第二条更细的发光线，增强效果
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
    ctx.lineWidth = 1.5;
    ctx.shadowColor = '#ffffff';
    ctx.shadowBlur = 8;
    
    ctx.beginPath();
    buffer.forEach((value, index) => {
      const x = (index / (BUFFER_SIZE - 1)) * width;
      let normalized;
      if (typeof value === 'number') {
        normalized = (value + 100) / 200;
      } else {
        normalized = 0.5;
      }
      const y = height - Math.min(Math.max(normalized, 0), 1) * height;
      
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();
    
    // 添加第三条极细的高光线
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.lineWidth = 0.5;
    ctx.shadowColor = '#ffffff';
    ctx.shadowBlur = 3;
    
    ctx.beginPath();
    buffer.forEach((value, index) => {
      const x = (index / (BUFFER_SIZE - 1)) * width;
      let normalized;
      if (typeof value === 'number') {
        normalized = (value + 100) / 200;
      } else {
        normalized = 0.5;
      }
      const y = height - Math.min(Math.max(normalized, 0), 1) * height;
      
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();
  }, []);
  
  // 动画循环 - 实现连续显示效果
  const animate = useCallback(() => {
    drawWaveform();
    animationFrameId.current = requestAnimationFrame(() => animate());
  }, [drawWaveform]);
  
  // 处理波形数据变化
  useEffect(() => {
    if (!waveform) return;
    
    // 处理从后端获取的波形数据
    let channels = [];
    if (waveform.channels) {
      // 从后端获取的数据格式
      channels = Object.entries(waveform.channels);
    } else if (waveform.waveform && waveform.waveform.channels) {
      // 处理嵌套的波形数据结构 {waveform: {channels: {...}}}
      channels = Object.entries(waveform.waveform.channels);
    } else if (Array.isArray(waveform) && waveform.length > 0) {
      // 可能是其他格式的数据
      channels = waveform.map((data, index) => [`channel_${index}`, data]);
    }
    
    // 确保我们有四个通道
    const requiredChannels = ['Fp1', 'Fp2', 'F3', 'F4'];
    const channelMap = new Map(channels);
    
    // 获取四个通道的数据
    const channelData = requiredChannels.map(channelName => {
      return channelMap.get(channelName) || [];
    });
    
    // 合并四个通道的数据
    const mergedData = mergeChannels(channelData);
    
    // 更新数据缓冲区
    updateBuffer(mergedData);
    
    // 标记为已初始化
    setIsInitialized(true);
  }, [waveform]); // 移除 mergeChannels 和 updateBuffer 依赖以避免无限循环
  
  // 启动动画循环和定时更新
  useEffect(() => {
    if (!isInitialized) return;
    
    // 启动动画循环
    if (!animationFrameId.current) {
      animate();
    }
    
    // 设置定时更新，模拟连续数据流
    updateIntervalRef.current = setInterval(() => {
      // 生成随机数据点，模拟连续数据流
      const randomValue = (Math.random() - 0.5) * 100;
      updateBuffer(randomValue);
    }, 100); // 每100ms更新一次
    
    // 清理函数
    return () => {
      if (animationFrameId.current) {
        cancelAnimationFrame(animationFrameId.current);
        animationFrameId.current = null;
      }
      
      if (updateIntervalRef.current) {
        clearInterval(updateIntervalRef.current);
        updateIntervalRef.current = null;
      }
    };
  }, [isInitialized, animate, updateBuffer]);
  
  // 如果没有波形数据，返回占位符
  if (!waveform) {
    return <div className="waveform-placeholder">暂无波形数据</div>;
  }
  
  return (
    <div className={`waveform-container${transparent ? ' waveform-container--transparent' : ''}`}>
      {!transparent && <h3>合并脑电波</h3>}
      <div className="waveform-chart">
        <canvas
          ref={(el) => {
            if (el) {
              // 设置canvas尺寸 - 增加宽度使波形更稀疏
              el.width = 1200;
              el.height = 200;
              canvasRef.current = el;
            }
          }}
          className="waveform-canvas"
          style={{ 
            width: '100%', 
            height: '100%', 
            borderRadius: transparent ? '0' : '8px',
            boxShadow: transparent ? 'none' : '0 4px 12px rgba(0, 0, 0, 0.15)'
          }}
        />
      </div>
    </div>
  );
}

CanvasWaveformChart.propTypes = {
  waveform: PropTypes.shape({
    channels: PropTypes.objectOf(PropTypes.arrayOf(PropTypes.number)),
  }),
  transparent: PropTypes.bool,
};

export default CanvasWaveformChart;