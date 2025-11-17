/**
 * EEG设备控制面板组件
 * 提供EEG设备连接、断开、数据采集控制等功能
 */

import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import useEEGDevice from '../hooks/useEEGDevice';
import './EEGDeviceControlPanel.css';

/**
 * EEG设备控制面板组件
 * @param {Object} props 组件属性
 * @param {Function} props.onDataUpdate 数据更新回调函数
 * @param {boolean} props.visible 是否显示控制面板
 */
export default function EEGDeviceControlPanel({ onDataUpdate, visible = true }) {
  // 使用EEG设备Hook
  const {
    deviceStatus,
    deviceInfo,
    isCollecting,
    isStreaming,
    eegData,
    error,
    connectDevice,
    disconnectDevice,
    startDataCollection,
    stopDataCollection,
    startDataStream,
    stopDataStream,
    refreshDeviceStatus,
    clearError
  } = useEEGDevice();

  // 连接选项状态
  const [connectionType, setConnectionType] = useState('serial');
  const [portName, setPortName] = useState('');
  const [deviceName, setDeviceName] = useState('');
  const [sampleRate, setSampleRate] = useState(250);
  const [channels, setChannels] = useState(8);

  // 当EEG数据更新时，调用回调函数
  useEffect(() => {
    if (eegData && onDataUpdate) {
      onDataUpdate(eegData);
    }
  }, [eegData, onDataUpdate]);

  // 处理连接设备
  const handleConnectDevice = async () => {
    clearError();
    
    const options = {
      connectionType
    };
    
    if (connectionType === 'serial' && portName) {
      options.port = portName;
    } else if (connectionType === 'bluetooth' && deviceName) {
      options.device_name = deviceName;
    }
    
    await connectDevice(options);
  };

  // 处理断开设备连接
  const handleDisconnectDevice = async () => {
    clearError();
    await disconnectDevice();
  };

  // 处理开始数据采集
  const handleStartDataCollection = async () => {
    clearError();
    await startDataCollection({ sampleRate, channels });
    
    // 开始数据流
    await startDataStream();
  };

  // 处理停止数据采集
  const handleStopDataCollection = async () => {
    clearError();
    
    // 停止数据流
    if (isStreaming) {
      stopDataStream();
    }
    
    // 停止数据采集
    if (isCollecting) {
      await stopDataCollection();
    }
  };

  // 刷新设备状态
  const handleRefreshStatus = async () => {
    clearError();
    await refreshDeviceStatus();
  };

  // 如果面板不可见，返回null
  if (!visible) {
    return null;
  }

  // 渲染设备状态指示器
  const renderStatusIndicator = () => {
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
      <div className="status-indicator-container">
        <div className="status-indicator" style={{ backgroundColor: statusColor }}></div>
        <span className="status-text">{statusText}</span>
      </div>
    );
  };

  // 渲染连接选项
  const renderConnectionOptions = () => {
    return (
      <div className="connection-options">
        <div className="form-group">
          <label>连接类型:</label>
          <select 
            value={connectionType} 
            onChange={(e) => setConnectionType(e.target.value)}
            disabled={deviceStatus === 'connected' || deviceStatus === 'connecting'}
          >
            <option value="serial">串口连接</option>
            <option value="bluetooth">蓝牙连接</option>
          </select>
        </div>
        
        {connectionType === 'serial' && (
          <div className="form-group">
            <label>串口名称:</label>
            <input 
              type="text" 
              value={portName} 
              onChange={(e) => setPortName(e.target.value)}
              placeholder="例如: COM3 或 /dev/ttyUSB0"
              disabled={deviceStatus === 'connected' || deviceStatus === 'connecting'}
            />
          </div>
        )}
        
        {connectionType === 'bluetooth' && (
          <div className="form-group">
            <label>设备名称:</label>
            <input 
              type="text" 
              value={deviceName} 
              onChange={(e) => setDeviceName(e.target.value)}
              placeholder="例如: MindWave Mobile"
              disabled={deviceStatus === 'connected' || deviceStatus === 'connecting'}
            />
          </div>
        )}
      </div>
    );
  };

  // 渲染数据采集选项
  const renderDataCollectionOptions = () => {
    return (
      <div className="data-collection-options">
        <div className="form-group">
          <label>采样率 (Hz):</label>
          <select 
            value={sampleRate} 
            onChange={(e) => setSampleRate(Number(e.target.value))}
            disabled={isCollecting}
          >
            <option value="125">125</option>
            <option value="250">250</option>
            <option value="500">500</option>
            <option value="1000">1000</option>
          </select>
        </div>
        
        <div className="form-group">
          <label>通道数:</label>
          <select 
            value={channels} 
            onChange={(e) => setChannels(Number(e.target.value))}
            disabled={isCollecting}
          >
            <option value="4">4</option>
            <option value="8">8</option>
            <option value="16">16</option>
            <option value="32">32</option>
          </select>
        </div>
      </div>
    );
  };

  // 渲染控制按钮
  const renderControlButtons = () => {
    return (
      <div className="control-buttons">
        {deviceStatus !== 'connected' ? (
          <button 
            className="connect-button" 
            onClick={handleConnectDevice}
            disabled={deviceStatus === 'connecting'}
          >
            {deviceStatus === 'connecting' ? '连接中...' : '连接设备'}
          </button>
        ) : (
          <button 
            className="disconnect-button" 
            onClick={handleDisconnectDevice}
          >
            断开连接
          </button>
        )}
        
        <button 
          className="refresh-button" 
          onClick={handleRefreshStatus}
          disabled={deviceStatus === 'connecting'}
        >
          刷新状态
        </button>
        
        {deviceStatus === 'connected' && !isCollecting && (
          <button 
            className="start-button" 
            onClick={handleStartDataCollection}
          >
            开始采集
          </button>
        )}
        
        {isCollecting && (
          <button 
            className="stop-button" 
            onClick={handleStopDataCollection}
          >
            停止采集
          </button>
        )}
      </div>
    );
  };

  // 渲染设备信息
  const renderDeviceInfo = () => {
    if (!deviceInfo || deviceStatus !== 'connected') {
      return null;
    }
    
    return (
      <div className="device-info">
        <h4>设备信息</h4>
        <div className="info-item">
          <span className="info-label">设备类型:</span>
          <span className="info-value">{deviceInfo.device_type || '未知'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">连接方式:</span>
          <span className="info-value">{deviceInfo.connection_type || '未知'}</span>
        </div>
        {deviceInfo.port && (
          <div className="info-item">
            <span className="info-label">端口:</span>
            <span className="info-value">{deviceInfo.port}</span>
          </div>
        )}
        <div className="info-item">
          <span className="info-label">采样状态:</span>
          <span className="info-value">{isCollecting ? '采集中' : '未采集'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">数据流状态:</span>
          <span className="info-value">{isStreaming ? '流式传输中' : '未传输'}</span>
        </div>
      </div>
    );
  };

  // 渲染错误信息
  const renderError = () => {
    if (!error) {
      return null;
    }
    
    return (
      <div className="error-message">
        <span className="error-icon">⚠️</span>
        <span className="error-text">{error}</span>
        <button className="clear-error-button" onClick={clearError}>
          ✕
        </button>
      </div>
    );
  };

  return (
    <div className="eeg-device-control-panel">
      <div className="panel-header">
        <h3>EEG设备控制</h3>
        {renderStatusIndicator()}
      </div>
      
      {renderError()}
      
      <div className="panel-content">
        {renderConnectionOptions()}
        {renderDataCollectionOptions()}
        {renderControlButtons()}
        {renderDeviceInfo()}
      </div>
    </div>
  );
}

EEGDeviceControlPanel.propTypes = {
  onDataUpdate: PropTypes.func,
  visible: PropTypes.bool
};