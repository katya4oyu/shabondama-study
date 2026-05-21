from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def detect_bubble_candidates(
    image: np.ndarray,
    *,
    min_radius: int = 8,
    max_radius: int = 240,
) -> tuple[np.ndarray, list[tuple[int, int, float]]]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 1.5)

    edges = cv2.Canny(blurred, 40, 120)
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(min_radius * 2, 16),
        param1=120,
        param2=22,
        minRadius=min_radius,
        maxRadius=max_radius,
    )

    candidates: list[tuple[int, int, float]] = []
    if circles is not None:
        for x, y, radius in np.round(circles[0]).astype("int"):
            if 0 <= x < image.shape[1] and 0 <= y < image.shape[0]:
                candidates.append((int(x), int(y), float(radius)))

    debug = image.copy()
    for index, (x, y, radius) in enumerate(candidates, start=1):
        cv2.circle(debug, (x, y), int(radius), (0, 255, 255), 2)
        cv2.circle(debug, (x, y), 2, (0, 0, 255), 3)
        cv2.putText(
            debug,
            str(index),
            (x + 6, y - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )

    edge_overlay = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    edge_overlay[:, :, 1] = np.maximum(edge_overlay[:, :, 1], edges)
    debug = cv2.addWeighted(debug, 0.85, edge_overlay, 0.35, 0)
    return debug, candidates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect soap-bubble candidates in a still image."
    )
    parser.add_argument("image", type=Path, help="Input image path")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("data/outputs/detected.png"),
        help="Debug output image path",
    )
    parser.add_argument("--min-radius", type=int, default=8)
    parser.add_argument("--max-radius", type=int, default=240)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image = cv2.imread(str(args.image))
    if image is None:
        raise SystemExit(f"Could not read image: {args.image}")

    debug, candidates = detect_bubble_candidates(
        image,
        min_radius=args.min_radius,
        max_radius=args.max_radius,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output), debug)

    print(f"found {len(candidates)} candidates")
    for index, (x, y, radius) in enumerate(candidates, start=1):
        print(f"{index}: x={x} y={y} radius={radius:.1f}")
