"""EXP-04: HSV 色マスクによる背景テクスチャ除去

緑（草木）と土色をマスクして HoughCircles の前処理から除外する。
屋外 3 枚（algerian_grassland, giant_bubble, grapevine）の主要誤検出源を狙い打ち。

マスク戦略:
    HSV で以下の範囲を「背景」として除外:
    - 草木: H=35〜85（黄緑〜深緑）× S>0.40
    - 土・幹: H=10〜35（橙〜黄土）× S>0.45
    除外ピクセルは画像の平均グレー値に置換してから Blur + HoughCircles。

仮説: outdoor 3 枚が 500 候補以下に削減。
     クリーンな背景の画像（closeup, supermacro）は候補数が変わらない。

Usage:
    uv run python experiments/exp_04_color_mask.py
"""

from __future__ import annotations

import json
import platform
import resource
import time
from pathlib import Path

import cv2
import numpy as np


def _rss_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024) if platform.system() == "Darwin" else rss / 1024

STANDARDIZED_DIR = Path("data/images/bubble-detection/standardized/long-edge-1600-png")
OUTPUT_DIR = Path("data/outputs/exp-04")

VISUAL_REFS: dict[str, int] = {
    "soap_bubbles_supermacro_pd": 75,
    "master_of_soapbubbles_cc0": 145,
    "irregular_bubble_cc0": 1,
    "soap_bubble_closeup_cc_by_2_0": 1,
    "soap_bubbles_algerian_grassland_cc_by_sa_4_0": 3,
    "giant_bubble_cc_by_sa_3_0": 1,
    "soap_bubble_grapevine_cc_by_sa_3_0": 1,
    "girl_with_soap_bubble_machine_cc_by_2_0": 45,
}

MIN_RADIUS = 8
MAX_RADIUS = 240
PARAM2 = 22


def build_background_mask(image_bgr: np.ndarray) -> np.ndarray:
    """
    1 = 背景（除外する）、0 = 前景（保持する）のマスク。
    草木（緑）と土色（茶・橙）を背景として検出。
    """
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0].astype(float)  # [0, 179]
    s = hsv[:, :, 1].astype(float) / 255.0  # [0, 1]

    # 草木: H=18〜60 (OpenCV では 35/2〜85/2) × S>0.40
    vegetation = (h >= 18) & (h <= 60) & (s > 0.40)
    # 土・幹: H=5〜18 (10/2〜35/2) × S>0.45
    earth = (h >= 5) & (h <= 18) & (s > 0.45)

    mask = (vegetation | earth).astype(np.uint8)
    # 小さなノイズを除去
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return mask


def detect_with_mask(
    image: np.ndarray, background_mask: np.ndarray
) -> list[tuple[int, int, float]]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mean_gray = int(np.mean(gray))

    # 背景ピクセルを平均グレーで埋めた gray を作る
    masked_gray = gray.copy()
    masked_gray[background_mask == 1] = mean_gray

    blurred = cv2.GaussianBlur(masked_gray, (7, 7), 1.5)
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(MIN_RADIUS * 2, 16),
        param1=120,
        param2=PARAM2,
        minRadius=MIN_RADIUS,
        maxRadius=MAX_RADIUS,
    )
    if circles is None:
        return []
    candidates = []
    for x, y, r in np.round(circles[0]).astype("int"):
        if 0 <= x < image.shape[1] and 0 <= y < image.shape[0]:
            candidates.append((int(x), int(y), float(r)))
    return candidates


def draw_overlay(image: np.ndarray, candidates: list[tuple[int, int, float]]) -> np.ndarray:
    debug = image.copy()
    for x, y, r in candidates:
        cv2.circle(debug, (x, y), int(r), (0, 255, 255), 2)
        cv2.circle(debug, (x, y), 2, (0, 0, 255), 3)
    return debug


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    print(f"{'image':<55} {'candidates':>10} {'visual_ref':>10} {'ratio':>8} {'masked%':>8} {'mask_ms':>8} {'det_ms':>8} {'rss_mb':>8}")
    print("-" * 124)

    for png in sorted(STANDARDIZED_DIR.glob("*.png")):
        image = cv2.imread(str(png))
        if image is None:
            continue

        t0 = time.perf_counter()
        bg_mask = build_background_mask(image)
        mask_ms = (time.perf_counter() - t0) * 1000
        masked_pct = round(100.0 * bg_mask.sum() / bg_mask.size, 1)

        t1 = time.perf_counter()
        candidates = detect_with_mask(image, bg_mask)
        det_ms = (time.perf_counter() - t1) * 1000
        rss_mb = _rss_mb()

        count = len(candidates)
        visual_ref = VISUAL_REFS.get(png.stem)
        ratio = round(count / visual_ref, 1) if visual_ref else None

        mask_vis = image.copy()
        mask_vis[bg_mask == 1] = (0, 0, 180)
        cv2.imwrite(str(OUTPUT_DIR / f"{png.stem}_mask.png"), mask_vis)

        overlay = draw_overlay(image, candidates)
        cv2.imwrite(str(OUTPUT_DIR / f"{png.stem}_overlay.png"), overlay)

        rows.append(
            {
                "filename": png.name,
                "stem": png.stem,
                "candidate_count": count,
                "visual_ref": visual_ref,
                "ratio": ratio,
                "masked_pct": masked_pct,
                "mask_time_ms": round(mask_ms, 1),
                "detect_time_ms": round(det_ms, 1),
                "total_time_ms": round(mask_ms + det_ms, 1),
                "rss_mb": round(rss_mb, 1),
            }
        )

        ratio_str = f"{ratio:.1f}x" if ratio is not None else "N/A"
        ref_str = str(visual_ref) if visual_ref is not None else "N/A"
        print(
            f"{png.stem:<55} {count:>10} {ref_str:>10} {ratio_str:>8} {masked_pct:>7.1f}% {mask_ms:>7.1f} {det_ms:>7.1f} {rss_mb:>7.1f}"
        )

    out_path = OUTPUT_DIR / "counts_color_mask.json"
    out_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"\nsaved → {out_path}")


if __name__ == "__main__":
    main()
