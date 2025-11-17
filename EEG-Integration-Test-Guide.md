# EEG设备集成测试指南

## 概述

本指南说明如何测试前端与真实EEG设备的集成功能。我们已经完成了以下工作：

1. 创建了EEG设备通信服务 (`frontend/src/services/eegDeviceService.js`)
2. 创建了EEG设备管理Hook (`frontend/src/hooks/useEEGDevice.js`)
3. 修改了EEG波形显示组件以支持真实数据 (`frontend/src/components/EEGWaveformDisplay.jsx`)
4. 创建了EEG设备控制面板 (`frontend/src/components/EEGDeviceControlPanel.jsx`)
5. 在ChatNew页面中集成了EEG设备控制功能

## 测试步骤

### 1. 启动系统

确保前端和后端服务器都已启动：

- 前端服务器：http://localhost:5173
- 后端服务器：http://localhost:8000

### 2. 访问主应用

访问 http://localhost:5173/ 进入应用。

### 3. 测试EEG设备功能

1. 在右上角找到"脑电波监测"面板
2. 点击"真实设备"按钮切换到真实设备模式
3. 点击齿轮图标打开设备控制面板
4. 在控制面板中：
   - 选择连接类型（串口或蓝牙）
   - 设置连接参数（串口号或蓝牙地址）
   - 点击"连接设备"按钮
   - 连接成功后，点击"开始采集"按钮
   - 观察脑电波数据显示

### 4. 使用测试页面（可选）

访问 http://localhost:5173/test-eeg.html 使用专门的测试页面：

1. 点击"运行所有测试"执行完整的测试流程
2. 或单独测试各个功能：
   - 连接/断开设备
   - 开始/停止数据采集
   - 获取EEG数据

## 预期结果

### 成功场景

1. 设备连接成功，状态显示为"已连接"
2. 数据采集启动成功，状态显示为"采集中"
3. 脑电波数据实时显示在波形图上
4. 设备控制面板显示正确的设备状态

### 可能的问题

1. **设备连接失败**
   - 检查设备是否正确连接
   - 确认串口号或蓝牙地址是否正确
   - 检查设备驱动是否安装

2. **数据采集失败**
   - 确认设备已成功连接
   - 检查采样率和通道数设置是否正确

3. **数据显示异常**
   - 检查WebSocket连接是否正常
   - 确认数据格式是否正确

## 技术细节

### API端点

- `POST /eeg/real/connect` - 连接EEG设备
- `POST /eeg/real/disconnect` - 断开EEG设备
- `GET /eeg/real/status` - 获取设备状态
- `POST /eeg/real/start` - 开始数据采集
- `POST /eeg/real/stop` - 停止数据采集
- `GET /eeg/real/data` - 获取EEG数据
- `WebSocket /eeg/real/stream/{room_id}` - 实时数据流

### 组件说明

1. **EEGDeviceService** - 处理与后端EEG API的通信
2. **useEEGDevice** - 管理EEG设备状态和数据的React Hook
3. **EEGWaveformDisplay** - 显示脑电波波形图
4. **EEGDeviceControlPanel** - 提供设备控制界面

## 故障排除

1. 检查浏览器控制台是否有错误信息
2. 确认前后端服务器都正常运行
3. 检查网络连接和防火墙设置
4. 验证EEG设备硬件是否正常工作

## 后续改进

1. 添加更多设备类型的支持
2. 优化数据采集性能
3. 增强错误处理和用户反馈
4. 添加设备配置保存功能