"""EEG-related routes."""

import logging
import time

import numpy as np
from fastapi import APIRouter, HTTPException

from ..dependencies import get_eeg_waveform_service, get_real_eeg_processor

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/eeg/waveform/{emotion}")
async def get_emotion_waveform(
    emotion: str,
    duration: float = 5.0,
    sample_rate: int = 250,
) -> dict:
    """
    根据情绪生成对应的脑电波形数据
    
    Args:
        emotion: 情绪类型 (happy, sad, neutral, angry, surprise, fear, disgust)
        duration: 波形持续时间(秒)
        sample_rate: 采样率(Hz)
    
    Returns:
        {
            "emotion": "情绪类型",
            "waveform": {
                "channels": {"signal": [波形数据点]},
                "sample_rate_hz": 采样率
            },
            "timestamp": "时间戳"
        }
    """
    try:
        # 根据情绪类型设置不同的脑电波特征
        emotion_configs = {
            "happy": {
                "alpha": 0.7,
                "beta": 0.8,
                "theta": 0.4,
                "gamma": 0.6,
            },
            "sad": {
                "alpha": 0.3,
                "beta": 0.4,
                "theta": 0.7,
                "gamma": 0.2,
            },
            "neutral": {
                "alpha": 0.5,
                "beta": 0.5,
                "theta": 0.5,
                "gamma": 0.5,
            },
            "angry": {
                "alpha": 0.2,
                "beta": 0.9,
                "theta": 0.3,
                "gamma": 0.8,
            },
            "surprise": {
                "alpha": 0.4,
                "beta": 0.8,
                "theta": 0.3,
                "gamma": 0.7,
            },
            "fear": {
                "alpha": 0.3,
                "beta": 0.7,
                "theta": 0.6,
                "gamma": 0.5,
            },
            "disgust": {
                "alpha": 0.4,
                "beta": 0.6,
                "theta": 0.5,
                "gamma": 0.4,
            }
        }
        
        # 获取情绪配置，如果不存在则使用中性配置
        config = emotion_configs.get(emotion, emotion_configs["neutral"])
        
        # 生成波形数据
        # 计算采样点数
        num_samples = int(duration * sample_rate)
        
        # 创建时间轴
        t = np.linspace(0, duration, num_samples)
        
        # 生成不同频段的脑电波
        delta = 0.5 * np.sin(2 * np.pi * 2 * t) * config.get("delta", 0.5)    # 0.5-4Hz
        theta = 0.5 * np.sin(2 * np.pi * 6 * t) * config.get("theta", 0.5)    # 4-8Hz
        alpha = 0.5 * np.sin(2 * np.pi * 10 * t) * config.get("alpha", 0.5)   # 8-13Hz
        beta = 0.5 * np.sin(2 * np.pi * 20 * t) * config.get("beta", 0.5)    # 13-30Hz
        gamma = 0.5 * np.sin(2 * np.pi * 40 * t) * config.get("gamma", 0.5)  # 30-45Hz
        
        # 合成波形
        waveform_data = delta + theta + alpha + beta + gamma
        
        # 添加一些随机噪声
        noise = np.random.normal(0, 0.1, num_samples)
        waveform_data += noise
        
        # 归一化到[-1, 1]范围
        if np.max(np.abs(waveform_data)) > 0:
            waveform_data = waveform_data / np.max(np.abs(waveform_data))
        
        # 转换为Python列表
        waveform_list = waveform_data.tolist()
        
        # 构建返回结果
        result = {
            "emotion": emotion,
            "waveform": {
                "channels": {"signal": waveform_list},
                "sample_rate_hz": sample_rate
            },
            "timestamp": time.time(),
            "duration": duration,
            "band_powers": {
                "delta": config.get("delta", 0.5),
                "theta": config.get("theta", 0.5),
                "alpha": config.get("alpha", 0.5),
                "beta": config.get("beta", 0.5),
                "gamma": config.get("gamma", 0.5)
            }
        }
        
        logger.info(f"Generated EEG waveform for emotion: {emotion}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to generate EEG waveform for emotion {emotion}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成脑电波形失败: {str(e)}")


@router.get("/eeg/face-waveform/{emotion}")
async def get_face_emotion_waveform(
    emotion: str,
    duration: float = 5.0,
    sample_rate: int = 250,
) -> dict:
    """
    根据面部情绪生成对应的脑电波形数据，整合训练数据信息
    
    Args:
        emotion: 面部情绪类型 (happy, sad, neutral, angry, surprise, fear, disgust)
        duration: 波形持续时间(秒)
        sample_rate: 采样率(Hz)
    
    Returns:
        {
            "emotion": "情绪类型",
            "waveform": {
                "channels": {"signal": [波形数据点]},
                "sample_rate_hz": 采样率
            },
            "timestamp": "时间戳",
            "training_data": {
                "info": {...},
                "recent_emotions": [...]
            }
        }
    """
    try:
        eeg_waveform_service = get_eeg_waveform_service()
        result = eeg_waveform_service.get_waveform_from_face_emotion(emotion, duration, sample_rate)
        
        logger.info(f"Generated face-based EEG waveform for emotion: {emotion}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to generate face-based EEG waveform for emotion {emotion}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成面部情绪脑电波形失败: {str(e)}")


