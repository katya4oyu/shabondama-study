"""EXP-10: 虹色（薄膜干渉）マスクによる前景検出

シャボン玉の薄膜干渉（虹色）は草・葉・地面にない泡固有の光学特性。
「局所的に色相が急変する領域」を検出してマスクにする。

アプローチ A: 局所色相勾配（hue gradient）
    色相チャネルに Sobel フィルタをかけ、色相変化が大きい領域を抽出。
    ただし色相はシクリック（0-179）なので折り返し補正が必要。

アプローチ B: 彩度 × 明度マスク（淡い虹色ゾーン）
    虹色は "pastel" ——程よい彩度（低すぎず高すぎず）で明るい。
    草・葉は濃い緑（高彩度）、地面は低彩度低明度。
    S: [20, 160] × V: [80, 255] で "泡らしい明るいパステル" を選ぶ。

スイープ: A と B を組み合わせた 4 条件を比較。
    - A のみ（hue_gradient > しきい値）
    - B のみ（pastel ゾーン）
    - A ∩ B（AND）
    - A ∪ B（OR、より広く取る）

最後に EXP-05（param2=50 + NMS=0.5）と組み合わせる。

Usage:
    uv run python experiments/exp_10_iridescence_mask.py
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
OUTPUT_DIR = Path("data/outputs/exp-10")

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

# スイープするマスク条件
MASK_MODES = ["hue_grad", "pastel", "and", "or"]


def _rss_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024) if platform.system() == "Darwin" else rss / 1024


def hue_gradient_mask(hsv: np.ndarray, grad_thresh: int = 15) -> np.ndarray:
    """
    色相チャネルの局所勾配が大きい領域を 1 にする。
    色相はシクリック（0-179）なので折り返し補正: 差が90超なら 180 から引く。
    """
    h = hsv[:, :, 0].astype(np.int16)

    # x 方向の差分
    dx = np.abs(np.diff(h, axis=1, append=h[:, -1:]))
    dx = np.where(dx > 90, 180 - dx, dx)

    # y 方向の差分
    dy = np.abs(np.diff(h, axis=0, append=h[-1:, :]))
    dy = np.where(dy > 90, 180 - dy, dy)

    grad_mag = np.sqrt(dx.astype(float)**2 + dy.astype(float)**2).astype(np.uint8)

    # しきい値化 → 膨張で領域を繋ぐ
    _, mask = cv2.threshold(grad_mag, grad_thresh, 1, cv2.THRESH_BINARY)
    kernel = np.ones((15, 15), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=3)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask.astype(np.uint8)


def pastel_mask(hsv: np.ndarray) -> np.ndarray:
    """
    S: [20, 160] × V: [80, 255] の "明るいパステル" 領域を 1 にする。
    草木（高 S 高 V 緑）・地面（低 V）・白い壁（低 S）を除外する。
    """
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    mask = ((s >= 20) & (s <= 160) & (v >= 80)).astype(np.uint8)
    kernel = np.ones((11, 11), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.dilate(mask, kernel, iterations=2)
    return mask


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
        dx = xs[i + 1:] - xs[i]
        dy = ys[i + 1:] - ys[i]
        dist = np.sqrt(dx**2 + dy**2)
        max_r = np.maximum(rs[i], rs[i + 1:])
        suppressed[i + 1:] |= dist < overlap_threshold * max_r
    return surviving


def detect_with_fg_mask(
    image_bgr: np.ndarray, fg_mask: np.ndarray
) -> list[tuple[int, int, float]]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    mean_gray = int(np.mean(gray))

    masked_gray = gray.copy()
    masked_gray[fg_mask == 0] = mean_gray

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
        if 0 <= x < image_bgr.shape[1] and 0 <= y < image_bgr.shape[0]:
            candidates.append((int(x), int(y), float(r)))
    return apply_nms(candidates, NMS_THRESHOLD)


def draw_overlay(
    image: np.ndarray,
    candidates: list[tuple[int, int, float]],
    fg_mask: np.ndarray,
) -> np.ndarray:
    # マスク範囲を半透明で可視化
    debug = image.copy()
    tint = image.copy()
    tint[fg_mask == 1] = np.clip(
        tint[fg_mask == 1].astype(int) + [40, 0, 0], 0, 255
    ).astype(np.uint8)
    debug = cv2.addWeighted(debug, 0.7, tint, 0.3, 0)

    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(debug, contours, -1, (0, 200, 0), 2)

    for x, y, r in candidates:
        cv2.circle(debug, (x, y), int(r), (0, 255, 255), 2)
        cv2.circle(debug, (x, y), 2, (0, 0, 255), 3)
    return debug


def main() -> None:
    pngs = sorted(STANDARDIZED_DIR.glob("*.png"))
    all_rows: list[dict] = []

    for mode in MASK_MODES:
        out_dir = OUTPUT_DIR / mode
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n=== mask_mode={mode} ===")
        print(
            f"{'image':<55} {'candidates':>10} {'visual_ref':>10} {'ratio':>8} "
            f"{'mask%':>7} {'ms':>8} {'rss_mb':>8}"
        )
        print("-" * 114)

        for png in pngs:
            image = cv2.imread(str(png))
            if image is None:
                continue

            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

            t0 = time.perf_counter()
            mask_hg = hue_gradient_mask(hsv)
            mask_ps = pastel_mask(hsv)

            if mode == "hue_grad":
                fg_mask = mask_hg
            elif mode == "pastel":
                fg_mask = mask_ps
            elif mode == "and":
                fg_mask = (mask_hg & mask_ps).astype(np.uint8)
            else:  # or
                fg_mask = (mask_hg | mask_ps).astype(np.uint8)

            candidates = detect_with_fg_mask(image, fg_mask)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            rss_mb = _rss_mb()

            count = len(candidates)
            visual_ref = VISUAL_REFS.get(png.stem)
            ratio = round(count / visual_ref, 1) if visual_ref else None
            mask_pct = round(100.0 * fg_mask.sum() / fg_mask.size, 1)

            cv2.imwrite(str(out_dir / f"{png.stem}_overlay.png"), draw_overlay(image, candidates, fg_mask))
            # マスク単体も保存
            mask_vis = np.zeros_like(image)
            mask_vis[fg_mask == 1] = (0, 200, 80)
            cv2.imwrite(str(out_dir / f"{png.stem}_mask.png"), cv2.addWeighted(image, 0.5, mask_vis, 0.5, 0))

            all_rows.append({
                "mask_mode": mode,
                "filename": png.name,
                "stem": png.stem,
                "candidate_count": count,
                "visual_ref": visual_ref,
                "ratio": ratio,
                "mask_pct": mask_pct,
                "time_ms": round(elapsed_ms, 1),
                "rss_mb": round(rss_mb, 1),
            })

            ratio_str = f"{ratio:.1f}x" if ratio is not None else "N/A"
            ref_str = str(visual_ref) if visual_ref is not None else "N/A"
            print(
                f"{png.stem:<55} {count:>10} {ref_str:>10} {ratio_str:>8} "
                f"{mask_pct:>6.1f}% {elapsed_ms:>7.1f} {rss_mb:>7.1f}"
            )

    out_path = OUTPUT_DIR / "counts_by_mask_mode.json"
    out_path.write_text(json.dumps(all_rows, indent=2, ensure_ascii=False))
    print(f"\nsaved → {out_path}")


if __name__ == "__main__":
    main()
