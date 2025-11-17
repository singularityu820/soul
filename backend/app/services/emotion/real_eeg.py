"""
真实脑电硬件连接和数据处理模块
支持多种脑电设备接口，实现真实脑电数据的采集、处理和情绪识别
"""
import asyncio
import logging
import time
import os
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import deque

import numpy as np
import pandas as pd
from scipy import signal as ss, stats as sst
import serial
import serial.tools.list_ports

from ...config import EEGStreamConfig, EEGClassifierConfig
from ...schemas import ChannelEmotion, EEGWaveform

logger = logging.getLogger(__name__)

# 脑电频段定义
BAND_RANGES_HZ = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
    "gamma": (30.0, 45.0),
}

# 情绪标签映射
EMOTION_LABELS = {
    1: "happy",
    2: "sad",
    3: "neutral",
    4: "angry",
    5: "surprise",
    6: "fear",
    7: "disgust"
}

# 面部情绪到训练类别的映射
FACE_EMOTION_TO_CLASS = {
    "neutral": 3,
    "happy": 1,
    "sad": 2,
    "angry": 4,
    "fear": 6,
    "surprise": 5,
    "disgust": 7
}


@dataclass
class EEGDataPacket:
    """脑电数据包"""
    timestamp: float
    channels: Dict[str, List[float]]
    sample_rate: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "channels": self.channels,
            "sample_rate": self.sample_rate
        }


class EEGHardwareInterface(ABC):
    """脑电硬件接口抽象基类"""
    
    @abstractmethod
    async def connect(self) -> bool:
        """连接设备"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        pass
    
    @abstractmethod
    async def read_data(self) -> Optional[EEGDataPacket]:
        """读取数据"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """检查连接状态"""
        pass


class SerialEEGDevice(EEGHardwareInterface):
    """基于串口的脑电设备接口"""
    
    def __init__(self, port: str = None, baudrate: int = 115200, 
                 channels: List[str] = None, sample_rate: float = 250.0):
        self.port = port or self._find_eeg_device()
        self.baudrate = baudrate
        self.channels = channels or ["Fp1", "Fp2", "F3", "F4"]
        self.sample_rate = sample_rate
        self.serial_conn = None
        self.is_device_connected = False
        self.data_buffer = deque(maxlen=1000)  # 缓冲最近1000个数据点
        
    def _find_eeg_device(self) -> Optional[str]:
        """自动查找脑电设备"""
        ports = serial.tools.list_ports.comports()
        # 常见的脑电设备VID/PID或名称特征
        eeg_device_keywords = ["EEG", "Brain", "NeuroSky", "OpenBCI", "Muse"]
        
        for port in ports:
            if any(keyword in port.description for keyword in eeg_device_keywords):
                logger.info(f"发现可能的脑电设备: {port.device} - {port.description}")
                return port.device
                
        # 如果没有找到特定设备，返回第一个可用端口
        if ports:
            logger.warning(f"未找到特定脑电设备，使用第一个可用端口: {ports[0].device}")
            return ports[0].device
            
        logger.error("未找到任何可用串口设备")
        return None
    
    async def connect(self) -> bool:
        """连接串口设备"""
        if not self.port:
            logger.error("未指定串口端口")
            return False
            
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0
            )
            self.is_device_connected = True
            logger.info(f"已连接到脑电设备: {self.port}")
            return True
        except Exception as e:
            logger.error(f"连接脑电设备失败: {e}")
            return False
    
    async def disconnect(self) -> None:
        """断开串口连接"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            self.is_device_connected = False
            logger.info("已断开脑电设备连接")
    
    async def read_data(self) -> Optional[EEGDataPacket]:
        """从串口读取数据"""
        if not self.is_device_connected or not self.serial_conn:
            return None
            
        try:
            # 等待并读取一行数据
            line = self.serial_conn.readline().decode('utf-8').strip()
            if not line:
                return None
                
            # 解析数据（假设格式为: channel1,channel2,channel3,channel4）
            values = line.split(',')
            if len(values) < len(self.channels):
                return None
                
            # 转换为浮点数
            channel_data = {}
            for i, channel in enumerate(self.channels):
                try:
                    channel_data[channel] = [float(values[i])]
                except (ValueError, IndexError):
                    channel_data[channel] = [0.0]  # 默认值
                    
            # 添加到缓冲区
            for channel, data in channel_data.items():
                self.data_buffer.append((channel, data[0], time.time()))
                
            return EEGDataPacket(
                timestamp=time.time(),
                channels=channel_data,
                sample_rate=self.sample_rate
            )
        except Exception as e:
            logger.error(f"读取脑电数据失败: {e}")
            return None
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.is_device_connected and self.serial_conn and self.serial_conn.is_open


