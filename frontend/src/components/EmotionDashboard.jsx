import PropTypes from "prop-types";
import { useEffect, useState } from "react";
import eegEventBus from "../utils/eegEventBus";
import CanvasWaveformChart from "./CanvasWaveformChart";



export default function EmotionDashboard({ emotion, faceEmotion, eegWaveform }) {
  // 添加状态来管理缓存的脑电波数据
  const [cachedEEGWaveform, setCachedEEGWaveform] = useState(null);
  
  // 监听事件总线中的脑电波数据更新
  useEffect(() => {
    // 获取初始缓存数据
    const initialCachedData = eegEventBus.getCachedWaveformData();
    if (initialCachedData) {
      setCachedEEGWaveform(initialCachedData);
    }
    
    // 订阅脑电波数据更新事件
    const unsubscribeUpdate = eegEventBus.subscribe('eeg_waveform_updated', (data) => {
      console.log('Received cached EEG waveform data:', data);
      setCachedEEGWaveform(data);
    });
    
    // 订阅脑电波数据清除事件
    const unsubscribeClear = eegEventBus.subscribe('eeg_waveform_cleared', () => {
      console.log('EEG waveform data cleared');
      setCachedEEGWaveform(null);
    });
    
    // 清理函数：取消订阅
    return () => {
      unsubscribeUpdate();
      unsubscribeClear();
    };
  }, []);
  
  // 处理情绪数据，确保有正确的结构
  const processedEmotion = emotion || {};
  const processedFaceEmotion = faceEmotion || {};
  const processedEegWaveform = eegWaveform || {};
  
  // 如果没有情绪数据，显示等待状态
  if (!processedEmotion && !processedFaceEmotion) {
    return (
      <div className="emotion-dashboard">
        <p>等待情感数据流…</p>
      </div>
    );
  }

  // 如果有面部情绪数据，生成模拟的脑电波数据
  const getWaveformFromEmotion = (emotionLabel, confidence) => {
    // 根据情绪标签生成不同的波形模式
    const patterns = {
      'happy': { frequency: 0.3, amplitude: 0.8 },
      'sad': { frequency: 0.1, amplitude: 0.4 },
      'angry': { frequency: 0.5, amplitude: 0.9 },
      'fear': { frequency: 0.7, amplitude: 0.6 },
      'surprise': { frequency: 0.6, amplitude: 0.7 },
      'neutral': { frequency: 0.2, amplitude: 0.3 },
      'disgust': { frequency: 0.4, amplitude: 0.5 }
    };
    
    const pattern = patterns[emotionLabel.toLowerCase()] || patterns['neutral'];
    const samples = 100;
    const channels = {
      'Fp1': [],
      'Fp2': [],
      'F3': [],
      'F4': []
    };
    
    // 为每个通道生成基于情绪的波形数据，但每个通道有不同的特性
    Object.keys(channels).forEach((channel, channelIndex) => {
      for (let i = 0; i < samples; i++) {
        // 为每个通道添加不同的相位偏移和频率变化，确保波形不同
        const phaseOffset = channelIndex * Math.PI / 4; // 每个通道有不同的相位偏移
        const frequencyMultiplier = 1 + (channelIndex * 0.1); // 每个通道有轻微的频率变化
        
        const baseValue = Math.sin(i * pattern.frequency * frequencyMultiplier * Math.PI / 10 + phaseOffset) * pattern.amplitude * 50;
        const noise = (Math.random() - 0.5) * 10;
        channels[channel].push(baseValue + noise);
      }
    });
    
    return { channels };
  };

  // 确定主要情绪标签和置信度
  let primaryLabel = 'neutral';
  let primaryConfidence = 0;
  let primaryMoodScore = 0;
  
  if (processedEmotion.label) {
    primaryLabel = processedEmotion.label;
    primaryConfidence = processedEmotion.confidence || 0;
    primaryMoodScore = processedEmotion.mood_score || primaryConfidence;
  } else if (processedFaceEmotion.label || processedFaceEmotion.emotion) {
    primaryLabel = processedFaceEmotion.label || processedFaceEmotion.emotion;
    primaryConfidence = processedFaceEmotion.confidence || 0;
    primaryMoodScore = primaryConfidence;
  }

  // 使用面部情绪数据生成脑电波，或使用原始脑电波数据
  const faceEmotionComponent = processedEmotion.components?.find(c => c.source === 'face');
  // 仅当有真实的脑电波形数据时才显示波形，否则不显示
  const waveform = processedEmotion.waveform;

  // 构建组件列表
  const components = [...(processedEmotion.components || [])];
  
  // 如果有独立的面部情绪数据且不在组件列表中，添加它
  if (processedFaceEmotion.label || processedFaceEmotion.emotion) {
    const faceLabel = processedFaceEmotion.label || processedFaceEmotion.emotion;
    if (!components.find(c => c.source === 'face' && c.label === faceLabel)) {
      components.push({
        source: 'face',
        label: faceLabel,
        confidence: processedFaceEmotion.confidence || 0,
        mood_score: processedFaceEmotion.confidence || 0
      });
    }
  }

  // 确定要显示的波形数据
  let displayWaveform = null;
  
  // 优先使用缓存的脑电波数据
  if (cachedEEGWaveform && cachedEEGWaveform.waveform) {
    displayWaveform = cachedEEGWaveform.waveform;
  }
  // 其次使用eegWaveform中的波形数据
  else if (processedEegWaveform && processedEegWaveform.waveform) {
    displayWaveform = processedEegWaveform.waveform;
  } 
  // 再次使用emotion中的波形数据
  else if (waveform) {
    displayWaveform = waveform;
  }
  // 如果都没有，但有面部情绪，则生成模拟波形
  else if (processedFaceEmotion.label || processedFaceEmotion.emotion) {
    const faceLabel = processedFaceEmotion.label || processedFaceEmotion.emotion;
    displayWaveform = getWaveformFromEmotion(faceLabel, processedFaceEmotion.confidence || 0);
  }

  return (
    <div className="emotion-dashboard">
      <header>
        <h2>融合情感</h2>
        <div className="emotion-current">
          <span className="emotion-label">{primaryLabel}</span>
          <span className="emotion-score">
            mood {primaryMoodScore.toFixed(2)} · conf {" "}
            {primaryConfidence.toFixed(2)}
          </span>
        </div>
      </header>
      <section className="emotion-components">
        <h3>通道贡献</h3>
        <ul>
          {components.map((component, index) => (
            <li key={`${component.source}-${index}`}>
              <span className="component-source">{component.source}</span>
              <span className="component-label">{component.label}</span>
              <span className="component-score">
                mood {component.mood_score.toFixed(2)} / conf {" "}
                {component.confidence.toFixed(2)}
              </span>
            </li>
          ))}
        </ul>
      </section>
      {/* 显示脑电波形数据 */}
      <section className="waveform-section">
        <h3>EEG 波形</h3>
        <CanvasWaveformChart waveform={displayWaveform} />
      </section>
    </div>
  );
}

EmotionDashboard.propTypes = {
  emotion: PropTypes.shape({
    label: PropTypes.string.isRequired,
    confidence: PropTypes.number.isRequired,
    mood_score: PropTypes.number.isRequired,
    components: PropTypes.arrayOf(
      PropTypes.shape({
        source: PropTypes.string.isRequired,
        label: PropTypes.string.isRequired,
        confidence: PropTypes.number.isRequired,
        mood_score: PropTypes.number.isRequired,
      })
    ).isRequired,
    waveform: PropTypes.shape({
      channels: PropTypes.objectOf(PropTypes.arrayOf(PropTypes.number)),
    }),
  }),
  faceEmotion: PropTypes.shape({
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
