"""EXP-05: Phase 1 ベスト組み合わせ — param2=50 + NMS threshold=0.5

Phase 1 Gate の判定:
    - EXP-01: param2=50 が最良（closeup 600→22, girl 40x→3.3x）
    - EXP-02: maxRadius 制限は無効（誤候補は小半径が主体）
    - EXP-03: NMS threshold=0.5 が最良（supermacro 1969→146, master 4755→376）
    - EXP-04: 色マスクは無効（grapevine/giant は悪化）

この実験では param2=50 で候補を絞った後、NMS threshold=0.5 で重複を除去する。

期待: 2 手法の削減効果が乗算的に効いて、各画像の ratio が Phase 1 単体より低くなる。
     特に単泡画像（closeup, grapevine, giant, irregular）の改善を確認する。

Usage:
    uv run python experiments/exp_05_combined_v1.py
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
OUTPUT_DIR = Path("data/outputs/exp-05")

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

PARAM2 = 50
NMS_THRESHOLD = 0.5
MIN_RADIUS = 8
MAX_RADIUS = 240


def detect_hough(image: np.ndarray) -> list[tuple[int, int, float]]:
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
        maxRadius=MAX_RADIUS,
    )
    if circles is None:
        return []
    candidates = []
    for x, y, r in np.round(circles[0]).astype("int"):
        if 0 <= x < image.shape[1] and 0 <= y < image.shape[0]:
            candidates.append((int(x), int(y), float(r)))
    return candidates


def apply_nms(
    candidates: list[tuple[int, int, float]], overlap_threshold: float
) -> list[tuple[int, int, float]]:
    if not candidates:
        return []
    sorted_cands = sorted(candidates, key=lambda c: c[2], reverse=True)
    xs = np.array([c[0] for c in sorted_cands], dtype=float)
    ys = np.array([c[1] for c in sorted_cands], dtype=float)
    rs = np.array([c[2] for c in sorted_cands], dtype=float)
    suppressed = np.zeros(len(sorted_cands), dtype=bool)
    surviving: list[tuple[int, int, float]] = []
    for i in range(len(sorted_cands)):
        if suppressed[i]:
            continue
        surviving.append(sorted_cands[i])
        dx = xs[i + 1 :] - xs[i]
        dy = ys[i + 1 :] - ys[i]
        dist = np.sqrt(dx**2 + dy**2)
        max_r = np.maximum(rs[i], rs[i + 1 :])
        suppressed[i + 1 :] |= dist < overlap_threshold * max_r
    return surviving


def draw_overlay(image: np.ndarray, candidates: list[tuple[int, int, float]]) -> np.ndarray:
    debug = image.copy()
    for idx, (x, y, r) in enumerate(candidates, start=1):
        cv2.circle(debug, (x, y), int(r), (0, 255, 255), 2)
        cv2.circle(debug, (x, y), 2, (0, 0, 255), 3)
        cv2.putText(
            debug,
            str(idx),
            (x + 6, y - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return debug


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    print(f"Settings: param2={PARAM2}, NMS threshold={NMS_THRESHOLD}")
    print()
    print(
        f"{'image':<55} {'raw':>6} {'after_nms':>10} {'visual_ref':>10} {'ratio':>8} {'det_ms':>8} {'nms_ms':>8} {'rss_mb':>8}"
    )
    print("-" * 124)

    for png in sorted(STANDARDIZED_DIR.glob("*.png")):
        image = cv2.imread(str(png))
        if image is None:
            continue

        t0 = time.perf_counter()
        raw = detect_hough(image)
        det_ms = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        final = apply_nms(raw, NMS_THRESHOLD)
        nms_ms = (time.perf_counter() - t1) * 1000
        rss_mb = _rss_mb()

        count = len(final)
        visual_ref = VISUAL_REFS.get(png.stem)
        ratio = round(count / visual_ref, 1) if visual_ref else None

        overlay = draw_overlay(image, final)
        cv2.imwrite(str(OUTPUT_DIR / f"{png.stem}_overlay.png"), overlay)

        rows.append(
            {
                "filename": png.name,
                "stem": png.stem,
                "raw_count": len(raw),
                "candidate_count": count,
                "visual_ref": visual_ref,
                "ratio": ratio,
                "param2": PARAM2,
                "nms_threshold": NMS_THRESHOLD,
                "detect_time_ms": round(det_ms, 1),
                "nms_time_ms": round(nms_ms, 1),
                "total_time_ms": round(det_ms + nms_ms, 1),
                "rss_mb": round(rss_mb, 1),
            }
        )

        ratio_str = f"{ratio:.1f}x" if ratio is not None else "N/A"
        ref_str = str(visual_ref) if visual_ref is not None else "N/A"
        print(
            f"{png.stem:<55} {len(raw):>6} {count:>10} {ref_str:>10} {ratio_str:>8} {det_ms:>7.1f} {nms_ms:>7.1f} {rss_mb:>7.1f}"
        )

    out_path = OUTPUT_DIR / "counts.json"
    out_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"\nsaved → {out_path}")


if __name__ == "__main__":
    main()
