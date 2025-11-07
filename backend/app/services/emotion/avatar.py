from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict

from ...config import AvatarConfig
from ...schemas import AvatarPose, EmotionState


@dataclass(slots=True)
class AvatarState:
    history: Deque[AvatarPose]


class AvatarOrchestrator:
    """Maps emotion state into avatar animation directives."""

    def __init__(self, config: AvatarConfig | None = None) -> None:
        self.config = config or AvatarConfig()
        self._state = AvatarState(history=deque(maxlen=self.config.max_pose_history))

    def translate(self, emotion: EmotionState) -> AvatarPose:
        mapping: Dict[str, AvatarPose] = {
            "joyful": AvatarPose(
                expression="sparkle-smile",
                pose="levitate",
                energy=min(1.0, 0.6 + emotion.mood_score * 0.4),
                color_theme="#FFD166",
                emphasis="celebrate",
            ),
            "calm": AvatarPose(
                expression="soft-smile",
                pose="hover",
                energy=0.4,
                color_theme="#06D6A0",
                emphasis="float",
            ),
            "neutral": AvatarPose(
                expression="neutral",
                pose="idle",
                energy=0.3,
                color_theme="#118AB2",
            ),
            "focused": AvatarPose(
                expression="focused",
                pose="lean-forward",
                energy=0.5,
                color_theme="#073B4C",
            ),
            "anxious": AvatarPose(
                expression="concerned",
                pose="curl",
                energy=min(1.0, 0.5 + abs(emotion.mood_score)),
                color_theme="#EF476F",
                emphasis="soothe",
            ),
            "stressed": AvatarPose(
                expression="frown",
                pose="tensed",
                energy=min(1.0, 0.5 + abs(emotion.mood_score)),
                color_theme="#EF476F",
                emphasis="breathe",
            ),
            "sad": AvatarPose(
                expression="tearful",
                pose="droop",
                energy=0.3,
                color_theme="#26547C",
                emphasis="comfort",
            ),
        }

        pose = mapping.get(emotion.label, mapping["neutral"])
        self._state.history.append(pose)
        return pose

    def recent_history(self) -> list[AvatarPose]:
        return list(self._state.history)
