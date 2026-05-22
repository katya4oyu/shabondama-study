"""EXP-06: SimpleBlobDetector

HoughCircles の代替として OpenCV SimpleBlobDetector を試す。
connectedComponents ベースなので、同一輪郭への重複票が原理的に発生しない。

仮説: 単泡画像（closeup, irregular）で自然に 1〜5 候補に収まる。
     密集泡（supermacro, master）では泡の孤立度が低いため苦労するかもしれない。

パラメータスイープ:
    minCircularity: 0.5 / 0.7 / 0.8
    minConvexity:   0.7 / 0.85
    （組み合わせ 6 通り）

Usage:
    uv run python experiments/exp_06_simpleblob.py
"""

from __future__ import annotations

import json
import platform
import resource
import time
from pathlib import Path

import cv2
import numpy as np

STANDARDIZED_DIR = Path("data/images/bubble-detection/standardized/long-edge-1600-png")
OUTPUT_DIR = Path("data/outputs/exp-06")

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

# スイープするパラメータ組み合わせ
PARAM_SETS = [
    {"minCircularity": 0.5, "minConvexity": 0.70},
    {"minCircularity": 0.5, "minConvexity": 0.85},
    {"minCircularity": 0.7, "minConvexity": 0.70},
    {"minCircularity": 0.7, "minConvexity": 0.85},
    {"minCircularity": 0.8, "minConvexity": 0.70},
    {"minCircularity": 0.8, "minConvexity": 0.85},
]


def _rss_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024) if platform.system() == "Darwin" else rss / 1024


def make_detector(min_circularity: float, min_convexity: float) -> cv2.SimpleBlobDetector:
    params = cv2.SimpleBlobDetector_Params()
    params.filterByArea = True
    params.minArea = 200       # ≈ radius 8px の円面積
    params.maxArea = 500_000   # 大きな泡も拾う
    params.filterByCircularity = True
    params.minCircularity = min_circularity
    params.filterByConvexity = True
    params.minConvexity = min_convexity
    params.filterByInertia = True
    params.minInertiaRatio = 0.3
    params.filterByColor = False
    return cv2.SimpleBlobDetector_create(params)


def draw_overlay(image: np.ndarray, keypoints: list) -> np.ndarray:
    debug = image.copy()
    for kp in keypoints:
        x, y = int(kp.pt[0]), int(kp.pt[1])
        r = int(kp.size / 2)
        cv2.circle(debug, (x, y), max(r, 4), (0, 255, 255), 2)
        cv2.circle(debug, (x, y), 2, (0, 0, 255), 3)
    return debug


def main() -> None:
    pngs = sorted(STANDARDIZED_DIR.glob("*.png"))
    all_rows: list[dict] = []

    for ps in PARAM_SETS:
        circ = ps["minCircularity"]
        conv = ps["minConvexity"]
        tag = f"circ{int(circ*10):02d}_conv{int(conv*100):02d}"
        out_dir = OUTPUT_DIR / tag
        out_dir.mkdir(parents=True, exist_ok=True)

        detector = make_detector(circ, conv)

        print(f"\n=== minCircularity={circ}, minConvexity={conv} ===")
        print(f"{'image':<55} {'candidates':>10} {'visual_ref':>10} {'ratio':>8} {'ms':>8} {'rss_mb':>8}")
        print("-" * 108)

        for png in pngs:
            image = cv2.imread(str(png))
            if image is None:
                continue

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (7, 7), 1.5)

            t0 = time.perf_counter()
            keypoints = detector.detect(blurred)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            rss_mb = _rss_mb()

            count = len(keypoints)
            visual_ref = VISUAL_REFS.get(png.stem)
            ratio = round(count / visual_ref, 1) if visual_ref else None

            overlay = draw_overlay(image, keypoints)
            cv2.imwrite(str(out_dir / f"{png.stem}_overlay.png"), overlay)

            all_rows.append({
                "minCircularity": circ,
                "minConvexity": conv,
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
