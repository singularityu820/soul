"""
真实脑电数据API端点
提供连接真实脑电设备、获取数据和处理情绪的API接口
"""
import asyncio
import logging
import json
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .real_eeg import create_eeg_processor, EEGDataPacket, RealEEGProcessor
from ...config import EEGStreamConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/eeg/real", tags=["真实脑电数据"])

# 全局变量存储EEG处理器实例
eeg_processor: Optional[RealEEGProcessor] = None
is_streaming = False
streaming_task: Optional[asyncio.Task] = None
active_connections: List[WebSocket] = []


class EEGDeviceConfig(BaseModel):
    """EEG设备配置"""
    device_type: str = "simulated"  # "simulated" 或 "serial"
    port: Optional[str] = None
    baudrate: int = 115200
    channels: List[str] = ["Fp1", "Fp2", "F3", "F4"]
    sample_rate: float = 250.0


class EEGConnectionResponse(BaseModel):
    """EEG连接响应"""
    success: bool
    message: str
    device_type: str
    connected: bool


class EEGEmotionResponse(BaseModel):
    """EEG情绪分析响应"""
    emotion_class: int
    emotion_label: str
    confidence: float
    mood_score: float
    timestamp: float


@router.post("/connect", response_model=EEGConnectionResponse)
async def connect_eeg_device(config: EEGDeviceConfig):
    """连接EEG设备"""
    global eeg_processor, is_streaming, streaming_task
    
    try:
        # 如果已经连接，先断开
        if eeg_processor and eeg_processor.device.is_connected():
            await eeg_processor.disconnect()
            is_streaming = False
            if streaming_task and not streaming_task.done():
                streaming_task.cancel()
        
        # 创建新的EEG处理器
        eeg_processor = create_eeg_processor(
            device_type=config.device_type,
            port=config.port,
            baudrate=config.baudrate,
            channels=config.channels,
            sample_rate=config.sample_rate
        )
        
        # 连接设备
        connected = await eeg_processor.connect()
        
        if connected:
            logger.info(f"成功连接到{config.device_type}设备")
            return EEGConnectionResponse(
                success=True,
                message=f"成功连接到{config.device_type}设备",
                device_type=config.device_type,
                connected=True
            )
        else:
            logger.error(f"连接{config.device_type}设备失败")
            return EEGConnectionResponse(
                success=False,
                message=f"连接{config.device_type}设备失败",
                device_type=config.device_type,
                connected=False
            )
    except Exception as e:
        logger.error(f"连接EEG设备时出错: {e}")
        raise HTTPException(status_code=500, detail=f"连接EEG设备失败: {str(e)}")


@router.post("/disconnect", response_model=EEGConnectionResponse)
async def disconnect_eeg_device():
    """断开EEG设备连接"""
    global eeg_processor, is_streaming, streaming_task
    
    try:
        if eeg_processor:
            # 停止数据流
            is_streaming = False
            if streaming_task and not streaming_task.done():
                streaming_task.cancel()
            
            # 断开设备连接
            await eeg_processor.disconnect()
            
            logger.info("已断开EEG设备连接")
            return EEGConnectionResponse(
                success=True,
                message="已断开EEG设备连接",
                device_type=eeg_processor.device.__class__.__name__,
                connected=False
            )
        else:
            return EEGConnectionResponse(
                success=True,
                message="没有连接的设备",
                device_type="none",
                connected=False
            )
    except Exception as e:
        logger.error(f"断开EEG设备连接时出错: {e}")
        raise HTTPException(status_code=500, detail=f"断开EEG设备连接失败: {str(e)}")


@router.post("/stream/start")
async def start_eeg_stream(background_tasks: BackgroundTasks):
    """开始EEG数据流"""
    global eeg_processor, is_streaming, streaming_task
    
    try:
        if not eeg_processor or not eeg_processor.device.is_connected():
            raise HTTPException(status_code=400, detail="设备未连接")
        
        if is_streaming:
            return {"success": True, "message": "数据流已在运行中"}
        
        # 启动数据流任务
        is_streaming = True
        streaming_task = asyncio.create_task(stream_eeg_data())
        
        logger.info("已启动EEG数据流")
        return {"success": True, "message": "EEG数据流已启动"}
    except Exception as e:
        logger.error(f"启动EEG数据流时出错: {e}")
        raise HTTPException(status_code=500, detail=f"启动EEG数据流失败: {str(e)}")


@router.post("/stream/stop")
async def stop_eeg_stream():
    """停止EEG数据流"""
    global is_streaming, streaming_task
    
    try:
        is_streaming = False
        if streaming_task and not streaming_task.done():
            streaming_task.cancel()
        
        logger.info("已停止EEG数据流")
        return {"success": True, "message": "EEG数据流已停止"}
    except Exception as e:
        logger.error(f"停止EEG数据流时出错: {e}")
        raise HTTPException(status_code=500, detail=f"停止EEG数据流失败: {str(e)}")


@router.get("/status")
async def get_eeg_status():
    """获取EEG设备状态"""
    global eeg_processor, is_streaming
    
    if not eeg_processor:
        return {
            "connected": False,
            "streaming": False,
            "device_type": "none",
            "message": "没有初始化的设备"
        }
    
    return {
        "connected": eeg_processor.device.is_connected(),
        "streaming": is_streaming,
        "device_type": eeg_processor.device.__class__.__name__,
        "channels": eeg_processor.device.channels,
        "sample_rate": eeg_processor.device.sample_rate,
        "buffer_size": {ch: len(buf) for ch, buf in eeg_processor.data_buffer.items()},
        "training_data_loaded": eeg_processor.training_data_loaded
    }