# Real EEG device endpoints
@router.post("/eeg/real/connect")
async def connect_real_eeg_device(
    device_type: str = "serial",
    port: str = "COM3",
    baudrate: int = 115200,
    simulate: bool = False
) -> dict:
    """连接真实脑电设备"""
    try:
        real_eeg_processor = get_real_eeg_processor()
        
        if simulate:
            device_id = await real_eeg_processor.connect_simulated_device()
            return {
                "status": "connected",
                "device_id": device_id,
                "message": f"已连接模拟EEG设备 (ID: {device_id})"
            }
        
        if device_type == "serial":
            device_id = await real_eeg_processor.connect_serial_device(port, baudrate)
        elif device_type == "bluetooth":
            device_id = await real_eeg_processor.connect_bluetooth_device(port)
        else:
            raise ValueError(f"不支持的设备类型: {device_type}")
        
        return {
            "status": "connected",
            "device_id": device_id,
            "message": f"已连接{device_type} EEG设备 (ID: {device_id})"
        }
        
    except Exception as e:
        logger.error(f"Failed to connect EEG device: {e}", exc_info=True)
        return {
            "status": "error",
            "device_id": None,
            "message": f"连接EEG设备失败: {str(e)}"
        }


@router.post("/eeg/real/disconnect")
async def disconnect_real_eeg_device(device_id: str = None) -> dict:
    """断开脑电设备连接"""
    try:
        real_eeg_processor = get_real_eeg_processor()
        
        if device_id:
            await real_eeg_processor.disconnect_device(device_id)
            message = f"已断开EEG设备 (ID: {device_id})"
        else:
            await real_eeg_processor.disconnect_all()
            message = "已断开所有EEG设备"
        
        return {
            "status": "disconnected",
            "message": message
        }
        
    except Exception as e:
        logger.error(f"Failed to disconnect EEG device: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"断开EEG设备失败: {str(e)}"
        }


@router.get("/eeg/real/status")
async def get_real_eeg_status() -> dict:
    """获取真实脑电设备状态"""
    try:
        real_eeg_processor = get_real_eeg_processor()
        devices = await real_eeg_processor.get_device_status()
        is_streaming = await real_eeg_processor.is_streaming()
        latest_emotion = await real_eeg_processor.get_latest_emotion()
        
        return {
            "connected_devices": devices,
            "is_streaming": is_streaming,
            "latest_emotion": latest_emotion
        }
        
    except Exception as e:
        logger.error(f"Failed to get EEG status: {e}", exc_info=True)
        return {
            "connected_devices": [],
            "is_streaming": False,
            "latest_emotion": None,
            "error": str(e)
        }


@router.post("/eeg/real/start")
async def start_real_eeg_stream(
    device_id: str = None,
    buffer_size: int = 1000
) -> dict:
    """开始从真实脑电设备接收数据流"""
    try:
        real_eeg_processor = get_real_eeg_processor()
        
        if not device_id:
            devices = await real_eeg_processor.get_device_status()
            if not devices:
                raise ValueError("没有可用的EEG设备")
            device_id = devices[0]["id"]
        
        await real_eeg_processor.start_streaming(device_id, buffer_size)
        
        return {
            "status": "streaming",
            "device_id": device_id,
            "sample_rate": 250,
            "channels": 8,
            "message": f"已开始从设备 {device_id} 接收EEG数据流"
        }
        
    except Exception as e:
        logger.error(f"Failed to start EEG stream: {e}", exc_info=True)
        return {
            "status": "error",
            "device_id": device_id,
            "sample_rate": None,
            "channels": None,
            "message": f"开始EEG数据流失败: {str(e)}"
        }


@router.post("/eeg/real/stop")
async def stop_real_eeg_stream(device_id: str = None) -> dict:
    """停止从真实脑电设备接收数据流"""
    try:
        real_eeg_processor = get_real_eeg_processor()
        
        if device_id:
            await real_eeg_processor.stop_streaming(device_id)
            message = f"已停止设备 {device_id} 的EEG数据流"
        else:
            await real_eeg_processor.stop_all_streaming()
            message = "已停止所有设备的EEG数据流"
        
        return {
            "status": "stopped",
            "message": message
        }
        
    except Exception as e:
        logger.error(f"Failed to stop EEG stream: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"停止EEG数据流失败: {str(e)}"
        }


@router.get("/eeg/real/data")
async def get_real_eeg_data(
    device_id: str = None,
    num_samples: int = 250
) -> dict:
    """获取真实脑电数据"""
    try:
        real_eeg_processor = get_real_eeg_processor()
        
        if not device_id:
            devices = await real_eeg_processor.get_device_status()
            if not devices:
                raise ValueError("没有可用的EEG设备")
            device_id = devices[0]["id"]
        
        # 获取数据
        data = await real_eeg_processor.get_latest_data(device_id, num_samples)
        
        # 分析情绪
        emotion = await real_eeg_processor.analyze_emotion(device_id)
        
        return {
            "device_id": device_id,
            "timestamp": time.time(),
            "sample_rate": 250,
            "channels": list(data.keys()) if data else [],
            "data": data,
            "emotion": emotion
        }
        
    except Exception as e:
        logger.error(f"Failed to get EEG data: {e}", exc_info=True)
        return {
            "device_id": device_id,
            "timestamp": time.time(),
            "sample_rate": None,
            "channels": [],
            "data": {},
            "emotion": None,
            "error": str(e)
        }
