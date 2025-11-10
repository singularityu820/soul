/**
 * 全局事件总线，用于管理脑电波数据的缓存和延长显示
 */
class EEGEventBus {
  constructor() {
    this.listeners = new Map();
    this.cachedWaveformData = null;
    this.waveformDisplayTimer = null;
    this.waveformDisplayDuration = 10000; // 默认显示10秒
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

  /**
   * 获取当前缓存的脑电波数据
   * @returns {Object|null} 当前缓存的脑电波数据
   */
  getCachedWaveformData() {
    // 检查缓存是否已过期
    if (this.cachedWaveformData && Date.now() > this.cachedWaveformData.displayUntil) {
      this.cachedWaveformData = null;
    }
    return this.cachedWaveformData;
  }

  /**
   * 设置脑电波显示持续时间
   * @param {number} duration 显示持续时间（毫秒）
   */
  setWaveformDisplayDuration(duration) {
    this.waveformDisplayDuration = duration;
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
    this.listeners.clear();
  }
}

// 创建全局单例实例
const eegEventBus = new EEGEventBus();

export default eegEventBus;