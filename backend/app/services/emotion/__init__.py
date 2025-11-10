"""Emotion sensing and fusion service modules."""

from .eeg import BCIDataFrame, EEGEmotionClassifier, EEGSample, EEGStreamTool
from .face import FaceEmotionTool
from .fusion import EmotionFusionService
from .avatar import AvatarOrchestrator
from .pipeline import EmotionPipeline
from .real_eeg import RealEEGProcessor, create_eeg_processor, EEGHardwareInterface, SerialEEGDevice, SimulatedEEGDevice

__all__ = [
    "BCIDataFrame",
    "EEGEmotionClassifier",
    "EEGSample",
    "EEGStreamTool",
    "FaceEmotionTool",
    "EmotionFusionService",
    "AvatarOrchestrator",
    "EmotionPipeline",
    "RealEEGProcessor",
    "create_eeg_processor",
    "EEGHardwareInterface",
    "SerialEEGDevice",
    "SimulatedEEGDevice",
]
