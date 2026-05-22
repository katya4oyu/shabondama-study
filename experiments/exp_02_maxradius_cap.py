"""EXP-02: maxRadius を画像短辺の比率で制限

画像短辺の 0.20/0.30/0.40 倍を maxRadius に設定し、
背景全体を覆う phantom circle（giant_bubble, irregular_bubble で顕著）を排除する。

仮説: 泡の最大半径は画像短辺の 30〜40% 以下に収まる。
     これを超える円は泡ではなく背景の弧や輪郭。

Usage:
    uv run python experiments/exp_02_maxradius_cap.py
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
OUTPUT_DIR = Path("data/outputs/exp-02")

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

FRACTIONS = [0.20, 0.30, 0.40]
MIN_RADIUS = 8
PARAM2 = 22  # ベースラインと同じ（EXP-02 は maxRadius だけ変える）


def detect_with_maxradius(
    image: np.ndarray, max_radius: int
) -> list[tuple[int, int, float]]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 1.5)

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(MIN_RADIUS * 2, 16),
        param1=120,
        param2=PARAM2,
        minRadius=MIN_RADIUS,
        maxRadius=max_radius,
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

    for fraction in FRACTIONS:
        tag = f"frac_{int(fraction * 100):02d}"

        print(f"\n=== maxRadius = short_edge × {fraction} ===")
        print(f"{'image':<55} {'max_r':>6} {'candidates':>10} {'visual_ref':>10} {'ratio':>8} {'ms':>8} {'rss_mb':>8}")
        print("-" * 116)

        for png in pngs:
            image = cv2.imread(str(png))
            if image is None:
                continue

            short_edge = min(image.shape[:2])
            max_radius = max(MIN_RADIUS + 1, int(short_edge * fraction))

            out_dir = OUTPUT_DIR / tag
            out_dir.mkdir(parents=True, exist_ok=True)

            t0 = time.perf_counter()
            candidates = detect_with_maxradius(image, max_radius)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            rss_mb = _rss_mb()

            count = len(candidates)
            visual_ref = VISUAL_REFS.get(png.stem)
            ratio = round(count / visual_ref, 1) if visual_ref else None

            radii = [r for _, _, r in candidates]
            radius_stats = {
                "min": float(min(radii)) if radii else None,
                "max": float(max(radii)) if radii else None,
                "mean": float(np.mean(radii)) if radii else None,
            }

            overlay = draw_overlay(image, candidates)
            cv2.imwrite(str(out_dir / f"{png.stem}_overlay.png"), overlay)

            all_rows.append(
                {
                    "fraction": fraction,
                    "max_radius_used": max_radius,
                    "filename": png.name,
                    "stem": png.stem,
                    "candidate_count": count,
                    "visual_ref": visual_ref,
                    "ratio": ratio,
                    "radius_stats": radius_stats,
                    "time_ms": round(elapsed_ms, 1),
                    "rss_mb": round(rss_mb, 1),
                }
            )

            ratio_str = f"{ratio:.1f}x" if ratio is not None else "N/A"
            ref_str = str(visual_ref) if visual_ref is not None else "N/A"
            print(
                f"{png.stem:<55} {max_radius:>6} {count:>10} {ref_str:>10} {ratio_str:>8} {elapsed_ms:>7.1f} {rss_mb:>7.1f}"
            )

    out_path = OUTPUT_DIR / "counts_by_maxradius.json"
    out_path.write_text(json.dumps(all_rows, indent=2, ensure_ascii=False))
    print(f"\nsaved → {out_path}")


if __name__ == "__main__":
    main()
