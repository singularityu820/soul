from __future__ import annotations

import asyncio
import logging
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional

import numpy as np

from ...config import EEGClassifierConfig, EEGStreamConfig
from ...schemas import ChannelEmotion, EEGWaveform

logger = logging.getLogger(__name__)

BAND_FREQUENCIES_HZ: Dict[str, float] = {
    "delta": 2.0,
    "theta": 6.0,
    "alpha": 10.0,
    "beta": 18.0,
    "gamma": 35.0,
}

BAND_WEIGHTS: Dict[str, float] = {
    "delta": 1.0,
    "theta": 0.8,
    "alpha": 0.6,
    "beta": 0.45,
    "gamma": 0.35,
}

BAND_RANGES_HZ: Dict[str, tuple[float, float]] = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
    "gamma": (30.0, 45.0),
}

ERROR_SENTINEL = "_undefine"


@dataclass(slots=True)
class BCIDataFrame:
    serial_number: int
    page_timestamp: float
    page_time_length: float
    sample_size: int
    point_timestamp: List[float]
    point_data: List[float]
    error_data: str = ERROR_SENTINEL

    def to_payload(self) -> Dict[str, Any]:
        return {
            "serial_number": self.serial_number,
            "page_timestamp": self.page_timestamp,
            "page_time_length": self.page_time_length,
            "sample_size": self.sample_size,
            "point_timestamp": list(self.point_timestamp),
            "point_data": list(self.point_data),
            "error_data": self.error_data,
        }


@dataclass(slots=True)
class EEGSample:
    waveform: EEGWaveform
    band_energy: Dict[str, float]
    frame: BCIDataFrame


class EEGStreamTool:
    """Generates EEG frames that mirror the documented BCI interface payload."""

    def __init__(self, config: EEGStreamConfig | None = None) -> None:
        self.config = config or EEGStreamConfig()
        buffer_capacity = max(
            1,
            int(round(self.config.sample_rate_hz * self.config.waveform_buffer_seconds)),
        )
        self._buffer: Deque[float] = deque(maxlen=buffer_capacity)
        self._rng = random.Random()
        self._serial = 0
        self._last_point_timestamp = 0.0
        amp_min_raw, amp_max_raw = self.config.amplitude_range
        self._amp_min = min(abs(amp_min_raw), abs(amp_max_raw))
        self._amp_max = max(abs(amp_min_raw), abs(amp_max_raw))
        self._noise_sigma = max(1e-3, (self._amp_max - self._amp_min) * 0.03)
        self._time_step_ms = 1000.0 / self.config.sample_rate_hz
        self._band_state: Dict[str, Dict[str, float]] = {
            band: {
                "phase": self._rng.random() * math.tau,
                "amplitude": self._random_amplitude(),
            }
            for band in BAND_FREQUENCIES_HZ
        }

    async def sample(self) -> EEGSample:
        await asyncio.sleep(self.config.update_interval)
        frame = self._simulate_frame()
        if frame.error_data != ERROR_SENTINEL:
            logger.warning("EEG frame reported error: %s", frame.error_data)
        self._buffer.extend(frame.point_data)
        waveform = self._build_waveform()
        band_energy = self._compute_band_energy()
        return EEGSample(waveform=waveform, band_energy=band_energy, frame=frame)

    def _simulate_frame(self) -> BCIDataFrame:
        sample_count = max(1, int(round(self.config.sample_rate_hz * self.config.update_interval)))
        timestamps: List[float] = []
        values: List[float] = []
        for _ in range(sample_count):
            self._last_point_timestamp += self._time_step_ms
            timestamps.append(self._last_point_timestamp)
            values.append(self._compose_sample())
        self._serial += 1
        return BCIDataFrame(
            serial_number=self._serial,
            page_timestamp=self._last_point_timestamp,
            page_time_length=self._time_step_ms * sample_count,
            sample_size=sample_count,
            point_timestamp=timestamps,
            point_data=values,
            error_data=ERROR_SENTINEL,
        )

    def _compose_sample(self) -> float:
        value = 0.0
        for band, state in self._band_state.items():
            phase = state["phase"]
            amplitude = state["amplitude"]
            weight = BAND_WEIGHTS.get(band, 1.0)
            value += amplitude * weight * math.sin(phase)
            state["phase"] = (phase + self._phase_increment(BAND_FREQUENCIES_HZ[band])) % math.tau
            drift = self._rng.gauss(0.0, (self._amp_max - self._amp_min) * 0.0005)
            state["amplitude"] = self._clamp_amplitude(amplitude + drift)
        value += self._rng.gauss(0.0, self._noise_sigma)
        return value

    def _phase_increment(self, frequency_hz: float) -> float:
        return 2.0 * math.pi * frequency_hz / self.config.sample_rate_hz

    def _random_amplitude(self) -> float:
        return self._rng.uniform(self._amp_min, self._amp_max)

    def _clamp_amplitude(self, value: float) -> float:
        return max(self._amp_min, min(self._amp_max, value))

    def _build_waveform(self) -> EEGWaveform:
        channel_name = self.config.channels[0] if self.config.channels else "signal"
        return EEGWaveform(
            channels={channel_name: list(self._buffer)},
            sample_rate_hz=self.config.sample_rate_hz,
        )

    def _compute_band_energy(self) -> Dict[str, float]:
        if not self._buffer:
            return {band: 0.0 for band in BAND_FREQUENCIES_HZ}
        signal = np.array(self._buffer, dtype=float)
        if signal.size < 4:
            base_level = float(np.mean(np.abs(signal))) if signal.size else 0.0
            return {band: base_level for band in BAND_FREQUENCIES_HZ}
        window = np.hanning(signal.size)
        spectrum = np.fft.rfft(signal * window)
        freqs = np.fft.rfftfreq(signal.size, d=1.0 / self.config.sample_rate_hz)
        power = (np.abs(spectrum) ** 2) / max(1e-9, np.sum(window ** 2))
        energies: Dict[str, float] = {}
        for band, (low, high) in BAND_RANGES_HZ.items():
            mask = (freqs >= low) & (freqs < high)
            if np.any(mask):
                energies[band] = float(np.mean(power[mask]))
            else:
                energies[band] = 0.0
        total_energy = sum(energies.values())
        if total_energy > 0:
            energies = {band: value / total_energy for band, value in energies.items()}
        return energies