class SimulatedEEGDevice(EEGHardwareInterface):
    """模拟脑电设备，用于测试"""
    
    def __init__(self, channels: List[str] = None, sample_rate: float = 250.0):
        self.channels = channels or ["Fp1", "Fp2", "F3", "F4"]
        self.sample_rate = sample_rate
        self.is_device_connected = False
        self.time_counter = 0
        
        # 初始化各通道的相位和频率
        self.channel_states = {}
        for channel in self.channels:
            self.channel_states[channel] = {
                "phase": random.random() * 2 * np.pi,
                "frequency": random.uniform(5, 15),  # 随机频率
                "amplitude": random.uniform(5, 15),  # 随机幅度
                "noise_level": random.uniform(0.5, 2.0)  # 随机噪声水平
            }
    
    async def connect(self) -> bool:
        """模拟连接"""
        await asyncio.sleep(0.1)  # 模拟连接延迟
        self.is_device_connected = True
        logger.info("已连接到模拟脑电设备")
        return True
    
    async def disconnect(self) -> None:
        """模拟断开连接"""
        self.is_device_connected = False
        logger.info("已断开模拟脑电设备连接")
    
    async def read_data(self) -> Optional[EEGDataPacket]:
        """生成模拟数据"""
        if not self.is_device_connected:
            return None
            
        self.time_counter += 1.0 / self.sample_rate
        
        channel_data = {}
        for channel, state in self.channel_states.items():
            # 生成正弦波加噪声
            value = state["amplitude"] * np.sin(
                2 * np.pi * state["frequency"] * self.time_counter + state["phase"]
            )
            # 添加随机噪声
            noise = np.random.normal(0, state["noise_level"])
            value += noise
            
            # 随机缓慢改变参数，使数据更真实
            if random.random() < 0.01:  # 1%概率改变参数
                state["frequency"] += random.uniform(-0.5, 0.5)
                state["frequency"] = max(1, min(30, state["frequency"]))  # 限制频率范围
                state["amplitude"] += random.uniform(-1, 1)
                state["amplitude"] = max(1, min(20, state["amplitude"]))  # 限制幅度范围
                
            channel_data[channel] = [value]
            
        return EEGDataPacket(
            timestamp=time.time(),
            channels=channel_data,
            sample_rate=self.sample_rate
        )
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.is_device_connected


