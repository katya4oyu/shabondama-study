"""EXP-03: NMS（Non-Maximum Suppression）による重複円の除去

ほぼ同一位置にある重複候補を抑制し、1 泡 → 1 候補に近づける。
新規依存なし（純 numpy 実装）。

アルゴリズム:
    1. 候補を半径降順にソート（大きい円が優先生存）
    2. 生存円の中心から overlap_threshold * max(r_a, r_b) 以内の
       小さい円を suppressed に追加
    3. overlap_threshold = 0.3 / 0.5 / 0.7 でスイープ

仮説: 過検出の大半は同一輪郭への重複票。
     NMS 後、soap_bubble_closeup と irregular_bubble（各 1 泡）が
     10 候補以下に収まるはず。

Usage:
    uv run python experiments/exp_03_nms.py
"""

from __future__ import annotations

import json
import platform
import resource
import time
from pathlib import Path

import cv2
import numpy as np

from shabondama_study.detect import detect_bubble_candidates


def _rss_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024) if platform.system() == "Darwin" else rss / 1024

STANDARDIZED_DIR = Path("data/images/bubble-detection/standardized/long-edge-1600-png")
OUTPUT_DIR = Path("data/outputs/exp-03")

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

OVERLAP_THRESHOLDS = [0.3, 0.5, 0.7]


def apply_nms(
    candidates: list[tuple[int, int, float]], overlap_threshold: float
) -> list[tuple[int, int, float]]:
    if not candidates:
        return []

    # 半径降順ソート（大きい円を優先）
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
        # i より後（半径が小さい）の円のうち、中心が近いものを suppress
        dx = xs[i + 1 :] - xs[i]
        dy = ys[i + 1 :] - ys[i]
        dist = np.sqrt(dx**2 + dy**2)
        max_r = np.maximum(rs[i], rs[i + 1 :])
        overlap = dist < overlap_threshold * max_r
        suppressed[i + 1 :] |= overlap

    return surviving


def draw_overlay(image: np.ndarray, candidates: list[tuple[int, int, float]]) -> np.ndarray:
    debug = image.copy()
    for x, y, r in candidates:
        cv2.circle(debug, (x, y), int(r), (0, 255, 255), 2)
        cv2.circle(debug, (x, y), 2, (0, 0, 255), 3)
    return debug


def main() -> None:
    pngs = sorted(STANDARDIZED_DIR.glob("*.png"))

    # ベースライン候補を一度だけ取得（全画像・全しきい値で共有）
    raw_candidates: dict[str, list[tuple[int, int, float]]] = {}
    raw_counts: dict[str, int] = {}
    detect_times: dict[str, float] = {}

    for png in pngs:
        image = cv2.imread(str(png))
        if image is None:
            continue
        t0 = time.perf_counter()
        _, candidates = detect_bubble_candidates(image)
        detect_times[png.stem] = (time.perf_counter() - t0) * 1000
        raw_candidates[png.stem] = candidates
        raw_counts[png.stem] = len(candidates)

    all_rows: list[dict] = []

    for threshold in OVERLAP_THRESHOLDS:
        tag = f"nms_{int(threshold * 10):02d}"

        print(f"\n=== NMS overlap_threshold={threshold} ===")
        print(
            f"{'image':<55} {'before':>8} {'after':>8} {'visual_ref':>10} {'ratio':>8} {'det_ms':>8} {'nms_ms':>8} {'rss_mb':>8}"
        )
        print("-" * 124)

        for png in pngs:
            if png.stem not in raw_candidates:
                continue

            image = cv2.imread(str(png))
            t0 = time.perf_counter()
            candidates_after = apply_nms(raw_candidates[png.stem], threshold)
            nms_ms = (time.perf_counter() - t0) * 1000
            rss_mb = _rss_mb()

            det_ms = detect_times[png.stem]
            count_before = raw_counts[png.stem]
            count_after = len(candidates_after)
            visual_ref = VISUAL_REFS.get(png.stem)
            ratio = round(count_after / visual_ref, 1) if visual_ref else None

            out_dir = OUTPUT_DIR / tag
            out_dir.mkdir(parents=True, exist_ok=True)
            overlay = draw_overlay(image, candidates_after)
            cv2.imwrite(str(out_dir / f"{png.stem}_overlay.png"), overlay)

            all_rows.append(
                {
                    "overlap_threshold": threshold,
                    "filename": png.name,
                    "stem": png.stem,
                    "count_before_nms": count_before,
                    "candidate_count": count_after,
                    "visual_ref": visual_ref,
                    "ratio": ratio,
                    "detect_time_ms": round(det_ms, 1),
                    "nms_time_ms": round(nms_ms, 1),
                    "total_time_ms": round(det_ms + nms_ms, 1),
                    "rss_mb": round(rss_mb, 1),
                }
            )

            ratio_str = f"{ratio:.1f}x" if ratio is not None else "N/A"
            ref_str = str(visual_ref) if visual_ref is not None else "N/A"
            print(
                f"{png.stem:<55} {count_before:>8} {count_after:>8} {ref_str:>10} {ratio_str:>8} {det_ms:>7.1f} {nms_ms:>7.1f} {rss_mb:>7.1f}"
            )

    out_path = OUTPUT_DIR / "counts_by_nms.json"
    out_path.write_text(json.dumps(all_rows, indent=2, ensure_ascii=False))
    print(f"\nsaved → {out_path}")


if __name__ == "__main__":
    main()
