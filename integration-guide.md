# 面部情绪识别、情感管道及脑电波显示功能集成指南

## 概述

本文档说明如何将面部情绪识别、情感管道及脑电波显示功能融入前端同学重构后的前端代码中。这些功能是情绪智能系统的核心组成部分，能够实时分析用户的面部表情，生成对应的脑电波形数据，并通过可视化界面展示。

## 功能架构

### 1. 面部情绪识别
- **功能描述**：通过摄像头捕获用户面部图像，使用深度学习模型识别情绪状态
- **技术实现**：基于DeepFace和百度API的情绪识别
- **输出**：情绪标签(happy/sad/angry等)和置信度

### 2. 情感管道
- **功能描述**：将面部情绪映射到脑电波形数据
- **技术实现**：基于训练数据的情绪到脑电波映射算法
- **输出**：多通道脑电波形数据

### 3. 脑电波显示
- **功能描述**：将脑电波形数据可视化展示
- **技术实现**：SVG波形图和实时数据更新
- **输出**：动态脑电波形图

## 核心组件

### 1. VideoDisplay组件
**位置**：`frontend/src/components/VideoDisplay.jsx`

**功能**：
- 捕获视频帧并发送到后端进行情绪识别
- 处理情绪检测结果
- 获取情绪对应的脑电波形数据
- 将脑电波数据缓存到事件总线

**关键代码**：
```javascript
// 获取情绪对应的脑电波形数据
const fetchEEGWaveform = useCallback(async (emotion) => {
  if (!emotion) return;
  
  try {
    const response = await fetch(`http://localhost:8000/eeg/waveform/${emotion}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    if (response.ok) {
      const waveformData = await response.json();
      
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
```

### 2. EmotionDashboard组件
**位置**：`frontend/src/components/EmotionDashboard.jsx`

**功能**：
- 显示融合情感数据
- 渲染脑电波形图
- 管理情绪历史记录

**关键代码**：
```javascript
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
  
  // 清理函数：取消订阅
  return () => {
    unsubscribeUpdate();
    unsubscribeClear();
  };
}, []);
```

### 3. EEGEventBus工具类
**位置**：`frontend/src/utils/eegEventBus.js`

**功能**：
- 管理脑电波数据的缓存和延长显示
- 提供发布-订阅模式的事件系统
- 确保脑电波数据在情绪检测间隔期间持续显示

**关键代码**：
```javascript
/**
 * 缓存脑电波数据并设置延长显示
 */
cacheWaveformData(waveformData, displayDuration = this.waveformDisplayDuration) {
  // 清除之前的定时器
  if (this.waveformDisplayTimer) {
    clearTimeout(this.waveformDisplayTimer);
  }
  
  // 缓存新的脑电波数据
  this.cachedWaveformData = {
    ...waveformData,
    timestamp: Date.now(),
    displayUntil: Date.now() + displayDuration
  };
  
  // 发布脑电波数据更新事件
  this.publish('eeg_waveform_updated', this.cachedWaveformData);
  
  // 设置新的定时器，在显示时间结束后清除缓存
  this.waveformDisplayTimer = setTimeout(() => {
    this.cachedWaveformData = null;
    this.publish('eeg_waveform_cleared', null);
  }, displayDuration);
}
```

## 后端API接口

### 1. 面部情绪识别API
**端点**：`POST /emotion/detect`

**功能**：接收图像数据，返回面部情绪识别结果

**请求格式**：
```javascript
const formData = new FormData();
formData.append('image', blob, 'frame.jpg');

