"""EXP-01: param2 スイープ

param2（円の累積器しきい値）を 22→60 の範囲でスイープし、
背景テクスチャ由来の誤候補を削減できる値を探す。

仮説: param2=22 は弱い円形エッジにも反応している。
     35〜60 に上げると屋外画像（grassland, grapevine, giant_bubble）の
     誤候補が減り、dense bubble 画像（supermacro）は視覚カウント 75 を維持する。

Usage:
    uv run python experiments/exp_01_param2_sweep.py
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
OUTPUT_DIR = Path("data/outputs/exp-01")

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

PARAM2_VALUES = [22, 30, 40, 50, 60]
MIN_RADIUS = 8
MAX_RADIUS = 240


def detect_with_param2(image: np.ndarray, param2: int) -> list[tuple[int, int, float]]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 1.5)

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(MIN_RADIUS * 2, 16),
        param1=120,
        param2=param2,
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
    pngs = sorted(STANDARDIZED_DIR.glob("*.png"))
    all_rows: list[dict] = []

    for param2 in PARAM2_VALUES:
        out_dir = OUTPUT_DIR / f"param2_{param2}"
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n=== param2={param2} ===")
        print(f"{'image':<55} {'candidates':>10} {'visual_ref':>10} {'ratio':>8} {'ms':>8} {'rss_mb':>8}")
        print("-" * 108)

        for png in pngs:
            image = cv2.imread(str(png))
            if image is None:
                continue

            t0 = time.perf_counter()
            candidates = detect_with_param2(image, param2)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            rss_mb = _rss_mb()

            count = len(candidates)
            visual_ref = VISUAL_REFS.get(png.stem)
            ratio = round(count / visual_ref, 1) if visual_ref else None

            overlay = draw_overlay(image, candidates)
            cv2.imwrite(str(out_dir / f"{png.stem}_overlay.png"), overlay)

            all_rows.append(
                {
                    "param2": param2,
                    "filename": png.name,
                    "stem": png.stem,
                    "candidate_count": count,
                    "visual_ref": visual_ref,
                    "ratio": ratio,
                    "time_ms": round(elapsed_ms, 1),
                    "rss_mb": round(rss_mb, 1),
                }
            )

            ratio_str = f"{ratio:.1f}x" if ratio is not None else "N/A"
            ref_str = str(visual_ref) if visual_ref is not None else "N/A"
            print(f"{png.stem:<55} {count:>10} {ref_str:>10} {ratio_str:>8} {elapsed_ms:>7.1f} {rss_mb:>7.1f}")

    out_path = OUTPUT_DIR / "counts_by_param2.json"
    out_path.write_text(json.dumps(all_rows, indent=2, ensure_ascii=False))
    print(f"\nsaved → {out_path}")


if __name__ == "__main__":
    main()
