from __future__ import annotations

import asyncio
import logging
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List

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
