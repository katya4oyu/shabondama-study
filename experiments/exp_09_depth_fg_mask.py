"""EXP-09: Depth Anything V2 による前景マスクで背景テクスチャを除去

背景分離の問題（algerian_grassland 29×, grapevine 164×, closeup 8×）に対して、
単眼深度推定でカメラに近い領域（＝泡がある前景）を抽出し、
その領域内だけで EXP-05（param2=50 + NMS=0.5）を走らせる。

仮説: 草・葉はカメラから遠い（深度が浅い）ので、深度しきい値で
     前景マスクを作れば背景テクスチャ由来の誤候補が消える。

モデル: depth-anything/Depth-Anything-V2-Small-hf
        初回実行時に HuggingFace から ~97MB を自動ダウンロード。
        Apple Silicon MPS を自動検出して使用。

スイープ:
    depth_threshold（前景と判定する正規化深度の下限）: 0.3 / 0.4 / 0.5
    （値が大きいほど「より手前のみ残す」＝厳しいマスク）

Usage:
    uv run python experiments/exp_09_depth_fg_mask.py
"""

from __future__ import annotations

import json
import platform
import resource
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from transformers import pipeline

STANDARDIZED_DIR = Path("data/images/bubble-detection/standardized/long-edge-1600-png")
OUTPUT_DIR = Path("data/outputs/exp-09")

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

DEPTH_THRESHOLDS = [0.3, 0.4, 0.5]
PARAM2 = 50
NMS_THRESHOLD = 0.5
MIN_RADIUS = 8
MAX_RADIUS = 240


def _rss_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024) if platform.system() == "Darwin" else rss / 1024


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


def detect_with_depth_mask(
    image_bgr: np.ndarray,
    depth_norm: np.ndarray,
    depth_threshold: float,
) -> list[tuple[int, int, float]]:
    """depth_norm: [0,1] 正規化済み深度マップ（高い値＝手前）"""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    mean_gray = int(np.mean(gray))

    # 前景マスク: 深度 > threshold の領域を残す
    fg_mask = (depth_norm >= depth_threshold).astype(np.uint8)
    # 小ノイズ除去
    kernel = np.ones((7, 7), np.uint8)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_DILATE, kernel)

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
    depth_norm: np.ndarray,
    depth_threshold: float,
) -> np.ndarray:
    # 深度マップをカラーで背景に重ねる（青=遠い、赤=近い）
    depth_u8 = (depth_norm * 255).astype(np.uint8)
    depth_color = cv2.applyColorMap(depth_u8, cv2.COLORMAP_TURBO)
    depth_color = cv2.resize(depth_color, (image.shape[1], image.shape[0]))
    debug = cv2.addWeighted(image, 0.6, depth_color, 0.4, 0)

    # 前景マスク境界を白で描画
    fg_mask = (depth_norm >= depth_threshold).astype(np.uint8)
    kernel = np.ones((7, 7), np.uint8)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_DILATE, kernel)
    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(debug, contours, -1, (255, 255, 255), 2)

    for x, y, r in candidates:
        cv2.circle(debug, (x, y), int(r), (0, 255, 255), 2)
        cv2.circle(debug, (x, y), 2, (0, 0, 255), 3)
    return debug


def save_depth_vis(depth_norm: np.ndarray, path: Path, orig_size: tuple[int, int]) -> None:
    """深度マップを TURBO カラーマップで可視化して保存。"""
    depth_u8 = (depth_norm * 255).astype(np.uint8)
    color = cv2.applyColorMap(depth_u8, cv2.COLORMAP_TURBO)
    color = cv2.resize(color, orig_size)
    cv2.imwrite(str(path), color)


