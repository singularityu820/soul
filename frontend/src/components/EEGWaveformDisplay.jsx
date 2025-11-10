import { useEffect, useState, useRef } from "react";
import PropTypes from "prop-types";
import eegEventBus from "../utils/eegEventBus";
import CanvasWaveformChart from "./CanvasWaveformChart";

/**
 * 简化的脑电波显示组件
 * 透明背景，只显示脑电波图
 */
export default function EEGWaveformDisplay({ faceEmotion, eegWaveform }) {
  const [cachedEEGWaveform, setCachedEEGWaveform] = useState(null);
  const [displayWaveform, setDisplayWaveform] = useState(null);
  
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
    
    // 优先使用缓存的脑电波数据
    if (cachedEEGWaveform && cachedEEGWaveform.waveform) {
      waveform = cachedEEGWaveform.waveform;
    }
    // 其次使用eegWaveform中的波形数据
    else if (eegWaveform && eegWaveform.waveform) {
      waveform = eegWaveform.waveform;
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
  }, [cachedEEGWaveform, eegWaveform, faceEmotion]);

  // 如果没有波形数据，使用假数据（确保始终有数据显示）
  const finalWaveform = displayWaveform || generateMockWaveform();

  return (
    <div className="eeg-waveform-display">
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
  })
};