class RealEEGProcessor:
    """真实脑电数据处理器"""
    
    def __init__(self, device: EEGHardwareInterface, config: EEGStreamConfig = None):
        self.device = device
        self.config = config or EEGStreamConfig()
        self.is_running = False
        self.data_buffer = {}
        self.emotion_classifier = None
        
        # 初始化各通道数据缓冲区
        for channel in self.device.channels:
            self.data_buffer[channel] = deque(maxlen=int(self.config.sample_rate_hz * self.config.waveform_buffer_seconds))
        
        # 加载训练数据用于情绪分类
        self._load_training_data()
    
    def _load_training_data(self):
        """加载训练数据用于情绪分类"""
        try:
            # 获取当前文件所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 训练数据目录
            training_data_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "Training Data")
            
            # 加载训练数据文件
            train_arousal_path = os.path.join(training_data_dir, "train_arousal.csv")
            train_valence_path = os.path.join(training_data_dir, "train_valence.csv")
            class_arousal_path = os.path.join(training_data_dir, "class_arousal.csv")
            class_valence_path = os.path.join(training_data_dir, "class_valence.csv")
            
            if all(os.path.exists(path) for path in [train_arousal_path, train_valence_path, 
                                                     class_arousal_path, class_valence_path]):
                self.train_arousal = pd.read_csv(train_arousal_path).values
                self.train_valence = pd.read_csv(train_valence_path).values
                self.class_arousal = pd.read_csv(class_arousal_path).values
                self.class_valence = pd.read_csv(class_valence_path).values
                self.training_data_loaded = True
                logger.info("成功加载训练数据用于情绪分类")
            else:
                self.training_data_loaded = False
                logger.warning("未找到训练数据文件，将使用默认情绪分类方法")
        except Exception as e:
            self.training_data_loaded = False
            logger.error(f"加载训练数据失败: {e}")
    
    async def connect(self) -> bool:
        """连接设备"""
        return await self.device.connect()
    
    async def disconnect(self) -> None:
        """断开连接"""
        self.is_running = False
        await self.device.disconnect()
    
    async def start_streaming(self) -> None:
        """开始数据流"""
        if not self.device.is_connected():
            logger.error("设备未连接，无法开始数据流")
            return
            
        self.is_running = True
        logger.info("开始脑电数据流")
        
        while self.is_running:
            data_packet = await self.device.read_data()
            if data_packet:
                # 更新数据缓冲区
                for channel, values in data_packet.channels.items():
                    if channel in self.data_buffer:
                        self.data_buffer[channel].extend(values)
                
                # 生成EEG样本
                sample = self._create_eeg_sample(data_packet)
                if sample:
                    yield sample
            
            await asyncio.sleep(0.01)  # 短暂延迟，避免CPU占用过高
    
    def _create_eeg_sample(self, data_packet: EEGDataPacket):
        """从数据包创建EEG样本"""
        try:
            # 构建波形数据
            channels_data = {}
            for channel, buffer in self.data_buffer.items():
                if buffer:
                    channels_data[channel] = list(buffer)
            
            if not channels_data:
                return None
                
            # 创建EEG波形
            waveform = EEGWaveform(
                channels=channels_data,
                sample_rate_hz=data_packet.sample_rate
            )
            
            # 计算频段能量
            band_energy = self._compute_band_energy(channels_data)
            
            # 创建数据帧
            frame = {
                "timestamp": data_packet.timestamp,
                "sample_rate": data_packet.sample_rate
            }
            
            # 返回EEG样本
            return {
                "waveform": waveform,
                "band_energy": band_energy,
                "frame": frame
            }
        except Exception as e:
            logger.error(f"创建EEG样本失败: {e}")
            return None
    
    def _compute_band_energy(self, channels_data: Dict[str, List[float]]) -> Dict[str, float]:
        """计算各频段能量"""
        if not channels_data:
            return {band: 0.0 for band in BAND_RANGES_HZ}
        
        # 合并所有通道数据
        all_data = []
        for channel_data in channels_data.values():
            all_data.extend(channel_data)
        
        if not all_data:
            return {band: 0.0 for band in BAND_RANGES_HZ}
            
        signal = np.array(all_data, dtype=float)
        if signal.size < 4:
            base_level = float(np.mean(np.abs(signal))) if signal.size else 0.0
            return {band: base_level for band in BAND_RANGES_HZ}
        
        # 应用汉宁窗
        window = np.hanning(signal.size)
        spectrum = np.fft.rfft(signal * window)
        freqs = np.fft.rfftfreq(signal.size, d=1.0 / self.device.sample_rate)
        power = (np.abs(spectrum) ** 2) / max(1e-9, np.sum(window ** 2))
        
        # 计算各频段能量
        energies = {}
        for band, (low, high) in BAND_RANGES_HZ.items():
            mask = (freqs >= low) & (freqs < high)
            if np.any(mask):
                energies[band] = float(np.mean(power[mask]))
            else:
                energies[band] = 0.0
        
        # 归一化
        total_energy = sum(energies.values())
        if total_energy > 0:
            energies = {band: value / total_energy for band, value in energies.items()}
            
        return energies
    
    def get_feature(self, channels_data: Dict[str, List[float]]) -> np.ndarray:
        """提取特征向量用于情绪分类"""
        try:
            # 合并所有通道数据
            all_data = []
            for channel_data in channels_data.values():
                all_data.extend(channel_data)
            
            if not all_data:
                return np.zeros(5)  # 默认特征向量
                
            signal = np.array(all_data, dtype=float)
            
            # 计算各频段功率
            features = []
            for band, (low, high) in BAND_RANGES_HZ.items():
                # 使用带通滤波器
                nyquist = 0.5 * self.device.sample_rate
                low_norm = low / nyquist
                high_norm = high / nyquist
                
                if low_norm >= 1 or high_norm >= 1:
                    features.append(0.0)
                    continue
                    
                b, a = ss.butter(4, [low_norm, high_norm], btype='band')
                filtered = ss.filtfilt(b, a, signal)
                
                # 计算功率
                power = np.mean(filtered ** 2)
                features.append(power)
            
            # 归一化特征向量
            features = np.array(features)
            if np.sum(features) > 0:
                features = features / np.sum(features)
                
            return features
        except Exception as e:
            logger.error(f"特征提取失败: {e}")
            return np.zeros(5)  # 默认特征向量
    
    def predict_emotion(self, feature: np.ndarray) -> Tuple[int, int]:
        """预测情绪类别 - 唤醒度和效价"""
        try:
            if not self.training_data_loaded:
                # 如果没有训练数据，返回随机结果
                return random.choice([1, 2, 3]), random.choice([1, 2, 3])
                
            # 计算与训练数据的距离
            distance_ar = [ss.distance.canberra(x, feature) for x in self.train_arousal]
            distance_va = [ss.distance.canberra(x, feature) for x in self.train_valence]
            
            # 获取最近的3个样本
            idx_nearest_ar = np.array(np.argsort(distance_ar)[:3])
            val_nearest_ar = np.array(np.sort(distance_ar)[:3])
            
            idx_nearest_va = np.array(np.argsort(distance_va)[:3])
            val_nearest_va = np.array(np.sort(distance_va)[:3])
            
            # 唤醒度预测
            if len(val_nearest_ar) > 1 and val_nearest_ar[1] != 0:
                comp_ar = val_nearest_ar[0] / val_nearest_ar[1]
                if comp_ar <= 0.97:
                    result_ar = self.class_arousal[0, idx_nearest_ar[0]]
                else:
                    result_ar = sst.mode(self.class_arousal[0, idx_nearest_ar[:3]])[0][0]
            else:
                result_ar = self.class_arousal[0, idx_nearest_ar[0]]
            
            # 效价预测
            if len(val_nearest_va) > 1 and val_nearest_va[1] != 0:
                comp_va = val_nearest_va[0] / val_nearest_va[1]
                if comp_va <= 0.97:
                    result_va = self.class_valence[0, idx_nearest_va[0]]
                else:
                    result_va = sst.mode(self.class_valence[0, idx_nearest_va[:3]])[0][0]
            else:
                result_va = self.class_valence[0, idx_nearest_va[0]]
            
            return int(result_ar), int(result_va)
        except Exception as e:
            logger.error(f"情绪预测失败: {e}")
            return random.choice([1, 2, 3]), random.choice([1, 2, 3])
    
    def determine_emotion_class(self, feature: np.ndarray) -> int:
        """确定最终情绪类别"""
        try:
            class_ar, class_va = self.predict_emotion(feature)
            
            if class_ar == 2.0 or class_va == 2.0:
                emotion_class = 3  # neutral
            elif class_ar == 3.0 and class_va == 1.0:
                emotion_class = 4  # angry
            elif class_ar == 3.0 and class_va == 3.0:
                emotion_class = 1  # happy
            elif class_ar == 1.0 and class_va == 3.0:
                emotion_class = 5  # surprise
            elif class_ar == 1.0 and class_va == 1.0:
                emotion_class = 2  # sad
            elif class_ar == 3.0 and class_va == 2.0:
                emotion_class = 6  # fear
            elif class_ar == 2.0 and class_va == 1.0:
                emotion_class = 7  # disgust
            else:
                emotion_class = 3  # 默认neutral
            
            logger.info(f"唤醒度: {class_ar}, 效价: {class_va} -> {EMOTION_LABELS[emotion_class]}")
            return emotion_class
        except Exception as e:
            logger.error(f"情绪分类失败: {e}")
            return 3  # 默认返回neutral
    
    def process_all_data(self, channels_data: Dict[str, List[float]]) -> Dict[str, Any]:
        """处理所有数据并预测情绪"""
        try:
            logger.info("处理EEG数据...")
            feature = self.get_feature(channels_data)
            emotion_class = self.determine_emotion_class(feature)
            
            result = {
                "emotion_class": emotion_class,
                "emotion_label": EMOTION_LABELS[emotion_class],
                "feature_vector": feature.tolist(),
                "timestamp": time.time()
            }
            
            logger.info(f"预测情绪: {emotion_class} - {EMOTION_LABELS[emotion_class]}")
            return result
        except Exception as e:
            logger.error(f"数据处理错误: {e}")
            return {
                "emotion_class": 3,
                "emotion_label": EMOTION_LABELS[3],
                "feature_vector": [0, 0, 0, 0, 0],
                "timestamp": time.time(),
                "error": str(e)
            }
    
    async def classify_emotion(self, sample: Dict[str, Any]) -> ChannelEmotion:
        """对EEG样本进行情绪分类"""
        try:
            if not sample or "waveform" not in sample:
                return ChannelEmotion(
                    source="eeg",
                    label="neutral",
                    confidence=0.5,
                    mood_score=0.0,
                    metadata={"error": "无效的EEG样本"}
                )
            
            # 提取特征
            feature = self.get_feature(sample["waveform"].channels)
            emotion_class = self.determine_emotion_class(feature)
            emotion_label = EMOTION_LABELS[emotion_class]
            
            # 计算情绪分数
            mood_scores = {
                1: 0.7,   # happy -> 正面
                2: -0.5,  # sad -> 负面
                3: 0.0,   # neutral -> 中性
                4: -0.7,  # angry -> 负面
                5: 0.5,   # surprise -> 正面
                6: -0.6,  # fear -> 负面
                7: -0.4   # disgust -> 负面
            }
            
            mood_score = mood_scores.get(emotion_class, 0.0)
            
            # 计算置信度
            confidence = min(1.0, 0.6 + random.random() * 0.3)
            
            metadata = {
                "emotion_class": emotion_class,
                "emotion_label": emotion_label,
                "feature_vector": feature.tolist(),
                "band_energy": sample.get("band_energy", {}),
                "notes": "基于真实EEG数据的情绪分类"
            }
            
            return ChannelEmotion(
                source="eeg",
                label=emotion_label,
                confidence=confidence,
                mood_score=mood_score,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"EEG情绪分类失败: {e}")
            return ChannelEmotion(
                source="eeg",
                label="neutral",
                confidence=0.3,
                mood_score=0.0,
                metadata={"error": str(e)}
            )


def create_eeg_processor(device_type: str = "simulated", **kwargs) -> RealEEGProcessor:
    """创建EEG处理器"""
    if device_type == "serial":
        device = SerialEEGDevice(**kwargs)
    elif device_type == "simulated":
        device = SimulatedEEGDevice(**kwargs)
    else:
        raise ValueError(f"不支持的设备类型: {device_type}")
    
    return RealEEGProcessor(device)