def main() -> None:
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"device: {device}")
    print("loading Depth Anything V2 Small ...")

    t_load = time.perf_counter()
    depth_pipe = pipeline(
        task="depth-estimation",
        model="depth-anything/Depth-Anything-V2-Small-hf",
        device=device,
    )
    load_ms = (time.perf_counter() - t_load) * 1000
    print(f"model loaded in {load_ms:.0f}ms, RSS={_rss_mb():.0f}MB\n")

    pngs = sorted(STANDARDIZED_DIR.glob("*.png"))
    all_rows: list[dict] = []

    # まず全画像の深度マップを一括生成（モデルロード後に連続して走らせる）
    print("generating depth maps ...")
    depth_maps: dict[str, np.ndarray] = {}
    depth_times: dict[str, float] = {}

    for png in pngs:
        pil_img = Image.open(png).convert("RGB")
        t0 = time.perf_counter()
        result = depth_pipe(pil_img)
        depth_ms = (time.perf_counter() - t0) * 1000
        # result["depth"] は PIL Image (L mode)
        depth_arr = np.array(result["depth"]).astype(np.float32)
        # 高い値 = 手前（モデルによって逆の場合あり → 後で確認）
        d_min, d_max = depth_arr.min(), depth_arr.max()
        depth_norm = (depth_arr - d_min) / (d_max - d_min + 1e-8)
        depth_maps[png.stem] = depth_norm
        depth_times[png.stem] = depth_ms
        print(f"  {png.stem}: {depth_ms:.0f}ms")

    # 深度マップのビジュアルを保存（threshold 依存なしの共通資料）
    vis_dir = OUTPUT_DIR / "depth_vis"
    vis_dir.mkdir(parents=True, exist_ok=True)
    for png in pngs:
        img = cv2.imread(str(png))
        orig_size = (img.shape[1], img.shape[0])
        save_depth_vis(depth_maps[png.stem], vis_dir / f"{png.stem}_depth.png", orig_size)

    print()

    # 各しきい値でスイープ
    for thresh in DEPTH_THRESHOLDS:
        tag = f"thresh_{int(thresh * 10):02d}"
        out_dir = OUTPUT_DIR / tag
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"=== depth_threshold={thresh} ===")
        print(f"{'image':<55} {'candidates':>10} {'visual_ref':>10} {'ratio':>8} {'depth_ms':>9} {'det_ms':>8} {'rss_mb':>8}")
        print("-" * 116)

        for png in pngs:
            image = cv2.imread(str(png))
            if image is None:
                continue
            depth_norm = depth_maps[png.stem]
            # 深度マップを画像サイズにリサイズ
            dn_resized = cv2.resize(depth_norm, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_LINEAR)

            t0 = time.perf_counter()
            candidates = detect_with_depth_mask(image, dn_resized, thresh)
            det_ms = (time.perf_counter() - t0) * 1000
            rss_mb = _rss_mb()

            count = len(candidates)
            visual_ref = VISUAL_REFS.get(png.stem)
            ratio = round(count / visual_ref, 1) if visual_ref else None
            depth_ms = depth_times[png.stem]

            overlay = draw_overlay(image, candidates, dn_resized, thresh)
            cv2.imwrite(str(out_dir / f"{png.stem}_overlay.png"), overlay)

            all_rows.append({
                "depth_threshold": thresh,
                "filename": png.name,
                "stem": png.stem,
                "candidate_count": count,
                "visual_ref": visual_ref,
                "ratio": ratio,
                "depth_time_ms": round(depth_ms, 1),
                "detect_time_ms": round(det_ms, 1),
                "total_time_ms": round(depth_ms + det_ms, 1),
                "rss_mb": round(rss_mb, 1),
            })

            ratio_str = f"{ratio:.1f}x" if ratio is not None else "N/A"
            ref_str = str(visual_ref) if visual_ref is not None else "N/A"
            print(
                f"{png.stem:<55} {count:>10} {ref_str:>10} {ratio_str:>8} {depth_ms:>8.0f} {det_ms:>7.1f} {rss_mb:>7.1f}"
            )

        print()

    out_path = OUTPUT_DIR / "counts_by_depth_threshold.json"
    out_path.write_text(json.dumps(all_rows, indent=2, ensure_ascii=False))
    print(f"saved → {out_path}")


if __name__ == "__main__":
    main()
