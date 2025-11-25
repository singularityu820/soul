import { useEffect, useState, useRef } from "react";
import PropTypes from "prop-types";
import eegEventBus from "../utils/eegEventBus";
import CanvasWaveformChart from "./CanvasWaveformChart";
import useEEGDevice from "../hooks/useEEGDevice";

/**
 * 脑电波显示组件
 * 支持显示真实EEG数据和模拟数据
 */
export default function EEGWaveformDisplay({ faceEmotion, eegWaveform, useRealData = true }) {
  const [cachedEEGWaveform, setCachedEEGWaveform] = useState(null);
  const [displayWaveform, setDisplayWaveform] = useState(null);
  const [isRealDataAvailable, setIsRealDataAvailable] = useState(false);
  
  // 使用EEG设备Hook
  const {
    deviceStatus,
    isStreaming,
    eegData,
    connectDevice,
    disconnectDevice,
    startDataStream,
    stopDataStream,
    error: eegError
  } = useEEGDevice();
  
  // 生成假数据用于测试
  const generateMockWaveform = () => {
    const samples = 100;
    const channels = {
      'Fp1': [],
      'Fp2': [],
      'F3': [],
      'F4': []
    };
    
    // 为每个通道生成模拟波形数据
    Object.keys(channels).forEach((channel, channelIndex) => {
      for (let i = 0; i < samples; i++) {
        // 生成不同频率和相位的正弦波
        const frequency = 0.2 + (channelIndex * 0.1);
        const phaseOffset = channelIndex * Math.PI / 4;
        const amplitude = 30 + (channelIndex * 10);
        const baseValue = Math.sin(i * frequency * Math.PI / 10 + phaseOffset) * amplitude;
        const noise = (Math.random() - 0.5) * 15;
        channels[channel].push(baseValue + noise);
      }
    });
    
    return { channels };
  };

  // 初始化真实EEG数据连接
  useEffect(() => {
    if (!useRealData) return;
    
    // 自动连接设备并启动数据流
    const initializeEEGDevice = async () => {
      try {
        // 尝试连接设备，默认使用串口连接
        const connectResult = await connectDevice({ connectionType: 'serial' });
        
        if (connectResult.success) {
          // 启动数据流
          const streamResult = await startDataStream();
          if (streamResult.success) {
            setIsRealDataAvailable(true);
          }
        }
      } catch (error) {
        console.error('初始化EEG设备失败:', error);
        setIsRealDataAvailable(false);
      }
    };
    
    initializeEEGDevice();
    
    // 组件卸载时清理资源
    return () => {
      if (isStreaming) {
        stopDataStream();
      }
      if (deviceStatus === 'connected') {
        disconnectDevice();
      }
    };
  }, [useRealData, connectDevice, startDataStream, stopDataStream, disconnectDevice, isStreaming, deviceStatus]);

  // 处理真实EEG数据
  useEffect(() => {
    if (!useRealData || !eegData || !eegData.success) return;
    
    // 将真实EEG数据转换为波形格式
    const waveformFromRealData = {
      channels: {}
    };
    
    // 假设eegData.data包含原始EEG数据点
    if (eegData.data && Array.isArray(eegData.data)) {
      // 为每个通道创建数据数组
      const channelNames = ['Fp1', 'Fp2', 'F3', 'F4'];
      channelNames.forEach((channel, index) => {
        waveformFromRealData.channels[channel] = eegData.data.map(sample => {
          // 假设每个样本是一个数组，包含所有通道的数据
          return Array.isArray(sample) ? (sample[index] || 0) : 0;
        });
      });
    }
    
    // 更新显示波形
    setDisplayWaveform(waveformFromRealData);
  }, [useRealData, eegData]);

  // 监听事件总线中的脑电波数据更新
  useEffect(() => {
    // 获取初始缓存数据
    const initialCachedData = eegEventBus.getCachedWaveformData();
    if (initialCachedData) {
      setCachedEEGWaveform(initialCachedData);
    }
    
    // 订阅脑电波数据更新事件
    const unsubscribeUpdate = eegEventBus.subscribe('eeg_waveform_updated', (data) => {
      setCachedEEGWaveform(data);
    });
    
    // 订阅脑电波数据清除事件
    const unsubscribeClear = eegEventBus.subscribe('eeg_waveform_cleared', () => {
      setCachedEEGWaveform(null);
    });
    
    return () => {
      unsubscribeUpdate();
      unsubscribeClear();
    };
  }, []);

  // 根据情绪生成模拟波形数据
  const getWaveformFromEmotion = (emotionLabel, confidence) => {
    const patterns = {
      'happy': { frequency: 0.3, amplitude: 0.8 },
      'sad': { frequency: 0.1, amplitude: 0.4 },
      'angry': { frequency: 0.5, amplitude: 0.9 },
      'fear': { frequency: 0.7, amplitude: 0.6 },
      'surprise': { frequency: 0.6, amplitude: 0.7 },
      'neutral': { frequency: 0.2, amplitude: 0.3 },
      'disgust': { frequency: 0.4, amplitude: 0.5 }
    };
    
    const pattern = patterns[emotionLabel?.toLowerCase()] || patterns['neutral'];
    const samples = 100;
    const channels = {
      'Fp1': [],
      'Fp2': [],
      'F3': [],
      'F4': []
    };
    
    Object.keys(channels).forEach((channel, channelIndex) => {
      for (let i = 0; i < samples; i++) {
        const phaseOffset = channelIndex * Math.PI / 4;
        const frequencyMultiplier = 1 + (channelIndex * 0.1);
        const baseValue = Math.sin(i * pattern.frequency * frequencyMultiplier * Math.PI / 10 + phaseOffset) * pattern.amplitude * 50;
        const noise = (Math.random() - 0.5) * 10;
        channels[channel].push(baseValue + noise);
      }
    });
    
    return { channels };
  };

  // 确定要显示的波形数据
  useEffect(() => {
    let waveform = null;
    
    // 如果使用真实数据且真实数据可用，优先使用真实数据
    if (useRealData && isRealDataAvailable && displayWaveform) {
      // 已经在处理真实EEG数据的useEffect中设置了displayWaveform
      return;
    }
    // 优先使用缓存的脑电波数据
    else if (cachedEEGWaveform && cachedEEGWaveform.waveform) {
      waveform = cachedEEGWaveform.waveform;
    }
    // 其次使用eegWaveform中的波形数据
    else if (eegWaveform && eegWaveform.waveform) {
      waveform = eegWaveform.waveform;
    }
    // 如果 eegWaveform 中只有情绪标签（例如来自语音情绪检测），也用该标签生成模拟波形
    else if (eegWaveform && (eegWaveform.label || eegWaveform.emotion)) {
      const emotionLabel = eegWaveform.label || eegWaveform.emotion;
      const confidence = eegWaveform.confidence || 0;
      waveform = getWaveformFromEmotion(emotionLabel, confidence);
    }
    // 如果都没有，但有面部情绪，则生成模拟波形
    else if (faceEmotion && (faceEmotion.label || faceEmotion.emotion)) {
      const faceLabel = faceEmotion.label || faceEmotion.emotion;
      waveform = getWaveformFromEmotion(faceLabel, faceEmotion.confidence || 0);
    }
    // 如果都没有数据，使用假数据用于测试
    else {
      waveform = generateMockWaveform();
    }
    
    setDisplayWaveform(waveform);
  }, [useRealData, isRealDataAvailable, cachedEEGWaveform, eegWaveform, faceEmotion]);

  // 如果没有波形数据，使用假数据（确保始终有数据显示）
  const finalWaveform = displayWaveform || generateMockWaveform();

  // 渲染设备状态指示器（仅在使用真实数据时显示）
  const renderDeviceStatus = () => {
    if (!useRealData) return null;
    
    let statusColor = '#888';
    let statusText = '未知';
    
    if (deviceStatus === 'connected') {
      statusColor = '#4CAF50';
      statusText = '已连接';
    } else if (deviceStatus === 'connecting') {
      statusColor = '#FFC107';
      statusText = '连接中';
    } else if (deviceStatus === 'error') {
      statusColor = '#F44336';
      statusText = '连接错误';
    } else {
      statusColor = '#888';
      statusText = '未连接';
    }
    
    return (
      <div className="eeg-device-status">
        <div className="status-indicator" style={{ backgroundColor: statusColor }}></div>
        <span className="status-text">{statusText}</span>
        {isRealDataAvailable && <span className="real-data-indicator">实时数据</span>}
      </div>
    );
  };

  // 迷你状态圆点颜色（用于 ChatNew 右上角紧凑显示）
  const getMiniDotColor = () => {
    if (!useRealData) return 'transparent';
    if (deviceStatus === 'connected') return '#4CAF50';
    if (deviceStatus === 'connecting') return '#FFC107';
    if (deviceStatus === 'error') return '#F44336';
    return '#888';
  };

  return (
    <div className="eeg-waveform-display">
      {/* 小圆点指示（最小化显示） */}
      <div
        className={`eeg-mini-dot ${deviceStatus === 'connected' ? 'connected' : ''}`}
        style={{ backgroundColor: getMiniDotColor() }}
        aria-hidden="true"
      />
      {renderDeviceStatus()}
      <CanvasWaveformChart waveform={finalWaveform} transparent={true} />
    </div>
  );
}

EEGWaveformDisplay.propTypes = {
  faceEmotion: PropTypes.shape({
    label: PropTypes.string,
    emotion: PropTypes.string,
    confidence: PropTypes.number,
  }),
  eegWaveform: PropTypes.shape({
    waveform: PropTypes.oneOfType([
      PropTypes.shape({
        channels: PropTypes.objectOf(PropTypes.arrayOf(PropTypes.number)),
      }),
      PropTypes.array
    ]),
    emotion: PropTypes.string
  }),
  useRealData: PropTypes.bool
};