class EEGEmotionClassifier:
    """EEG情绪分类器，支持模拟数据和真实数据"""

    def __init__(self, config: EEGClassifierConfig | None = None, use_real_data: bool = False) -> None:
        self.config = config or EEGClassifierConfig()
        self._rng = random.Random()
        self.use_real_data = use_real_data
        
        # 如果使用真实数据，初始化真实EEG处理器
        if use_real_data:
            try:
                from .real_eeg import create_eeg_processor
                self.real_eeg_processor = create_eeg_processor(device_type="simulated")
                self.training_data_loaded = False
                logger.info("已初始化真实EEG处理器")
            except ImportError as e:
                logger.error(f"导入真实EEG处理器失败: {e}")
                self.use_real_data = False
                self.real_eeg_processor = None

    async def classify(self, sample: EEGSample) -> ChannelEmotion:
        if self.use_real_data and self.real_eeg_processor:
            return await self._classify_real_data(sample)
        else:
            return await self._classify_simulated_data(sample)
    
    async def _classify_real_data(self, sample: EEGSample) -> ChannelEmotion:
        """使用真实数据分类方法"""
        try:
            # 从EEG样本中提取通道数据
            channels_data = {}
            for channel, data in sample.waveform.channels.items():
                channels_data[channel] = data
            
            # 使用真实EEG处理器进行情绪分类
            emotion_result = self.real_eeg_processor.process_all_data(channels_data)
            
            # 映射到系统使用的情绪标签（更新后的情绪映射）
            label_mapping = {
                0: "happy",
                1: "sad",
                2: "neutral",
                3: "angry",
                4: "surprise",
                5: "fear",
                6: "disgust"
            }
            
            emotion_class = emotion_result.get("emotion_class", 2)
            system_label = label_mapping.get(emotion_class, "neutral")
            
            # 计算情绪分数（更新后的情绪分数映射）
            mood_scores = {
                "happy": 0.7,
                "sad": -0.5,
                "neutral": 0.0,
                "angry": -0.7,
                "surprise": 0.5,
                "fear": -0.6,
                "disgust": -0.4
            }
            
            mood_score = mood_scores.get(system_label, 0.0)
            
            # 计算置信度
            confidence = min(1.0, 0.6 + random.random() * 0.3)
            
            metadata = {
                "emotion_class": emotion_class,
                "emotion_label": emotion_result.get("emotion_label", system_label),
                "feature_vector": emotion_result.get("feature_vector", []),
                "band_energy": sample.band_energy,
                "notes": "基于真实EEG数据的情绪分类"
            }
            
            return ChannelEmotion(
                source="eeg",
                label=system_label,
                confidence=confidence,
                mood_score=mood_score,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"真实EEG数据分类失败: {e}")
            # 降级到模拟数据分类
            return await self._classify_simulated_data(sample)
    
    async def _classify_simulated_data(self, sample: EEGSample) -> ChannelEmotion:
        """使用模拟数据分类方法（原有逻辑）"""
        features = sample.band_energy
        calm_metric = features.get("alpha", 0.0) - features.get("beta", 0.0) * 0.4
        focus_metric = features.get("beta", 0.0) - features.get("theta", 0.0) * 0.3
        stress_metric = features.get("gamma", 0.0) + features.get("beta", 0.0)
        
        # 计算各频段相对功率
        total_power = sum(features.values()) if sum(features.values()) > 0 else 1
        alpha_ratio = features.get("alpha", 0.0) / total_power
        beta_ratio = features.get("beta", 0.0) / total_power
        theta_ratio = features.get("theta", 0.0) / total_power
        gamma_ratio = features.get("gamma", 0.0) / total_power
        delta_ratio = features.get("delta", 0.0) / total_power

        mood_score = (
            0.5 * math.tanh(calm_metric * 0.1)
            - 0.4 * math.tanh(stress_metric * 0.08)
            + 0.3 * math.tanh(focus_metric * 0.1)
            + self.config.baseline_mood_bias
        )
        mood_score = max(-1.0, min(1.0, mood_score))

        # 基于频段比例确定情绪（扩展的情绪分类）
        if beta_ratio > 0.4 and alpha_ratio < 0.2:
            label = "angry"
            mood_score = -0.7
        elif alpha_ratio > 0.4 and beta_ratio < 0.2:
            label = "happy"
            mood_score = 0.7
        elif theta_ratio > 0.3 and alpha_ratio > 0.3:
            label = "relaxed"
            mood_score = 0.5
        elif theta_ratio > 0.4:
            label = "sad"
            mood_score = -0.5
        elif beta_ratio > 0.3 and theta_ratio > 0.3:
            label = "surprise"
            mood_score = 0.5
        elif beta_ratio > 0.35 and alpha_ratio > 0.25:
            label = "fear"
            mood_score = -0.6
        elif theta_ratio > 0.35 and beta_ratio > 0.25:
            label = "disgust"
            mood_score = -0.4
        elif mood_score > 0.45:
            label = "happy"
        elif mood_score > 0.1:
            label = "neutral"
        elif mood_score < -0.45:
            label = "angry"
        elif mood_score < -0.15:
            label = "sad"
        else:
            label = "neutral"

        confidence = min(1.0, 0.5 + abs(mood_score) * 0.5 + self._rng.random() * 0.1)

        metadata = {
            "features": features,
            "band_ratios": {
                "alpha": alpha_ratio,
                "beta": beta_ratio,
                "theta": theta_ratio,
                "gamma": gamma_ratio,
                "delta": delta_ratio
            },
            "notes": "Enhanced simulated classification with extended emotion categories.",
        }

        return ChannelEmotion(
            source="eeg",
            label=label,
            confidence=confidence,
            mood_score=mood_score,
            metadata=metadata,
        )
