from __future__ import annotations

import asyncio
import math
import random
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, Tuple

import numpy as np

from ..config import EEGClassifierConfig, EEGStreamConfig
from ..schemas import ChannelEmotion, EEGWaveform


@dataclass(slots=True)
class EEGSample:
    waveform: EEGWaveform
    band_energy: Dict[str, float]


class EEGStreamTool:
    """Simulated EEG stream producing band-limited waveforms."""

    def __init__(self, config: EEGStreamConfig | None = None) -> None:
        self.config = config or EEGStreamConfig()
        self._buffers: Dict[str, Deque[float]] = {
            channel: deque(
                maxlen=int(
                    self.config.sample_rate_hz * self.config.waveform_buffer_seconds
                )
            )
            for channel in self.config.channels
        }
        self._rng = random.Random()
        self._phase_offsets: Dict[str, float] = {
            channel: self._rng.random() * math.tau for channel in self.config.channels
        }

    async def sample(self) -> EEGSample:
        await asyncio.sleep(self.config.update_interval)
        samples_per_channel = int(
            self.config.sample_rate_hz * self.config.update_interval
        )
        now = time.time()
        new_values: Dict[str, Iterable[float]] = {}
        band_energy: Dict[str, float] = {}

        for channel in self.config.channels:
            freq = self._channel_frequency(channel)
            phase = self._phase_offsets[channel]
            noise_scale = self._channel_noise(channel)
            values = []
            for i in range(samples_per_channel):
                t = now + i / self.config.sample_rate_hz
                base_wave = math.sin(math.tau * freq * t + phase)
                mod_wave = math.sin(math.tau * freq * 0.25 * t + phase / 2.0)
                noise = self._rng.gauss(0.0, noise_scale)
                amplitude = self._rng.uniform(*self.config.amplitude_range)
                value = (base_wave + 0.3 * mod_wave) * (amplitude / 2.0) + noise
                values.append(value)
                self._buffers[channel].append(value)
            new_values[channel] = list(values)
            band_energy[channel] = float(np.mean(np.abs(values)))

        waveform = EEGWaveform(
            channels={k: list(self._buffers[k]) for k in self.config.channels},
            sample_rate_hz=self.config.sample_rate_hz,
        )
        return EEGSample(waveform=waveform, band_energy=band_energy)

    def _channel_frequency(self, channel: str) -> float:
        base_map: Dict[str, float] = {
            "delta": 2.0,
            "theta": 6.0,
            "alpha": 10.0,
            "beta": 18.0,
            "gamma": 35.0,
        }
        return base_map.get(channel, 8.0)

    def _channel_noise(self, channel: str) -> float:
        if channel in {"alpha", "beta"}:
            return 1.5
        if channel == "gamma":
            return 2.5
        return 1.0


class EEGEmotionClassifier:
    """Placeholder MLP-driven classifier. Replace logic with real model calls."""

    def __init__(self, config: EEGClassifierConfig | None = None) -> None:
        self.config = config or EEGClassifierConfig()
        self._rng = random.Random()

    async def classify(self, sample: EEGSample) -> ChannelEmotion:
        features = sample.band_energy
        calm_metric = features.get("alpha", 0.0) - features.get("beta", 0.0) * 0.4
        focus_metric = features.get("beta", 0.0) - features.get("theta", 0.0) * 0.3
        stress_metric = features.get("gamma", 0.0) + features.get("beta", 0.0)

        mood_score = (
            0.5 * math.tanh(calm_metric * 0.1)
            - 0.4 * math.tanh(stress_metric * 0.08)
            + 0.3 * math.tanh(focus_metric * 0.1)
            + self.config.baseline_mood_bias
        )
        mood_score = max(-1.0, min(1.0, mood_score))

        if mood_score > 0.45:
            label = "joyful"
        elif mood_score > 0.1:
            label = "calm"
        elif mood_score < -0.45:
            label = "anxious"
        elif mood_score < -0.15:
            label = "stressed"
        else:
            label = "neutral"

        confidence = min(1.0, 0.5 + abs(mood_score) * 0.5 + self._rng.random() * 0.1)

        metadata = {
            "features": features,
            "notes": "Simulated classification. Replace with real EEG emotion MLP tool.",
        }

        return ChannelEmotion(
            source="eeg",
            label=label,
            confidence=confidence,
            mood_score=mood_score,
            metadata=metadata,
        )
