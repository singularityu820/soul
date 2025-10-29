"""Local test harness for FaceEmotionTool.

This script can be used to verify the face tool behavior without running
the full pipeline or frontend. It supports two modes:
  - simulated (no DeepFace): quick sanity check of API and fallback behavior
  - deepface: if deepface and tensorflow/torch are installed, it will run
    DeepFace.analyze on a provided image (best-effort) and print the
    ChannelEmotion returned by the tool.

Usage (from backend folder):
  python tools/test_face_tool.py --image ../assets/test_face.jpg --mode simulated
  python tools/test_face_tool.py --image ../assets/test_face.jpg --mode deepface

Note: put a test image at backend/assets/test_face.jpg or change path.
"""

from __future__ import annotations

import argparse
import asyncio
import cv2
import numpy as np
import sys
from pathlib import Path
import json
# Ensure repo imports resolve when running from backend/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.face import FaceEmotionTool
from app.config import FaceEmotionConfig


async def run_test(image_path: str, mode: str):
    cfg = FaceEmotionConfig()
    use_deepface = mode == "deepface"
    tool = FaceEmotionTool(cfg, use_deepface=use_deepface,deepface_kwargs = {"detector_backend": "opencv","actions": ["emotion"],"enforce_detection": False})

    img = cv2.imread(image_path)
    if img is None:
        print("Failed to load image:", image_path)
        return
    # convert to RGB numpy array expected by DeepFace
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    print("Updating frame into FaceEmotionTool (frame shape):", img_rgb.shape)
    await tool.update_frame(img_rgb)

    print("Calling analyze()... (this may be slow if DeepFace runs)")
    channel = await tool.analyze()

    print("Result ChannelEmotion:")
    # Pydantic v2: prefer model_dump()/model_dump_json() over deprecated .json()
    try:
        data = channel.model_dump()
    except Exception:
        # Fallback to dict() if model_dump is unavailable for some reason
        data = dict(channel)
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Path to test image")
    parser.add_argument("--mode", choices=("simulated", "deepface"), default="simulated")
    args = parser.parse_args()

    asyncio.run(run_test(args.image, args.mode))


if __name__ == "__main__":
    main()
