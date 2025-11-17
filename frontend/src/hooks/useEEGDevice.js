/**
 * EEG设备管理Hook
 * 提供EEG设备连接、数据获取和状态管理的功能
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import eegDeviceService from '../services/eegDeviceService';

/**
 * EEG设备管理Hook
 * @returns {Object} EEG设备状态和控制函数
 */
export const useEEGDevice = () => {
  // 设备状态
  const [deviceStatus, setDeviceStatus] = useState('disconnected'); // disconnected, connecting, connected, error
  const [deviceInfo, setDeviceInfo] = useState(null);
  const [isCollecting, setIsCollecting] = useState(false);
  const [eegData, setEEGData] = useState(null);
  const [error, setError] = useState(null);
  
  // WebSocket连接状态
  const [isStreaming, setIsStreaming] = useState(false);
  
  // 引用
  const roomIdRef = useRef(`eeg-room-${Date.now()}`);
  const dataCallbackRef = useRef(null);
  const statusCallbackRef = useRef(null);

  // 更新设备状态
  const updateDeviceStatus = useCallback((status) => {
    setDeviceStatus(status);
  }, []);

  // 连接设备
  const connectDevice = useCallback(async (options = {}) => {
    try {
      setError(null);
      const result = await eegDeviceService.connectDevice(options);
      
      if (result.success) {
        // 获取设备状态
        const status = await eegDeviceService.getDeviceStatus();
        if (status.success) {
          setDeviceInfo(status);
        }
      } else {
        setError(result.message);
      }
      
      return result;
    } catch (err) {
      const errorMessage = `连接设备失败: ${err.message}`;
      setError(errorMessage);
      return { success: false, message: errorMessage };
    }
  }, []);

  // 断开设备连接
  const disconnectDevice = useCallback(async () => {
    try {
      // 先停止数据流
      if (isStreaming) {
        stopDataStream();
      }
      
      // 如果正在采集，先停止采集
      if (isCollecting) {
        await stopDataCollection();
      }
      
      const result = await eegDeviceService.disconnectDevice();
      if (!result.success) {
        setError(result.message);
      }
      
      setDeviceInfo(null);
      setEEGData(null);
      return result;
    } catch (err) {
      const errorMessage = `断开设备连接失败: ${err.message}`;
      setError(errorMessage);
      return { success: false, message: errorMessage };
    }
  }, [isStreaming, isCollecting]);

  // 开始数据采集
  const startDataCollection = useCallback(async (options = {}) => {
    try {
      setError(null);
      const result = await eegDeviceService.startDataCollection(options);
      
      if (result.success) {
        setIsCollecting(true);
      } else {
        setError(result.message);
      }
      
      return result;
    } catch (err) {
      const errorMessage = `开始数据采集失败: ${err.message}`;
      setError(errorMessage);
      return { success: false, message: errorMessage };
    }
  }, []);

  // 停止数据采集
  const stopDataCollection = useCallback(async () => {
    try {
      setError(null);
      const result = await eegDeviceService.stopDataCollection();
      
      if (result.success) {
        setIsCollecting(false);
      } else {
        setError(result.message);
      }
      
      return result;
    } catch (err) {
      const errorMessage = `停止数据采集失败: ${err.message}`;
      setError(errorMessage);
      return { success: false, message: errorMessage };
    }
  }, []);

  // 获取当前数据
  const getCurrentData = useCallback(async () => {
    try {
      const data = await eegDeviceService.getCurrentData();
      
      if (data.success) {
        setEEGData(data);
      } else {
        setError(data.message);
      }
      
      return data;
    } catch (err) {
      const errorMessage = `获取数据失败: ${err.message}`;
      setError(errorMessage);
      return { success: false, message: errorMessage };
    }
  }, []);

  // 数据回调函数
  const handleDataCallback = useCallback((data) => {
    setEEGData(data);
  }, []);

  // 状态回调函数
  const handleStatusCallback = useCallback((status) => {
    setDeviceStatus(status);
  }, []);

  // 开始数据流
  const startDataStream = useCallback(async () => {
    try {
      setError(null);
      
      // 保存回调函数引用
      dataCallbackRef.current = handleDataCallback;
      statusCallbackRef.current = handleStatusCallback;
      
      const result = await eegDeviceService.startDataStream(
        roomIdRef.current,
        handleDataCallback,
        handleStatusCallback
      );
      
      if (result.success) {
        setIsStreaming(true);
      } else {
        setError(result.message);
      }
      
      return result;
    } catch (err) {
      const errorMessage = `启动数据流失败: ${err.message}`;
      setError(errorMessage);
      return { success: false, message: errorMessage };
    }
  }, [handleDataCallback, handleStatusCallback]);

  // 停止数据流
  const stopDataStream = useCallback(() => {
    eegDeviceService.stopDataStream();
    setIsStreaming(false);
  }, []);

  // 刷新设备状态
  const refreshDeviceStatus = useCallback(async () => {
    try {
      const status = await eegDeviceService.getDeviceStatus();
      if (status.success) {
        setDeviceInfo(status);
        setDeviceStatus(status.status);
      } else {
        setError(status.message);
      }
      return status;
    } catch (err) {
      const errorMessage = `刷新设备状态失败: ${err.message}`;
      setError(errorMessage);
      return { success: false, message: errorMessage };
    }
  }, []);

  // 清除错误
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // 组件卸载时清理资源
  useEffect(() => {
    return () => {
      if (isStreaming) {
        stopDataStream();
      }
    };
  }, [isStreaming, stopDataStream]);

  return {
    // 状态
    deviceStatus,
    deviceInfo,
    isCollecting,
    isStreaming,
    eegData,
    error,
    
    // 控制函数
    connectDevice,
    disconnectDevice,
    startDataCollection,
    stopDataCollection,
    getCurrentData,
    startDataStream,
    stopDataStream,
    refreshDeviceStatus,
    clearError,
  };
};

export default useEEGDevice;