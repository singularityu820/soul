/**
 * 全局事件总线，用于管理脑电波数据的缓存和延长显示
 */
class EEGEventBus {
  constructor() {
    this.listeners = new Map();
    this.cachedWaveformData = null;
    this.waveformDisplayTimer = null;
    this.waveformDisplayDuration = 10000; // 默认显示10秒
    
    // 历史数据存储和滑动窗口 - 优化参数以支持更高的更新频率
    this.waveformHistory = [];
    this.maxHistorySize = 20; // 增加历史记录大小，从10到20
    this.slidingWindowSize = 8; // 增加滑动窗口大小，从5到8，提供更丰富的数据
  }

  /**
   * 订阅事件
   * @param {string} eventType 事件类型
   * @param {Function} callback 回调函数
   */
  subscribe(eventType, callback) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, []);
    }
    this.listeners.get(eventType).push(callback);
    
    // 返回取消订阅函数
    return () => {
      const callbacks = this.listeners.get(eventType);
      if (callbacks) {
        const index = callbacks.indexOf(callback);
        if (index > -1) {
          callbacks.splice(index, 1);
        }
      }
    };
  }

  /**
   * 发布事件
   * @param {string} eventType 事件类型
   * @param {any} data 事件数据
   */
  publish(eventType, data) {
    const callbacks = this.listeners.get(eventType);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in event callback for ${eventType}:`, error);
        }
      });
    }
  }

  /**
   * 缓存脑电波数据并设置延长显示
   * @param {Object} waveformData 脑电波数据
   * @param {number} displayDuration 显示持续时间（毫秒）
   */
  cacheWaveformData(waveformData, displayDuration = this.waveformDisplayDuration) {
    // 清除之前的定时器
    if (this.waveformDisplayTimer) {
      clearTimeout(this.waveformDisplayTimer);
    }
    
    // 添加到历史记录
    this.addToHistory(waveformData);
    
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
      // 不清除缓存，而是使用历史数据生成滑动窗口数据
      this.generateSlidingWindowData();
    }, displayDuration);
  }

  /**
   * 添加波形数据到历史记录
   * @param {Object} waveformData 脑电波数据
   */
  addToHistory(waveformData) {
    // 添加到历史记录
    this.waveformHistory.push({
      ...waveformData,
      timestamp: Date.now()
    });
    
    // 如果历史记录超过最大大小，移除最旧的数据
    if (this.waveformHistory.length > this.maxHistorySize) {
      this.waveformHistory.shift();
    }
    
    // 发布历史数据更新事件
    this.publish('eeg_history_updated', this.waveformHistory);
  }

  /**
   * 生成滑动窗口数据
   */
  generateSlidingWindowData() {
    if (this.waveformHistory.length === 0) {
      this.cachedWaveformData = null;
      this.publish('eeg_waveform_cleared', null);
      return;
    }
    
    // 获取最近的滑动窗口数据
    const recentData = this.waveformHistory.slice(-this.slidingWindowSize);
    
    // 合并波形数据
    const mergedWaveform = this.mergeWaveformData(recentData);
    
    // 更新缓存数据
    this.cachedWaveformData = {
      ...mergedWaveform,
      timestamp: Date.now(),
      displayUntil: Date.now() + this.waveformDisplayDuration,
      isSlidingWindow: true
    };
    
    // 发布更新事件
    this.publish('eeg_waveform_updated', this.cachedWaveformData);
    
    // 设置定时器，继续生成滑动窗口数据
    this.waveformDisplayTimer = setTimeout(() => {
      this.generateSlidingWindowData();
    }, this.waveformDisplayDuration);
  }

  /**
   * 合并多个波形数据
   * @param {Array} waveformList 波形数据列表
   * @returns {Object} 合并后的波形数据
   */
  mergeWaveformData(waveformList) {
    if (!waveformList || waveformList.length === 0) {
      return null;
    }
    
    // 如果只有一个数据，直接返回
    if (waveformList.length === 1) {
      return waveformList[0];
    }
    
    // 合并多个波形数据
    const mergedChannels = {};
    
    // 获取所有通道名称
    const allChannels = new Set();
    waveformList.forEach(waveform => {
      if (waveform.waveform && waveform.waveform.channels) {
        Object.keys(waveform.waveform.channels).forEach(channel => {
          allChannels.add(channel);
        });
      } else if (waveform.channels) {
        Object.keys(waveform.channels).forEach(channel => {
          allChannels.add(channel);
        });
      }
    });
    
    // 为每个通道合并数据
    allChannels.forEach(channel => {
      const channelData = [];
      
      waveformList.forEach(waveform => {
        let data = null;
        
        if (waveform.waveform && waveform.waveform.channels && waveform.waveform.channels[channel]) {
          data = waveform.waveform.channels[channel];
        } else if (waveform.channels && waveform.channels[channel]) {
          data = waveform.channels[channel];
        }
        
        if (data && Array.isArray(data)) {
          channelData.push(...data);
        }
      });
      
      mergedChannels[channel] = channelData;
    });
    
    // 返回合并后的波形数据
    return {
      waveform: {
        channels: mergedChannels
      }
    };
  }

  /**
   * 获取当前缓存的脑电波数据
   * @returns {Object|null} 当前缓存的脑电波数据
   */
  getCachedWaveformData() {
    // 检查缓存是否已过期
    if (this.cachedWaveformData && Date.now() > this.cachedWaveformData.displayUntil) {
      // 如果是滑动窗口数据，生成新的滑动窗口数据
      if (this.cachedWaveformData.isSlidingWindow) {
        this.generateSlidingWindowData();
      } else {
        this.cachedWaveformData = null;
      }
    }
    return this.cachedWaveformData;
  }

  /**
   * 获取历史数据
   * @returns {Array} 历史数据列表
   */
  getWaveformHistory() {
    return [...this.waveformHistory];
  }

  /**
   * 设置脑电波显示持续时间
   * @param {number} duration 显示持续时间（毫秒）
   */
  setWaveformDisplayDuration(duration) {
    this.waveformDisplayDuration = duration;
  }

  /**
   * 设置历史数据最大大小
   * @param {number} size 最大大小
   */
  setMaxHistorySize(size) {
    this.maxHistorySize = size;
    
    // 如果当前历史记录超过新的大小，移除最旧的数据
    while (this.waveformHistory.length > this.maxHistorySize) {
      this.waveformHistory.shift();
    }
  }

  /**
   * 设置滑动窗口大小
   * @param {number} size 窗口大小
   */
  setSlidingWindowSize(size) {
    this.slidingWindowSize = size;
  }

  /**
   * 清除所有定时器和缓存
   */
  clearAll() {
    if (this.waveformDisplayTimer) {
      clearTimeout(this.waveformDisplayTimer);
      this.waveformDisplayTimer = null;
    }
    this.cachedWaveformData = null;
    this.waveformHistory = [];
    this.listeners.clear();
  }
}

// 创建全局单例实例
const eegEventBus = new EEGEventBus();

export default eegEventBus;