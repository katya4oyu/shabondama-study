"""EXP-00: ベースライン候補数テーブル

全 8 枚の standardized PNG に対してデフォルト HoughCircles を実行し、
候補数・目視正解数・過検出倍率を JSON で保存する。
以降の全実験がこのファイルと比較して改善を確認する数値アンカー。

Usage:
    uv run python experiments/exp_00_count_baseline.py
"""

from __future__ import annotations

import json
import platform
import resource
import time
from pathlib import Path

import cv2

from shabondama_study.detect import detect_bubble_candidates


def _rss_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS returns bytes; Linux returns KiB
    return rss / (1024 * 1024) if platform.system() == "Darwin" else rss / 1024

STANDARDIZED_DIR = Path("data/images/bubble-detection/standardized/long-edge-1600-png")
OUTPUT_DIR = Path("data/outputs/exp-00")

# 目視正解数（bubble-detection-report.md より）
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


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    print(f"{'image':<55} {'candidates':>10} {'visual_ref':>10} {'ratio':>8} {'ms':>8} {'rss_mb':>8}")
    print("-" * 108)

    for png in sorted(STANDARDIZED_DIR.glob("*.png")):
        stem = png.stem
        image = cv2.imread(str(png))
        if image is None:
            print(f"SKIP (unreadable): {png}")
            continue

        t0 = time.perf_counter()
        _, candidates = detect_bubble_candidates(image)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        rss_mb = _rss_mb()

        count = len(candidates)
        visual_ref = VISUAL_REFS.get(stem)
        ratio = round(count / visual_ref, 1) if visual_ref else None

        rows.append(
            {
                "filename": png.name,
                "stem": stem,
                "candidate_count": count,
                "visual_ref": visual_ref,
                "ratio": ratio,
                "time_ms": round(elapsed_ms, 1),
                "rss_mb": round(rss_mb, 1),
            }
        )

        ratio_str = f"{ratio:.1f}x" if ratio is not None else "N/A"
        ref_str = str(visual_ref) if visual_ref is not None else "N/A"
        print(f"{stem:<55} {count:>10} {ref_str:>10} {ratio_str:>8} {elapsed_ms:>7.1f} {rss_mb:>7.1f}")

    out_path = OUTPUT_DIR / "counts.json"
    out_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"\nsaved → {out_path}")


if __name__ == "__main__":
    main()
