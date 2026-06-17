from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import cv2
import numpy as np


MODULE_PATH = Path(__file__).resolve().parents[1] / "experiments" / "exp_11_video_tracking.py"
spec = importlib.util.spec_from_file_location("exp_11_video_tracking", MODULE_PATH)
assert spec is not None and spec.loader is not None
exp11 = importlib.util.module_from_spec(spec)
sys.modules["exp_11_video_tracking"] = exp11
spec.loader.exec_module(exp11)


def test_score_priority_nms_keeps_stronger_overlapping_detection() -> None:
    weak_large = exp11.Detection(
        x=50,
        y=50,
        r=24,
        area=1800,
        circularity=1.0,
        score=0.2,
        source="hough",
    )
    strong_small = exp11.Detection(
        x=53,
        y=52,
        r=18,
        area=1000,
        circularity=1.0,
        score=0.9,
        source="bright",
    )
    separate = exp11.Detection(
        x=130,
        y=130,
        r=12,
        area=450,
        circularity=1.0,
        score=0.4,
        source="hough",
    )

    kept = exp11.apply_scored_circle_nms(
        [weak_large, strong_small, separate],
        overlap_threshold=0.7,
    )

    assert kept == [strong_small, separate]


def test_hybrid_detector_uses_bright_overlap_to_reject_background_circles() -> None:
    frame = np.full((160, 220, 3), 35, dtype=np.uint8)
    cv2.circle(frame, (70, 80), 28, (220, 220, 220), -1)
    cv2.circle(frame, (155, 80), 28, (75, 75, 75), 2)

    detections, _ = exp11.detect_hybrid_bubbles(
        frame,
        min_radius=18,
        max_radius=40,
        hough_param2=12,
        min_mean_value=40,
        min_inner_mean_value=0,
        bright_value=170,
        min_bright_fraction=0,
        min_local_contrast=0,
        highlight_percentile=99,
        min_highlight_value=0,
        min_area=80,
        max_area=5000,
        min_circularity=0.25,
        min_value=145,
        max_saturation=135,
        min_bright_overlap=0.2,
        min_hybrid_score=0.35,
        max_hybrid_rois=8,
        motion_mask=None,
    )

    assert detections
    assert all(abs(d.x - 70) < 18 for d in detections)
    assert all(d.score >= 0.35 for d in detections)
    assert any("bright" in d.source for d in detections)


if __name__ == "__main__":
    test_score_priority_nms_keeps_stronger_overlapping_detection()
    test_hybrid_detector_uses_bright_overlap_to_reject_background_circles()