const response = await fetch('http://localhost:8000/emotion/detect', {
  method: 'POST',
  body: formData
});
```

**响应格式**：
```json
{
  "emotion": "happy",
  "confidence": 0.85,
  "face_position": [
    {
      "x": 100,
      "y": 100,
      "width": 200,
      "height": 200
    }
  ]
}
```

### 2. 脑电波形生成API
**端点**：`GET /eeg/waveform/{emotion}`

**功能**：根据情绪类型生成对应的脑电波形数据

**请求格式**：
```javascript
const response = await fetch(`http://localhost:8000/eeg/waveform/${emotion}`, {
  method: 'GET',
  headers: {
    'Content-Type': 'application/json'
  }
});
```

**响应格式**：
```json
{
  "emotion": "happy",
  "waveform": {
    "channels": {
      "signal": [0.1, 0.2, 0.15, ...]
    },
    "sample_rate_hz": 250
  },
  "timestamp": 1234567890,
  "duration": 5.0,
  "band_powers": {
    "delta": 0.2,
    "theta": 0.4,
    "alpha": 0.7,
    "beta": 0.8,
    "gamma": 0.7
  }
}
```

### 3. 面部情绪到脑电波形映射API
**端点**：`GET /eeg/face-waveform/{emotion}`

**功能**：根据面部情绪生成对应的脑电波形数据，整合训练数据信息

**请求格式**：
```javascript
const response = await fetch(`http://localhost:8000/eeg/face-waveform/${emotion}`, {
  method: 'GET',
  headers: {
    'Content-Type': 'application/json'
  }
});
```

**响应格式**：
```json
{
  "emotion": "happy",
  "waveform": {
    "channels": {
      "signal": [0.1, 0.2, 0.15, ...]
    },
    "sample_rate_hz": 250
  },
  "timestamp": "2023-01-01T00:00:00",
  "duration": 5.0,
  "band_powers": {
    "delta": 0.2,
    "theta": 0.4,
    "alpha": 0.7,
    "beta": 0.8,
    "gamma": 0.7
  },
  "data_source": "real_training_data",
  "emotion_history": [
    {
      "timestamp": "2023-01-01T00:00:00",
      "emotion": "happy",
      "data_source": "real_training_data",
      "duration": 5.0,
      "sample_rate": 250
    }
  ]
}
```

## 集成步骤

### 步骤1：复制核心文件
将以下文件复制到新的前端项目中：
1. `frontend/src/components/VideoDisplay.jsx`
2. `frontend/src/components/EmotionDashboard.jsx`
3. `frontend/src/utils/eegEventBus.js`

### 步骤2：安装依赖
确保安装了以下依赖：
```bash
npm install prop-types
```

### 步骤3：集成VideoDisplay组件
在需要显示视频和情绪检测的页面中集成VideoDisplay组件：

```javascript
import VideoDisplay from './components/VideoDisplay';

// 在组件中使用
<VideoDisplay
  stream={videoStream}
  isActive={isVideoActive}
  roomId={currentRoomId}
  onEmotionDetected={handleEmotionDetected}
  emotionDetectionEnabled={emotionDetectionEnabled}
/>
```

### 步骤4：集成EmotionDashboard组件
在需要显示情绪数据和脑电波形的页面中集成EmotionDashboard组件：

```javascript
import EmotionDashboard from './components/EmotionDashboard';

// 在组件中使用
<EmotionDashboard
  emotion={currentEmotion}
  faceEmotion={faceEmotionData}
  eegWaveform={eegWaveformData}
/>
```

### 步骤5：处理情绪数据流
在父组件中处理情绪数据流：

```javascript
// 处理情绪检测结果
const handleEmotionDetected = useCallback((emotionData) => {
  // 更新本地情绪状态
  setEmotionState(emotionData);

  // 调用父组件的情绪更新回调
  if (onEmotionUpdate) {
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
```

### 步骤6：配置API前缀
确保API_PREFIX正确配置：

```javascript
const API_PREFIX = 'http://localhost:8000';
```

## 注意事项

1. **跨域问题**：确保后端API配置了正确的CORS设置，允许前端访问。

2. **视频流权限**：确保应用已获取摄像头权限，否则情绪检测功能无法正常工作。

3. **性能优化**：情绪检测和脑电波形生成是计算密集型操作，建议：
   - 限制情绪检测频率（如每秒1次）
   - 使用缓存机制减少不必要的API调用
   - 在组件卸载时清理定时器和事件监听器

4. **错误处理**：添加适当的错误处理，确保在API调用失败或设备不可用时应用仍能正常运行。

5. **数据格式**：确保前后端数据格式一致，特别是情绪标签和脑电波数据结构。

## 扩展功能

1. **真实脑电设备集成**：系统已预留了真实脑电设备接口，可通过以下API端点使用：
   - `POST /eeg/real/connect` - 连接真实脑电设备
   - `POST /eeg/real/start` - 开始数据流
   - `GET /eeg/real/data` - 获取真实脑电数据

2. **情绪历史记录**：系统支持记录情绪历史，可用于长期情绪分析。

3. **多通道脑电波**：系统支持多通道脑电波数据，可扩展为更复杂的脑电波可视化。

## 总结

通过以上步骤，您可以成功将面部情绪识别、情感管道及脑电波显示功能集成到前端同学重构后的前端代码中。这些功能将为用户提供更加智能和沉浸式的情绪交互体验。