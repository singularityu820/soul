"""
EEG波形生成服务
"""
import logging
import time
import math
import random
import os
import datetime
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

class EEGWaveformService:
    """EEG波形生成服务，根据情绪生成对应的脑电波形数据"""
    
    def __init__(self):
        # 训练数据路径
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.training_data_dir = os.path.join(self.current_dir, "..", "..", "..", "Training Data")
        
        # 训练数据文件路径
        self.train_arousal_path = os.path.join(self.training_data_dir, "train_arousal.csv")
        self.train_valence_path = os.path.join(self.training_data_dir, "train_valence.csv")
        self.class_arousal_path = os.path.join(self.training_data_dir, "class_arousal.csv")
        self.class_valence_path = os.path.join(self.training_data_dir, "class_valence.csv")
        
        # 初始化训练数据状态
        self.training_data_loaded = False
        self.train_arousal_data = None
        self.train_valence_data = None
        self.class_arousal_data = None
        self.class_valence_data = None
        
        # 加载训练数据
        self.load_training_data()
    
    def load_training_data(self):
        """加载训练数据"""
        try:
            # 验证文件存在
            for path in [self.train_arousal_path, self.train_valence_path,
                         self.class_arousal_path, self.class_valence_path]:
                if not os.path.exists(path):
                    logger.error(f"训练数据文件不存在: {path}")
                    self.training_data_loaded = False
                    return

            # 加载训练数据
            self.train_arousal_data = pd.read_csv(self.train_arousal_path, header=None)
            self.train_valence_data = pd.read_csv(self.train_valence_path, header=None)
            self.class_arousal_data = pd.read_csv(self.class_arousal_path, header=None).values.flatten()
            self.class_valence_data = pd.read_csv(self.class_valence_path, header=None).values.flatten()
            
            self.training_data_loaded = True
            logger.info("训练数据加载成功")
            
        except Exception as e:
            logger.error(f"加载训练数据失败: {e}")
            self.training_data_loaded = False
    
    def map_face_emotion_to_training_class(self, emotion: str) -> int:
        """
        将面部情绪映射到训练数据中的类别
        
        Args:
            emotion: 面部情绪类型 (neutral, happy, sad, angry, fear, surprise, disgust)
            
        Returns:
            训练数据中的情绪类别索引
        """
        # 将面部情绪映射到训练数据中的类别
        # 基于唤醒度和效价进行映射
        emotion_mapping = {
            "neutral": 5,      # 中性
            "happy": 2,        # 高唤醒-高效价
            "sad": 4,          # 低唤醒-低效价
            "angry": 1,        # 高唤醒-低效价
            "fear": 3,         # 高唤醒-低效价
            "surprise": 1,     # 高唤醒-中等效价
            "disgust": 1       # 中等唤醒-低效价
        }
        return emotion_mapping.get(emotion, 5)  # 默认返回中性
    def generate_waveform(self, emotion: str, duration: float = 5.0, sample_rate: int = 250) -> Dict[str, Any]:
        """
        根据情绪生成对应的脑电波形数据，基于真实训练数据
        
        Args:
            emotion: 情绪类型 (neutral, happy, sad, angry, fear, surprise, disgust)
            duration: 波形持续时间(秒)
            sample_rate: 采样率(Hz)
        
        Returns:
            包含波形数据的字典
        """
        try:
            # 验证情绪类型
            valid_emotions = ["neutral", "happy", "sad", "angry", "fear", "surprise", "disgust"]
            if emotion not in valid_emotions:
                raise ValueError(f"Unsupported emotion: {emotion}. Supported emotions: {valid_emotions}")
            
            # 计算采样点数
            num_samples = int(duration * sample_rate)
            
            # 创建时间轴
            t = np.linspace(0, duration, num_samples)
            
            # 初始化波形数据
            waveform_data = np.zeros(num_samples)
            
            # 如果训练数据加载成功，使用真实数据生成波形
            if self.training_data_loaded:
                # 映射面部情绪到训练数据类别
                emotion_class = self.map_face_emotion_to_training_class(emotion)
                
                # 从训练数据中获取对应的样本
                # 随机选择一个属于该情绪类别的样本
                matching_indices = np.where(self.class_valence_data == emotion_class)[0]
                
                if len(matching_indices) > 0:
                    # 随机选择一个匹配的样本
                    sample_idx = np.random.choice(matching_indices)
                    
                    # 获取该样本的EEG特征数据
                    eeg_features = self.train_valence_data.iloc[sample_idx].values
                    
                    # 将EEG特征转换为波形
                    # 使用特征作为不同频段的权重
                    delta_weight = eeg_features[0] if len(eeg_features) > 0 else 0.5
                    theta_weight = eeg_features[1] if len(eeg_features) > 1 else 0.5
                    alpha_weight = eeg_features[2] if len(eeg_features) > 2 else 0.5
                    beta_weight = eeg_features[3] if len(eeg_features) > 3 else 0.5
                    gamma_weight = eeg_features[4] if len(eeg_features) > 4 else 0.5
                    
                    # 归一化权重到[0.1, 1.0]范围
                    def normalize_weight(w):
                        return max(0.1, min(1.0, abs(w)))
                    
                    delta_weight = normalize_weight(delta_weight)
                    theta_weight = normalize_weight(theta_weight)
                    alpha_weight = normalize_weight(alpha_weight)
                    beta_weight = normalize_weight(beta_weight)
                    gamma_weight = normalize_weight(gamma_weight)
                    
                    # 生成不同频段的脑电波
                    # δ波 (0.5-4 Hz): 深度睡眠，无意识状态
                    delta = 0.5 * np.sin(2 * np.pi * 2 * t) * delta_weight
                    
                    # θ波 (4-8 Hz): 放松，创造性思维，冥想
                    theta = 0.5 * np.sin(2 * np.pi * 6 * t) * theta_weight
                    
                    # α波 (8-13 Hz): 放松但清醒，闭眼休息状态
                    alpha = 0.5 * np.sin(2 * np.pi * 10 * t) * alpha_weight
                    
                    # β波 (13-30 Hz): 警觉，专注，活跃思考
                    beta = 0.5 * np.sin(2 * np.pi * 20 * t) * beta_weight
                    
                    # γ波 (30-45 Hz): 高级认知处理，记忆，学习
                    gamma = 0.5 * np.sin(2 * np.pi * 40 * t) * gamma_weight
                    
                    # 合成波形
                    waveform_data = delta + theta + alpha + beta + gamma
                    
                    # 添加一些基于训练数据的噪声
                    if len(eeg_features) > 5:
                        noise_level = min(0.1, abs(eeg_features[5]) * 0.05)
                    else:
                        noise_level = 0.05
                    
                    noise = np.random.normal(0, noise_level, num_samples)
                    waveform_data += noise
                    
                    # 计算频段功率
                    band_powers = {
                        "delta": delta_weight,
                        "theta": theta_weight,
                        "alpha": alpha_weight,
                        "beta": beta_weight,
                        "gamma": gamma_weight
                    }
                else:
                    # 如果没有找到匹配的样本，使用默认值
                    logger.warning(f"No matching samples found for emotion {emotion}, using default values")
                    waveform_data, band_powers = self._generate_default_waveform(emotion, t)
            else:
                # 如果训练数据未加载，使用默认值
                logger.warning("Training data not loaded, using default waveform generation")
                waveform_data, band_powers = self._generate_default_waveform(emotion, t)
            
            # 归一化到[-1, 1]范围
            waveform_data = np.clip(waveform_data, -1, 1)
            
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
                "band_powers": band_powers,
                "data_source": "real_training_data" if self.training_data_loaded else "synthetic"
            }
            
            logger.info(f"Generated EEG waveform for emotion: {emotion}, data source: {result['data_source']}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate EEG waveform for emotion {emotion}: {e}", exc_info=True)
            raise
    
    def _generate_default_waveform(self, emotion: str, t: np.ndarray) -> tuple:
        """
        生成默认的脑电波形（当训练数据不可用时）
        
        Args:
            emotion: 情绪类型
            t: 时间轴
            
        Returns:
            (waveform_data, band_powers) 元组
        """
        # 默认频段权重，基于脑电波研究，与DeepFace情绪分类一致
        default_band_powers = {
            "neutral": {"delta": 0.3, "theta": 0.5, "alpha": 0.6, "beta": 0.5, "gamma": 0.4},
            "happy": {"delta": 0.2, "theta": 0.4, "alpha": 0.7, "beta": 0.8, "gamma": 0.7},
            "sad": {"delta": 0.4, "theta": 0.7, "alpha": 0.8, "beta": 0.3, "gamma": 0.2},
            "angry": {"delta": 0.2, "theta": 0.3, "alpha": 0.3, "beta": 0.9, "gamma": 0.8},
            "surprise": {"delta": 0.2, "theta": 0.4, "alpha": 0.5, "beta": 0.7, "gamma": 0.9},
            "fear": {"delta": 0.2, "theta": 0.6, "alpha": 0.4, "beta": 0.8, "gamma": 0.6},
            "disgust": {"delta": 0.3, "theta": 0.5, "alpha": 0.6, "beta": 0.7, "gamma": 0.5}
        }
        
        # 获取情绪对应的频段权重
        band_weights = default_band_powers.get(emotion, default_band_powers["neutral"])
        
        # 生成不同频段的脑电波
        delta = 0.5 * np.sin(2 * np.pi * 2 * t) * band_weights["delta"]
        theta = 0.5 * np.sin(2 * np.pi * 6 * t) * band_weights["theta"]
        alpha = 0.5 * np.sin(2 * np.pi * 10 * t) * band_weights["alpha"]
        beta = 0.5 * np.sin(2 * np.pi * 20 * t) * band_weights["beta"]
        gamma = 0.5 * np.sin(2 * np.pi * 40 * t) * band_weights["gamma"]
        
        # 合成波形
        waveform_data = delta + theta + alpha + beta + gamma
        
        # 添加噪声
        noise = np.random.normal(0, 0.05, len(t))
        waveform_data += noise
        
        return waveform_data, band_weights
    
    def __init__(self):
        # 训练数据路径
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.training_data_dir = os.path.join(self.current_dir, "..", "..", "..", "Training Data")
        
        # 训练数据文件路径
        self.train_arousal_path = os.path.join(self.training_data_dir, "train_arousal.csv")
        self.train_valence_path = os.path.join(self.training_data_dir, "train_valence.csv")
        self.class_arousal_path = os.path.join(self.training_data_dir, "class_arousal.csv")
        self.class_valence_path = os.path.join(self.training_data_dir, "class_valence.csv")
        
        # 初始化训练数据状态
        self.training_data_loaded = False
        self.train_arousal_data = None
        self.train_valence_data = None
        self.class_arousal_data = None
        self.class_valence_data = None
        
        # 情绪历史记录
        self.emotion_history: List[Dict[str, Any]] = []
        
        # 加载训练数据
        self.load_training_data()
    
    def get_waveform_from_face_emotion(self, emotion: str, duration: float = 5.0, sample_rate: int = 250) -> Dict[str, Any]:
        """
        根据面部情绪生成脑电波形数据
        
        Args:
            emotion: 面部情绪类型
            duration: 波形持续时间（秒）
            sample_rate: 采样率（Hz）
            
        Returns:
            包含波形数据和元数据的字典
        """
        try:
            # 生成脑电波形
            waveform_result = self.generate_waveform(emotion, duration, sample_rate)
            
            # 添加时间戳
            timestamp = datetime.datetime.now().isoformat()
            
            # 记录情绪历史
            emotion_record = {
                "timestamp": timestamp,
                "emotion": emotion,
                "data_source": waveform_result["data_source"],
                "duration": duration,
                "sample_rate": sample_rate
            }
            self.emotion_history.append(emotion_record)
            
            # 更新返回结果
            waveform_result["timestamp"] = timestamp
            waveform_result["emotion_history"] = self.emotion_history[-5:]  # 只保留最近5条记录
            
            return waveform_result
            
        except Exception as e:
            logger.error(f"Failed to get waveform from face emotion {emotion}: {e}", exc_info=True)
            raise
    
    def get_training_data_info(self) -> Dict[str, Any]:
        """
        获取训练数据信息
        
        Returns:
            训练数据信息字典
        """
        return self.training_data_info
    
    def get_emotion_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的情绪历史记录
        
        Args:
            limit: 返回的记录数量限制
        
        Returns:
            情绪历史记录列表
        """
        return self.emotion_history[-limit:] if self.emotion_history else []