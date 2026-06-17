"""EXP-11: video bubble tracking baseline.

Usage:
    uv run --locked python experiments/exp_11_video_tracking.py \
        /path/to/video1.mp4 /path/to/video2.mp4

The detector is intentionally lightweight and supports two modes:
    motion: MOG2 background subtraction -> contour filtering -> greedy centroid tracking.
    bright: white/bright mask -> contour filtering -> greedy centroid tracking.
    hough: grayscale Hough circle detection -> greedy centroid tracking.
    hybrid: bright mask + Hough/blob candidates + feature scoring + greedy tracking.
It is a baseline for checking whether video motion makes bubble tracking easier
than single-frame transparent-object detection.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import resource
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np


OUTPUT_DIR = Path("data/outputs/exp-11-video-tracking")


@dataclass
class Detection:
    x: float
    y: float
    r: float
    area: float
    circularity: float
    score: float = 1.0
    source: str = "unknown"


@dataclass
class Track:
    track_id: int
    x: float
    y: float
    r: float
    age: int = 1
    hits: int = 1
    missed: int = 0
    history: list[tuple[int, float, float]] = field(default_factory=list)


def _rss_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024) if platform.system() == "Darwin" else rss / 1024


def resize_for_processing(frame: np.ndarray, long_edge: int) -> tuple[np.ndarray, float]:
    height, width = frame.shape[:2]
    current_long_edge = max(width, height)
    if current_long_edge <= long_edge:
        return frame, 1.0
    scale = long_edge / current_long_edge
    resized = cv2.resize(
        frame,
        (round(width * scale), round(height * scale)),
        interpolation=cv2.INTER_AREA,
    )
    return resized, scale


def detect_motion_blobs(
    frame: np.ndarray,
    subtractor: cv2.BackgroundSubtractorMOG2,
    *,
    min_area: float,
    max_area: float,
    min_circularity: float,
) -> tuple[list[Detection], np.ndarray]:
    foreground = subtractor.apply(frame)
    _, mask = cv2.threshold(foreground, 200, 255, cv2.THRESH_BINARY)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    detections: list[Detection] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue

        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        circularity = 4 * math.pi * area / (perimeter * perimeter)
        if circularity < min_circularity:
            continue

        (x, y), radius = cv2.minEnclosingCircle(contour)
        if radius <= 0:
            continue
        detections.append(Detection(x=x, y=y, r=radius, area=area, circularity=circularity))

    return detections, mask


def detections_from_mask(
    mask: np.ndarray,
    *,
    min_area: float,
    max_area: float,
    min_circularity: float,
) -> list[Detection]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    detections: list[Detection] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue

        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        circularity = 4 * math.pi * area / (perimeter * perimeter)
        if circularity < min_circularity:
            continue

        (x, y), radius = cv2.minEnclosingCircle(contour)
        if radius <= 0:
            continue
        detections.append(Detection(x=x, y=y, r=radius, area=area, circularity=circularity))

    return detections


def detect_bright_blobs(
    frame: np.ndarray,
    *,
    min_area: float,
    max_area: float,
    min_circularity: float,
    min_value: int,
    max_saturation: int,
) -> tuple[list[Detection], np.ndarray]:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        np.array([0, 0, min_value], dtype=np.uint8),
        np.array([179, max_saturation, 255], dtype=np.uint8),
    )
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    detections = detections_from_mask(
        mask,
        min_area=min_area,
        max_area=max_area,
        min_circularity=min_circularity,
    )
    return detections, mask


def make_bright_mask(frame: np.ndarray, *, min_value: int, max_saturation: int) -> np.ndarray:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        np.array([0, 0, min_value], dtype=np.uint8),
        np.array([179, max_saturation, 255], dtype=np.uint8),
    )
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def _circle_mask(shape: tuple[int, int], x: int, y: int, radius: int, thickness: int = -1) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    cv2.circle(mask, (x, y), max(1, int(radius)), 255, thickness)
    return mask


def _mask_fraction(mask: np.ndarray, sample_mask: np.ndarray) -> float:
    sample_pixels = int((sample_mask > 0).sum())
    if sample_pixels == 0:
        return 0.0
    return float(((mask > 0) & (sample_mask > 0)).sum() / sample_pixels)


def find_padded_rois(
    mask: np.ndarray,
    *,
    min_area: float,
    padding: int,
    max_rois: int,
) -> list[tuple[int, int, int, int]]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[tuple[float, tuple[int, int, int, int]]] = []
    height, width = mask.shape[:2]
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        x0 = max(0, x - padding)
        y0 = max(0, y - padding)
        x1 = min(width, x + w + padding)
        y1 = min(height, y + h + padding)
        boxes.append((area, (x0, y0, x1, y1)))
    boxes.sort(key=lambda item: item[0], reverse=True)
    return [box for _, box in boxes[:max_rois]]


def score_circle_candidate(
    gray: np.ndarray,
    bright_mask: np.ndarray,
    motion_mask: np.ndarray | None,
    *,
    x: int,
    y: int,
    radius: int,
    bright_value: int,
    highlight_percentile: float,
) -> tuple[float, dict[str, float]]:
    circle_mask = _circle_mask(gray.shape, x, y, radius)
    inner_mask = _circle_mask(gray.shape, x, y, max(1, int(radius * 0.65)))
    outer_mask = _circle_mask(gray.shape, x, y, int(radius * 1.35))
    cv2.circle(outer_mask, (x, y), int(radius * 1.05), 0, -1)

    circle_values = gray[circle_mask > 0]
    if circle_values.size == 0:
        return 0.0, {}

    mean_value = cv2.mean(gray, mask=circle_mask)[0]
    inner_mean_value = cv2.mean(gray, mask=inner_mask)[0]
    outer_mean_value = cv2.mean(gray, mask=outer_mask)[0]
    local_contrast = inner_mean_value - outer_mean_value
    bright_fraction = float((circle_values >= bright_value).mean())
    highlight_value = float(np.percentile(circle_values, highlight_percentile))
    bright_overlap = _mask_fraction(bright_mask, circle_mask)
    motion_support = _mask_fraction(motion_mask, circle_mask) if motion_mask is not None else 0.0

    score = (
        0.28 * min(1.0, max(0.0, bright_overlap / 0.45))
        + 0.24 * min(1.0, max(0.0, local_contrast / 45.0))
        + 0.20 * min(1.0, max(0.0, (highlight_value - 120.0) / 100.0))
        + 0.16 * min(1.0, max(0.0, bright_fraction / 0.35))
        + 0.12 * min(1.0, max(0.0, motion_support / 0.25))
    )
    features = {
        "mean_value": mean_value,
        "inner_mean_value": inner_mean_value,
        "local_contrast": local_contrast,
        "bright_fraction": bright_fraction,
        "highlight_value": highlight_value,
        "bright_overlap": bright_overlap,
        "motion_support": motion_support,
    }
    return score, features


def detect_hough_circles(
    frame: np.ndarray,
    *,
    min_radius: int,
    max_radius: int,
    hough_param2: float,
    min_mean_value: float,
    min_inner_mean_value: float,
    bright_value: int,
    min_bright_fraction: float,
    min_local_contrast: float,
    highlight_percentile: float,
    min_highlight_value: float,
) -> tuple[list[Detection], np.ndarray]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(min_radius * 2, 32),
        param1=80,
        param2=hough_param2,
        minRadius=min_radius,
        maxRadius=max_radius,
    )

    detections: list[Detection] = []
    mask = np.zeros_like(gray)
    if circles is None:
        return detections, mask

    for x, y, radius in np.round(circles[0]).astype("int"):
        if not (0 <= x < gray.shape[1] and 0 <= y < gray.shape[0]):
            continue
        circle_mask = np.zeros_like(gray)
        cv2.circle(circle_mask, (x, y), int(radius), 255, -1)
        inner_mask = np.zeros_like(gray)
        cv2.circle(inner_mask, (x, y), max(1, int(radius * 0.65)), 255, -1)
        outer_mask = np.zeros_like(gray)
        cv2.circle(outer_mask, (x, y), int(radius * 1.35), 255, -1)
        cv2.circle(outer_mask, (x, y), int(radius * 1.05), 0, -1)
        mean_value = cv2.mean(gray, mask=circle_mask)[0]
        inner_mean_value = cv2.mean(gray, mask=inner_mask)[0]
        outer_mean_value = cv2.mean(gray, mask=outer_mask)[0]
        local_contrast = inner_mean_value - outer_mean_value
        circle_values = gray[circle_mask > 0]
        bright_fraction = float((circle_values >= bright_value).mean())
        highlight_value = float(np.percentile(circle_values, highlight_percentile))
        if (
            mean_value < min_mean_value
            or inner_mean_value < min_inner_mean_value
            or bright_fraction < min_bright_fraction
            or local_contrast < min_local_contrast
            or highlight_value < min_highlight_value
        ):
            continue
        area = math.pi * float(radius) * float(radius)
        detections.append(
            Detection(
                x=float(x),
                y=float(y),
                r=float(radius),
                area=area,
                circularity=1.0,
            )
        )
        cv2.circle(mask, (x, y), int(radius), 255, 2)

    return detections, mask


def apply_circle_nms(
    detections: list[Detection], overlap_threshold: float
) -> list[Detection]:
    if not detections:
        return []

    sorted_detections = sorted(detections, key=lambda detection: detection.r, reverse=True)
    kept: list[Detection] = []
    for detection in sorted_detections:
        duplicate = False
        for existing in kept:
            distance = math.hypot(detection.x - existing.x, detection.y - existing.y)
            if distance < overlap_threshold * max(detection.r, existing.r):
                duplicate = True
                break
        if not duplicate:
            kept.append(detection)
    return kept


def apply_scored_circle_nms(
    detections: list[Detection], overlap_threshold: float
) -> list[Detection]:
    if not detections:
        return []

    sorted_detections = sorted(
        detections,
        key=lambda detection: (detection.score, detection.r),
        reverse=True,
    )
    kept: list[Detection] = []
    for detection in sorted_detections:
        duplicate = False
        for existing in kept:
            distance = math.hypot(detection.x - existing.x, detection.y - existing.y)
            if distance < overlap_threshold * max(detection.r, existing.r):
                duplicate = True
                break
        if not duplicate:
            kept.append(detection)
    return kept


def detect_hybrid_bubbles(
    frame: np.ndarray,
    *,
    min_radius: int,
    max_radius: int,
    hough_param2: float,
    min_mean_value: float,
    min_inner_mean_value: float,
    bright_value: int,
    min_bright_fraction: float,
    min_local_contrast: float,
    highlight_percentile: float,
    min_highlight_value: float,
    min_area: float,
    max_area: float,
    min_circularity: float,
    min_value: int,
    max_saturation: int,
    min_bright_overlap: float,
    min_hybrid_score: float,
    max_hybrid_rois: int,
    motion_mask: np.ndarray | None,
) -> tuple[list[Detection], np.ndarray]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    bright_mask = make_bright_mask(
        frame,
        min_value=min_value,
        max_saturation=max_saturation,
    )
    detections: list[Detection] = []

    for detection in detections_from_mask(
        bright_mask,
        min_area=min_area,
        max_area=max_area,
        min_circularity=min_circularity,
    ):
        x = int(round(detection.x))
        y = int(round(detection.y))
        radius = int(round(detection.r))
        score, features = score_circle_candidate(
            gray,
            bright_mask,
            motion_mask,
            x=x,
            y=y,
            radius=radius,
            bright_value=bright_value,
            highlight_percentile=highlight_percentile,
        )
        if score < min_hybrid_score:
            continue
        detection.score = score
        detection.source = "bright"
        detections.append(detection)

    hough_rois = find_padded_rois(
        bright_mask,
        min_area=max(8.0, min_area * 0.25),
        padding=max_radius,
        max_rois=max_hybrid_rois,
    )
    for x0, y0, x1, y1 in hough_rois:
        roi_gray = gray[y0:y1, x0:x1]
        if roi_gray.shape[0] < min_radius * 2 or roi_gray.shape[1] < min_radius * 2:
            continue
        blurred = cv2.GaussianBlur(roi_gray, (9, 9), 2)
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=max(min_radius * 2, 32),
            param1=80,
            param2=hough_param2,
            minRadius=min_radius,
            maxRadius=max_radius,
        )
        if circles is None:
            continue
        for roi_x, roi_y, radius in np.round(circles[0]).astype("int"):
            x = int(roi_x + x0)
            y = int(roi_y + y0)
            if not (0 <= x < gray.shape[1] and 0 <= y < gray.shape[0]):
                continue
            score, features = score_circle_candidate(
                gray,
                bright_mask,
                motion_mask,
                x=x,
                y=y,
                radius=radius,
                bright_value=bright_value,
                highlight_percentile=highlight_percentile,
            )
            if (
                features.get("mean_value", 0.0) < min_mean_value
                or features.get("inner_mean_value", 0.0) < min_inner_mean_value
                or features.get("bright_fraction", 0.0) < min_bright_fraction
                or features.get("local_contrast", 0.0) < min_local_contrast
                or features.get("highlight_value", 0.0) < min_highlight_value
                or features.get("bright_overlap", 0.0) < min_bright_overlap
                or score < min_hybrid_score
            ):
                continue
            detections.append(
                Detection(
                    x=float(x),
                    y=float(y),
                    r=float(radius),
                    area=math.pi * float(radius) * float(radius),
                    circularity=1.0,
                    score=score,
                    source="hough",
                )
            )

    mask = cv2.cvtColor(bright_mask, cv2.COLOR_GRAY2BGR)
    for detection in detections:
        cv2.circle(
            mask,
            (round(detection.x), round(detection.y)),
            round(detection.r),
            (0, 255, 255) if detection.source == "hough" else (255, 0, 0),
            2,
        )
    return detections, mask


def update_tracks(
    tracks: list[Track],
    detections: list[Detection],
    *,
    frame_index: int,
    next_track_id: int,
    max_match_distance: float,
    max_missed: int,
) -> tuple[list[Track], int]:
    unmatched_tracks = set(range(len(tracks)))
    unmatched_detections = set(range(len(detections)))
    pairs: list[tuple[float, int, int]] = []

    for track_index, track in enumerate(tracks):
        for detection_index, detection in enumerate(detections):
            distance = math.hypot(track.x - detection.x, track.y - detection.y)
            if distance <= max_match_distance + max(track.r, detection.r) * 0.5:
                pairs.append((distance, track_index, detection_index))

    for _, track_index, detection_index in sorted(pairs, key=lambda item: item[0]):
        if track_index not in unmatched_tracks or detection_index not in unmatched_detections:
            continue
        track = tracks[track_index]
        detection = detections[detection_index]
        alpha = 0.65
        track.x = alpha * detection.x + (1 - alpha) * track.x
        track.y = alpha * detection.y + (1 - alpha) * track.y
        track.r = alpha * detection.r + (1 - alpha) * track.r
        track.age += 1
        track.hits += 1
        track.missed = 0
        track.history.append((frame_index, track.x, track.y))
        unmatched_tracks.remove(track_index)
        unmatched_detections.remove(detection_index)

    for track_index in unmatched_tracks:
        tracks[track_index].age += 1
        tracks[track_index].missed += 1

    for detection_index in unmatched_detections:
        detection = detections[detection_index]
        tracks.append(
            Track(
                track_id=next_track_id,
                x=detection.x,
                y=detection.y,
                r=detection.r,
                history=[(frame_index, detection.x, detection.y)],
            )
        )
        next_track_id += 1

    live_tracks = [track for track in tracks if track.missed <= max_missed]
    return live_tracks, next_track_id


def draw_overlay(
    frame: np.ndarray,
    detections: list[Detection],
    tracks: list[Track],
    *,
    frame_index: int,
) -> np.ndarray:
    output = frame.copy()
    for detection in detections:
        center = (round(detection.x), round(detection.y))
        cv2.circle(output, center, round(detection.r), (0, 255, 255), 1)

    for track in tracks:
        if track.hits < 2:
            continue
        center = (round(track.x), round(track.y))
        cv2.circle(output, center, round(track.r), (0, 180, 0), 2)
        cv2.putText(
            output,
            f"#{track.track_id}",
            (center[0] + 6, center[1] - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 180, 0),
            1,
            cv2.LINE_AA,
        )

    cv2.putText(
        output,
        f"frame {frame_index} det={len(detections)} tracks={sum(t.hits >= 2 for t in tracks)}",
        (12, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return output


def process_video(args: argparse.Namespace, video_path: Path) -> dict:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise SystemExit(f"Could not open video: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 30
    source_frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    source_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    source_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    output_video = OUTPUT_DIR / f"{video_path.stem}_{args.detector}_tracked.mp4"
    writer: cv2.VideoWriter | None = None
    subtractor = None
    if args.detector in {"motion", "hybrid"}:
        subtractor = cv2.createBackgroundSubtractorMOG2(
            history=args.history,
            varThreshold=args.var_threshold,
            detectShadows=False,
        )

    tracks: list[Track] = []
    next_track_id = 1
    frame_index = 0
    processed_frames = 0
    detection_counts: list[int] = []
    active_track_counts: list[int] = []
    started_at = time.perf_counter()

    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if args.max_frames and processed_frames >= args.max_frames:
            break
        if frame_index % args.frame_stride != 0:
            frame_index += 1
            continue

        work_frame, _ = resize_for_processing(frame, args.long_edge)
        motion_mask = None
        if args.detector == "hybrid":
            if subtractor is None:
                raise AssertionError("hybrid detector requires a background subtractor")
            foreground = subtractor.apply(work_frame)
            _, motion_mask = cv2.threshold(foreground, 200, 255, cv2.THRESH_BINARY)
            kernel = np.ones((5, 5), np.uint8)
            motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_OPEN, kernel)
            motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_CLOSE, kernel)

        if args.detector == "motion":
            if subtractor is None:
                raise AssertionError("motion detector requires a background subtractor")
            detections, _ = detect_motion_blobs(
                work_frame,
                subtractor,
                min_area=args.min_area,
                max_area=args.max_area,
                min_circularity=args.min_circularity,
            )
        elif args.detector == "bright":
            detections, _ = detect_bright_blobs(
                work_frame,
                min_area=args.min_area,
                max_area=args.max_area,
                min_circularity=args.min_circularity,
                min_value=args.min_value,
                max_saturation=args.max_saturation,
            )
        elif args.detector == "hough":
            detections, _ = detect_hough_circles(
                work_frame,
                min_radius=args.min_radius,
                max_radius=args.max_radius,
                hough_param2=args.hough_param2,
                min_mean_value=args.min_mean_value,
                min_inner_mean_value=args.min_inner_mean_value,
                bright_value=args.bright_value,
                min_bright_fraction=args.min_bright_fraction,
                min_local_contrast=args.min_local_contrast,
                highlight_percentile=args.highlight_percentile,
                min_highlight_value=args.min_highlight_value,
            )
        else:
            detections, _ = detect_hybrid_bubbles(
                work_frame,
                min_radius=args.min_radius,
                max_radius=args.max_radius,
                hough_param2=args.hough_param2,
                min_mean_value=args.min_mean_value,
                min_inner_mean_value=args.min_inner_mean_value,
                bright_value=args.bright_value,
                min_bright_fraction=args.min_bright_fraction,
                min_local_contrast=args.min_local_contrast,
                highlight_percentile=args.highlight_percentile,
                min_highlight_value=args.min_highlight_value,
                min_area=args.min_area,
                max_area=args.max_area,
                min_circularity=args.min_circularity,
                min_value=args.min_value,
                max_saturation=args.max_saturation,
                min_bright_overlap=args.min_bright_overlap,
                min_hybrid_score=args.min_hybrid_score,
                max_hybrid_rois=args.max_hybrid_rois,
                motion_mask=motion_mask,
            )
        if args.detector == "hybrid":
            detections = apply_scored_circle_nms(detections, args.nms_threshold)
        else:
            detections = apply_circle_nms(detections, args.nms_threshold)
        tracks, next_track_id = update_tracks(
            tracks,
            detections,
            frame_index=frame_index,
            next_track_id=next_track_id,
            max_match_distance=args.max_match_distance,
            max_missed=args.max_missed,
        )
        overlay = draw_overlay(work_frame, detections, tracks, frame_index=frame_index)

        if writer is None:
            height, width = overlay.shape[:2]
            output_fps = max(1.0, fps / args.frame_stride)
            writer = cv2.VideoWriter(
                str(output_video),
                cv2.VideoWriter_fourcc(*"mp4v"),
                output_fps,
                (width, height),
            )
        writer.write(overlay)

        detection_counts.append(len(detections))
        active_track_counts.append(sum(track.hits >= args.min_hits for track in tracks))
        processed_frames += 1
        frame_index += 1

    capture.release()
    if writer is not None:
        writer.release()

    elapsed = time.perf_counter() - started_at
    confirmed_tracks = [track for track in tracks if track.hits >= args.min_hits]
    return {
        "video": str(video_path),
        "source_width": source_width,
        "source_height": source_height,
        "source_fps": round(fps, 2),
        "source_frame_count": source_frame_count,
        "processed_frames": processed_frames,
        "frame_stride": args.frame_stride,
        "long_edge": args.long_edge,
        "detector": args.detector,
        "output_video": str(output_video),
        "confirmed_track_count_at_end": len(confirmed_tracks),
        "max_active_tracks": max(active_track_counts, default=0),
        "mean_detections_per_processed_frame": round(float(np.mean(detection_counts)), 2)
        if detection_counts
        else 0,
        "max_detections_per_processed_frame": max(detection_counts, default=0),
        "elapsed_seconds": round(elapsed, 2),
        "mean_ms_per_processed_frame": round((elapsed / processed_frames) * 1000, 1)
        if processed_frames
        else None,
        "rss_mb": round(_rss_mb(), 1),
        "parameters": {
            "history": args.history,
            "var_threshold": args.var_threshold,
            "min_value": args.min_value,
            "max_saturation": args.max_saturation,
            "min_radius": args.min_radius,
            "max_radius": args.max_radius,
            "hough_param2": args.hough_param2,
            "min_mean_value": args.min_mean_value,
            "min_inner_mean_value": args.min_inner_mean_value,
            "bright_value": args.bright_value,
            "min_bright_fraction": args.min_bright_fraction,
            "min_local_contrast": args.min_local_contrast,
            "highlight_percentile": args.highlight_percentile,
            "min_highlight_value": args.min_highlight_value,
            "min_bright_overlap": args.min_bright_overlap,
            "min_hybrid_score": args.min_hybrid_score,
            "max_hybrid_rois": args.max_hybrid_rois,
            "nms_threshold": args.nms_threshold,
            "min_area": args.min_area,
            "max_area": args.max_area,
            "min_circularity": args.min_circularity,
            "max_match_distance": args.max_match_distance,
            "max_missed": args.max_missed,
            "min_hits": args.min_hits,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Track bubble-like motion in videos.")
    parser.add_argument("videos", type=Path, nargs="+", help="Input video paths")
    parser.add_argument("--long-edge", type=int, default=960)
    parser.add_argument(
        "--detector",
        choices=["motion", "bright", "hough", "hybrid"],
        default="motion",
        help=(
            "motion uses MOG2; bright uses white thresholding; "
            "hough detects circle edges; hybrid scores bright/blob/Hough candidates."
        ),
    )
    parser.add_argument("--frame-stride", type=int, default=1)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--history", type=int, default=120)
    parser.add_argument("--var-threshold", type=float, default=24)
    parser.add_argument("--min-value", type=int, default=180)
    parser.add_argument("--max-saturation", type=int, default=80)
    parser.add_argument("--min-radius", type=int, default=12)
    parser.add_argument("--max-radius", type=int, default=120)
    parser.add_argument("--hough-param2", type=float, default=24)
    parser.add_argument("--min-mean-value", type=float, default=80)
    parser.add_argument("--min-inner-mean-value", type=float, default=0)
    parser.add_argument("--bright-value", type=int, default=170)
    parser.add_argument("--min-bright-fraction", type=float, default=0)
    parser.add_argument("--min-local-contrast", type=float, default=0)
    parser.add_argument("--highlight-percentile", type=float, default=99)
    parser.add_argument("--min-highlight-value", type=float, default=0)
    parser.add_argument("--min-bright-overlap", type=float, default=0.15)
    parser.add_argument("--min-hybrid-score", type=float, default=0.35)
    parser.add_argument("--max-hybrid-rois", type=int, default=24)
    parser.add_argument("--nms-threshold", type=float, default=0.7)
    parser.add_argument("--min-area", type=float, default=35)
    parser.add_argument("--max-area", type=float, default=12000)
    parser.add_argument("--min-circularity", type=float, default=0.35)
    parser.add_argument("--max-match-distance", type=float, default=45)
    parser.add_argument("--max-missed", type=int, default=8)
    parser.add_argument("--min-hits", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    global OUTPUT_DIR
    OUTPUT_DIR = args.output_dir
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for video_path in args.videos:
        summary = process_video(args, video_path)
        rows.append(summary)
        print(
            f"{Path(summary['video']).name}: "
            f"frames={summary['processed_frames']} "
            f"max_tracks={summary['max_active_tracks']} "
            f"mean_det={summary['mean_detections_per_processed_frame']} "
            f"ms/frame={summary['mean_ms_per_processed_frame']} "
            f"out={summary['output_video']}"
        )

    summary_path = OUTPUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"saved {summary_path}")


if __name__ == "__main__":
    main()
