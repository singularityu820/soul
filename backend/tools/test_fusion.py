from __future__ import annotations

import os
import sys

# Ensure backend root is on sys.path so `import app` works when this script
# is executed from the `tools` directory (common when running tests).
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.services.fusion import EmotionFusionService
from app.schemas import ChannelEmotion


def run():
    # 构造示例 ChannelEmotion：EEG、face、speech
    eeg = ChannelEmotion(source="eeg", label="joyful", confidence=0.6, mood_score=0.5, metadata={})
    face = ChannelEmotion(source="face", label="surprise", confidence=0.9, mood_score=0.3, metadata={})
    speech = ChannelEmotion(source="speech", label="surprised", confidence=0.5, mood_score=0.25, metadata={})

    fusion = EmotionFusionService()
    result = fusion.fuse([eeg, face, speech])
    # Pydantic v2: use model_dump_json which handles datetimes and other types
    print("Fusion result:\n", result.model_dump_json(indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run()
