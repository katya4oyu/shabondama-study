"""EXP-07: LoG (Laplacian of Gaussian) blob 検出

skimage.feature.blob_log を使う。スケール正規化されており、
葉のエッジは泡のスケールで blob と検出されにくいはずという仮説を検証する。

戻り値の sigma から半径を推定: radius ≈ sigma * sqrt(2)

スイープ:
    threshold (blob の強さのしきい値): 0.05 / 0.10 / 0.20
    max_sigma (検出する最大スケール): 50 / 100 / 150

Usage:
    uv run python experiments/exp_07_log_blob.py
"""

from __future__ import annotations

import json
import platform
import resource
import time
from pathlib import Path

import cv2
import numpy as np
from skimage.feature import blob_log

STANDARDIZED_DIR = Path("data/images/bubble-detection/standardized/long-edge-1600-png")
OUTPUT_DIR = Path("data/outputs/exp-07")

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

PARAM_SETS = [
    {"threshold": 0.05, "max_sigma": 50},
    {"threshold": 0.05, "max_sigma": 100},
    {"threshold": 0.10, "max_sigma": 50},
    {"threshold": 0.10, "max_sigma": 100},
    {"threshold": 0.20, "max_sigma": 50},
    {"threshold": 0.20, "max_sigma": 100},
]


def _rss_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024) if platform.system() == "Darwin" else rss / 1024


def draw_overlay(image: np.ndarray, blobs: np.ndarray) -> np.ndarray:
    """blobs: array of (y, x, sigma)"""
    debug = image.copy()
    for y, x, sigma in blobs:
        r = int(sigma * (2 ** 0.5))
        cv2.circle(debug, (int(x), int(y)), max(r, 4), (0, 255, 255), 2)
        cv2.circle(debug, (int(x), int(y)), 2, (0, 0, 255), 3)
    return debug


def main() -> None:
    pngs = sorted(STANDARDIZED_DIR.glob("*.png"))
    all_rows: list[dict] = []

    for ps in PARAM_SETS:
        thresh = ps["threshold"]
        max_sig = ps["max_sigma"]
        tag = f"thresh{int(thresh*100):02d}_maxsig{max_sig}"
        out_dir = OUTPUT_DIR / tag
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n=== threshold={thresh}, max_sigma={max_sig} ===")
        print(f"{'image':<55} {'candidates':>10} {'visual_ref':>10} {'ratio':>8} {'ms':>8} {'rss_mb':>8}")
        print("-" * 108)

        for png in pngs:
            image = cv2.imread(str(png))
            if image is None:
                continue

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            # skimage は [0,1] float を期待する
            gray_f = gray.astype(np.float32) / 255.0

            t0 = time.perf_counter()
            blobs = blob_log(
                gray_f,
                min_sigma=3,
                max_sigma=max_sig,
                num_sigma=10,
                threshold=thresh,
                overlap=0.5,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            rss_mb = _rss_mb()

            count = len(blobs)
            visual_ref = VISUAL_REFS.get(png.stem)
            ratio = round(count / visual_ref, 1) if visual_ref else None

            overlay = draw_overlay(image, blobs)
            cv2.imwrite(str(out_dir / f"{png.stem}_overlay.png"), overlay)

            all_rows.append({
                "threshold": thresh,
                "max_sigma": max_sig,
                "filename": png.name,
                "stem": png.stem,
                "candidate_count": count,
                "visual_ref": visual_ref,
                "ratio": ratio,
                "time_ms": round(elapsed_ms, 1),
                "rss_mb": round(rss_mb, 1),
            })

            ratio_str = f"{ratio:.1f}x" if ratio is not None else "N/A"
            ref_str = str(visual_ref) if visual_ref is not None else "N/A"
            print(f"{png.stem:<55} {count:>10} {ref_str:>10} {ratio_str:>8} {elapsed_ms:>7.1f} {rss_mb:>7.1f}")

    out_path = OUTPUT_DIR / "counts_by_params.json"
    out_path.write_text(json.dumps(all_rows, indent=2, ensure_ascii=False))
    print(f"\nsaved → {out_path}")


if __name__ == "__main__":
    main()