@router.get("/data/latest")
async def get_latest_eeg_data():
    """获取最新的EEG数据"""
    global eeg_processor
    
    if not eeg_processor or not eeg_processor.device.is_connected():
        raise HTTPException(status_code=400, detail="设备未连接")
    
    try:
        # 获取最新数据
        channels_data = {}
        for channel, buffer in eeg_processor.data_buffer.items():
            if buffer:
                channels_data[channel] = list(buffer)
        
        if not channels_data:
            return {"message": "没有可用的数据"}
        
        # 处理数据并预测情绪
        emotion_result = eeg_processor.process_all_data(channels_data)
        
        return {
            "timestamp": emotion_result["timestamp"],
            "channels": channels_data,
            "emotion": emotion_result,
            "band_energy": eeg_processor._compute_band_energy(channels_data)
        }
    except Exception as e:
        logger.error(f"获取EEG数据时出错: {e}")
        raise HTTPException(status_code=500, detail=f"获取EEG数据失败: {str(e)}")


@router.get("/emotion/current", response_model=EEGEmotionResponse)
async def get_current_emotion():
    """获取当前情绪分析结果"""
    global eeg_processor
    
    if not eeg_processor or not eeg_processor.device.is_connected():
        raise HTTPException(status_code=400, detail="设备未连接")
    
    try:
        # 获取最新数据
        channels_data = {}
        for channel, buffer in eeg_processor.data_buffer.items():
            if buffer:
                channels_data[channel] = list(buffer)
        
        if not channels_data:
            raise HTTPException(status_code=400, detail="没有可用的数据")
        
        # 处理数据并预测情绪
        emotion_result = eeg_processor.process_all_data(channels_data)
        
        return EEGEmotionResponse(
            emotion_class=emotion_result["emotion_class"],
            emotion_label=emotion_result["emotion_label"],
            confidence=0.7,  # 默认置信度
            mood_score=0.0,  # 默认情绪分数
            timestamp=emotion_result["timestamp"]
        )
    except Exception as e:
        logger.error(f"获取情绪分析结果时出错: {e}")
        raise HTTPException(status_code=500, detail=f"获取情绪分析结果失败: {str(e)}")


@router.websocket("/stream")
async def websocket_eeg_stream(websocket: WebSocket):
    """WebSocket端点，实时传输EEG数据"""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            # 等待客户端消息
            await websocket.receive_text()
            
            # 获取最新数据
            if eeg_processor and eeg_processor.device.is_connected():
                channels_data = {}
                for channel, buffer in eeg_processor.data_buffer.items():
                    if buffer:
                        channels_data[channel] = list(buffer)
                
                if channels_data:
                    # 处理数据并预测情绪
                    emotion_result = eeg_processor.process_all_data(channels_data)
                    band_energy = eeg_processor._compute_band_energy(channels_data)
                    
                    # 发送数据到客户端
                    await websocket.send_json({
                        "timestamp": emotion_result["timestamp"],
                        "channels": channels_data,
                        "emotion": emotion_result,
                        "band_energy": band_energy
                    })
            
            await asyncio.sleep(0.1)  # 限制发送频率
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info("WebSocket连接已断开")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)


async def stream_eeg_data():
    """后台任务，持续读取EEG数据"""
    global eeg_processor, is_streaming
    
    if not eeg_processor:
        return
    
    try:
        async for sample in eeg_processor.start_streaming():
            if not is_streaming:
                break
                
            # 将数据发送到所有连接的WebSocket客户端
            if active_connections:
                channels_data = {}
                for channel, buffer in eeg_processor.data_buffer.items():
                    if buffer:
                        channels_data[channel] = list(buffer)
                
                if channels_data:
                    # 处理数据并预测情绪
                    emotion_result = eeg_processor.process_all_data(channels_data)
                    band_energy = eeg_processor._compute_band_energy(channels_data)
                    
                    # 发送数据到所有连接的客户端
                    message = {
                        "timestamp": emotion_result["timestamp"],
                        "channels": channels_data,
                        "emotion": emotion_result,
                        "band_energy": band_energy
                    }
                    
                    # 发送到所有活跃连接
                    disconnected = []
                    for connection in active_connections:
                        try:
                            await connection.send_json(message)
                        except Exception as e:
                            logger.error(f"发送WebSocket消息失败: {e}")
                            disconnected.append(connection)
                    
                    # 移除断开的连接
                    for connection in disconnected:
                        if connection in active_connections:
                            active_connections.remove(connection)
            
            await asyncio.sleep(0.05)  # 控制数据流速率
    except asyncio.CancelledError:
        logger.info("EEG数据流任务已取消")
    except Exception as e:
        logger.error(f"EEG数据流错误: {e}")
        is_streaming = False


@router.get("/devices/available")
async def get_available_devices():
    """获取可用的EEG设备列表"""
    try:
        import serial.tools.list_ports
        
        ports = serial.tools.list_ports.comports()
        available_devices = []
        
        for port in ports:
            device_info = {
                "port": port.device,
                "description": port.description,
                "hwid": port.hwid,
                "vid": port.vid,
                "pid": port.pid
            }
            available_devices.append(device_info)
        
        return {
            "available_ports": available_devices,
            "simulated_device": {
                "type": "simulated",
                "description": "模拟脑电设备，用于测试"
            }
        }
    except Exception as e:
        logger.error(f"获取可用设备列表时出错: {e}")
        return {"error": str(e)}