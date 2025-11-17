/**
 * EEG设备API服务
 * 处理与真实EEG设备的连接、数据获取和状态管理
 */

// API基础URL
const API_PREFIX = process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8000';

/**
 * EEG设备服务类
 */
class EEGDeviceService {
  constructor() {
    this.deviceStatus = 'disconnected'; // disconnected, connecting, connected, error
    this.streamSocket = null;
    this.roomId = null;
    this.dataCallback = null;
    this.statusCallback = null;
  }

  /**
   * 连接EEG设备
   * @param {Object} options 连接选项
   * @param {string} options.connectionType 连接类型：bluetooth 或 serial
   * @param {string} options.port 串口名称（仅串口连接需要）
   * @param {string} options.deviceName 设备名称（仅蓝牙连接需要）
   * @returns {Promise<Object>} 连接结果
   */
  async connectDevice(options = {}) {
    try {
      this.updateStatus('connecting');
      
      const response = await fetch(`${API_PREFIX}/eeg/real/connect`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(options),
      });

      if (!response.ok) {
        throw new Error(`连接失败: ${response.statusText}`);
      }

      const result = await response.json();
      
      if (result.success) {
        this.updateStatus('connected');
        return { success: true, message: result.message };
      } else {
        this.updateStatus('error');
        return { success: false, message: result.message };
      }
    } catch (error) {
      this.updateStatus('error');
      console.error('连接EEG设备失败:', error);
      return { success: false, message: error.message };
    }
  }

  /**
   * 断开EEG设备连接
   * @returns {Promise<Object>} 断开结果
   */
  async disconnectDevice() {
    try {
      // 先停止数据流
      if (this.streamSocket) {
        this.stopDataStream();
      }

      const response = await fetch(`${API_PREFIX}/eeg/real/disconnect`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error(`断开连接失败: ${response.statusText}`);
      }

      const result = await response.json();
      this.updateStatus('disconnected');
      return { success: true, message: result.message };
    } catch (error) {
      console.error('断开EEG设备连接失败:', error);
      return { success: false, message: error.message };
    }
  }

  /**
   * 获取设备状态
   * @returns {Promise<Object>} 设备状态
   */
  async getDeviceStatus() {
    try {
      const response = await fetch(`${API_PREFIX}/eeg/real/status`);
      
      if (!response.ok) {
        throw new Error(`获取状态失败: ${response.statusText}`);
      }

      const status = await response.json();
      return status;
    } catch (error) {
      console.error('获取EEG设备状态失败:', error);
      return { 
        success: false, 
        status: 'error', 
        message: error.message 
      };
    }
  }

  /**
   * 开始EEG数据采集
   * @param {Object} options 采集选项
   * @param {number} options.sampleRate 采样率，默认250Hz
   * @param {number} options.channels 通道数，默认8
   * @returns {Promise<Object>} 开始结果
   */
  async startDataCollection(options = {}) {
    try {
      const { sampleRate = 250, channels = 8 } = options;
      
      const response = await fetch(`${API_PREFIX}/eeg/real/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ sample_rate: sampleRate, channels }),
      });

      if (!response.ok) {
        throw new Error(`开始采集失败: ${response.statusText}`);
      }

      const result = await response.json();
      return { success: true, message: result.message };
    } catch (error) {
      console.error('开始EEG数据采集失败:', error);
      return { success: false, message: error.message };
    }
  }

  /**
   * 停止EEG数据采集
   * @returns {Promise<Object>} 停止结果
   */
  async stopDataCollection() {
    try {
      const response = await fetch(`${API_PREFIX}/eeg/real/stop`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error(`停止采集失败: ${response.statusText}`);
      }

      const result = await response.json();
      return { success: true, message: result.message };
    } catch (error) {
      console.error('停止EEG数据采集失败:', error);
      return { success: false, message: error.message };
    }
  }

  /**
   * 获取当前EEG数据
   * @returns {Promise<Object>} EEG数据
   */
  async getCurrentData() {
    try {
      const response = await fetch(`${API_PREFIX}/eeg/real/data`);
      
      if (!response.ok) {
        throw new Error(`获取数据失败: ${response.statusText}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('获取EEG数据失败:', error);
      return { 
        success: false, 
        message: error.message 
      };
    }
  }

  /**
   * 开始EEG数据流
   * @param {string} roomId 房间ID，用于WebSocket连接
   * @param {Function} dataCallback 数据回调函数
   * @param {Function} statusCallback 状态回调函数
   * @returns {Promise<Object>} 开始结果
   */
  async startDataStream(roomId, dataCallback, statusCallback) {
    try {
      this.roomId = roomId;
      this.dataCallback = dataCallback;
      this.statusCallback = statusCallback;

      // 确定WebSocket URL
      const wsUrl = process.env.NODE_ENV === 'production' 
        ? `/ws/eeg/real/stream/${roomId}` 
        : `ws://localhost:8000/ws/eeg/real/stream/${roomId}`;

      // 创建WebSocket连接
      this.streamSocket = new WebSocket(wsUrl);

      return new Promise((resolve, reject) => {
        // 连接超时处理
        const timeoutId = setTimeout(() => {
          if (this.streamSocket.readyState !== WebSocket.OPEN) {
            this.streamSocket.close();
            reject(new Error("WebSocket连接超时"));
          }
        }, 5000);

        this.streamSocket.onopen = () => {
          clearTimeout(timeoutId);
          console.log("EEG数据流WebSocket连接已建立");
          resolve({ success: true, message: "数据流已连接" });
        };

        this.streamSocket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (this.dataCallback) {
              this.dataCallback(data);
            }
          } catch (error) {
            console.error("解析EEG数据失败:", error);
          }
        };

        this.streamSocket.onerror = (error) => {
          console.error("EEG数据流WebSocket错误:", error);
          if (this.statusCallback) {
            this.statusCallback('error');
          }
          reject(new Error("WebSocket连接错误"));
        };

        this.streamSocket.onclose = () => {
          console.log("EEG数据流WebSocket连接已关闭");
          if (this.statusCallback) {
            this.statusCallback('disconnected');
          }
        };
      });
    } catch (error) {
      console.error('启动EEG数据流失败:', error);
      return { success: false, message: error.message };
    }
  }

  /**
   * 停止EEG数据流
   */
  stopDataStream() {
    if (this.streamSocket) {
      this.streamSocket.close();
      this.streamSocket = null;
    }
    this.roomId = null;
    this.dataCallback = null;
    this.statusCallback = null;
  }

  /**
   * 更新设备状态
   * @param {string} status 新状态
   */
  updateStatus(status) {
    this.deviceStatus = status;
    if (this.statusCallback) {
      this.statusCallback(status);
    }
  }

  /**
   * 获取当前设备状态
   * @returns {string} 当前状态
   */
  getStatus() {
    return this.deviceStatus;
  }
}

// 创建单例实例
const eegDeviceService = new EEGDeviceService();

export default eegDeviceService;