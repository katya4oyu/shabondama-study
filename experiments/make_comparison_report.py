"""比較レポート生成スクリプト

各実験の overlay 画像を並べた比較シートと、
全結果をまとめた Markdown レポートを生成する。

生成物:
    data/outputs/comparison/strip_{stem}.png  — 画像ごとの 5 列比較ストリップ
    data/outputs/comparison/summary_best.png  — EXP-05 全 8 枚のサマリーシート
    data/outputs/bubble-detection-comparison-report.md

比較する手法:
    [0] Original        — 入力画像（検出なし）
    [1] Baseline        — EXP-01 param2=22（スモークテストと同等）
    [2] param2=50       — EXP-01 param2=50（累積器しきい値を厳しく）
    [3] NMS thresh=0.5  — EXP-03 nms_05（重複除去のみ、param2=22）
    [4] Combined        — EXP-05 param2=50 + NMS 0.5（Phase 1 ベスト）

Usage:
    uv run python experiments/make_comparison_report.py
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import cv2
import numpy as np

# ─── パス定義 ────────────────────────────────────────────────────────────────
ORIG_DIR = Path("data/images/bubble-detection/standardized/long-edge-1600-png")
OUT_BASE = Path("data/outputs")
COMP_DIR = OUT_BASE / "comparison"

OVERLAY_DIRS = {
    "baseline":  OUT_BASE / "exp-01/param2_22",
    "param2_50": OUT_BASE / "exp-01/param2_50",
    "nms_05":    OUT_BASE / "exp-03/nms_05",
    "combined":  OUT_BASE / "exp-05",
}

REPORT_PATH = OUT_BASE / "bubble-detection-comparison-report.md"

# ─── 目視正解数 ───────────────────────────────────────────────────────────────
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

# 短縮ラベル（表示用）
SHORT_NAMES = {
    "soap_bubbles_supermacro_pd":                    "supermacro\n(~75泡)",
    "master_of_soapbubbles_cc0":                     "master\n(~145泡)",
    "irregular_bubble_cc0":                          "irregular\n(1泡)",
    "soap_bubble_closeup_cc_by_2_0":                 "closeup\n(1泡)",
    "soap_bubbles_algerian_grassland_cc_by_sa_4_0":  "grassland\n(~3泡)",
    "giant_bubble_cc_by_sa_3_0":                     "giant\n(1泡)",
    "soap_bubble_grapevine_cc_by_sa_3_0":            "grapevine\n(1泡)",
    "girl_with_soap_bubble_machine_cc_by_2_0":       "girl_machine\n(~45泡)",
}

PANEL_W = 360   # 各パネルの幅 (px)
LABEL_H = 52    # 上部ラベル領域の高さ
METHOD_LABELS = [
    "Original",
    "Baseline\n(param2=22)",
    "EXP-01\n(param2=50)",
    "EXP-03\n(NMS=0.5)",
    "EXP-05\n(p2=50+NMS)",
]


# ─── ヘルパー ─────────────────────────────────────────────────────────────────

def load_counts() -> dict[str, dict[str, int]]:
    """各実験の counts JSON から stem → candidate_count を返す。"""
    data: dict[str, dict[str, int]] = {}

    # EXP-01 (param2=22 と param2=50)
    exp01 = json.loads((OUT_BASE / "exp-01/counts_by_param2.json").read_text())
    for row in exp01:
        if row["param2"] == 22:
            data.setdefault("baseline", {})[row["stem"]] = row["candidate_count"]
        if row["param2"] == 50:
            data.setdefault("param2_50", {})[row["stem"]] = row["candidate_count"]

    # EXP-03 (nms threshold=0.5)
    exp03 = json.loads((OUT_BASE / "exp-03/counts_by_nms.json").read_text())
    for row in exp03:
        if row["overlap_threshold"] == 0.5:
            data.setdefault("nms_05", {})[row["stem"]] = row["candidate_count"]

    # EXP-05
    exp05 = json.loads((OUT_BASE / "exp-05/counts.json").read_text())
    for row in exp05:
        data.setdefault("combined", {})[row["stem"]] = row["candidate_count"]

    return data


def load_timing() -> dict[str, dict[str, float]]:
    """EXP-05 から timing データを返す (stem → {det_ms, nms_ms, total_ms})."""
    exp05 = json.loads((OUT_BASE / "exp-05/counts.json").read_text())
    result = {}
    for row in exp05:
        result[row["stem"]] = {
            "det_ms": row.get("detect_time_ms", 0),
            "nms_ms": row.get("nms_time_ms", 0),
            "total_ms": row.get("total_time_ms", 0),
            "rss_mb": row.get("rss_mb", 0),
        }
    return result


def resize_to_width(img: np.ndarray, width: int) -> np.ndarray:
    h, w = img.shape[:2]
    new_h = int(h * width / w)
    return cv2.resize(img, (width, new_h), interpolation=cv2.INTER_AREA)


def make_label_bar(text: str, width: int, height: int, bg: tuple, fg: tuple) -> np.ndarray:
    bar = np.full((height, width, 3), bg, dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    lines = text.split("\n")
    line_h = height // (len(lines) + 1)
    for i, line in enumerate(lines, 1):
        scale = 0.42
        thickness = 1
        (tw, th), _ = cv2.getTextSize(line, font, scale, thickness)
        x = (width - tw) // 2
        y = i * line_h + th // 2
        cv2.putText(bar, line, (x, y), font, scale, fg, thickness, cv2.LINE_AA)
    return bar


def add_count_badge(panel: np.ndarray, count: int | None, visual_ref: int | None) -> np.ndarray:
    """右下に候補数バッジを貼る。"""
    if count is None:
        return panel
    out = panel.copy()
    h, w = out.shape[:2]

    if visual_ref is not None and count > 0:
        ratio = count / visual_ref
        if ratio <= 3:
            color = (30, 200, 30)    # 緑: ≤3×
        elif ratio <= 20:
            color = (30, 180, 230)   # 黄: 3–20×
        else:
            color = (30, 30, 220)    # 赤: >20×
    else:
        color = (180, 180, 180)

    label = str(count)
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.65
    thickness = 2
    (tw, th), baseline = cv2.getTextSize(label, font, scale, thickness)
    pad = 6
    bx1, by1 = w - tw - pad * 2 - 2, h - th - baseline - pad * 2 - 2
    bx2, by2 = w - 2, h - 2
    cv2.rectangle(out, (bx1, by1), (bx2, by2), color, -1)
    cv2.rectangle(out, (bx1, by1), (bx2, by2), (255, 255, 255), 1)
    cv2.putText(out, label, (bx1 + pad, by2 - baseline - pad // 2),
                font, scale, (255, 255, 255), thickness, cv2.LINE_AA)
    return out


def make_strip(stem: str, counts: dict[str, dict[str, int]]) -> np.ndarray:
    """1 枚の画像について 5 手法を横並びにした比較ストリップを生成。"""
    visual_ref = VISUAL_REFS.get(stem)

    # 各パネルの画像を収集
    panels_img: list[np.ndarray] = []

    # [0] Original
    orig = cv2.imread(str(ORIG_DIR / f"{stem}.png"))
    panels_img.append(orig)

    # [1–4] 各実験の overlay
    for key in ("baseline", "param2_50", "nms_05", "combined"):
        overlay_path = OVERLAY_DIRS[key] / f"{stem}_overlay.png"
        img = cv2.imread(str(overlay_path))
        panels_img.append(img)

    # 高さを揃えるため最初の有効画像の縦横比を基準にする
    base_img = next(p for p in panels_img if p is not None)
    bh, bw = base_img.shape[:2]
    target_h = int(bh * PANEL_W / bw)

    panels: list[np.ndarray] = []
    count_vals: list[int | None] = [None]  # original は count なし
    count_vals += [counts.get(k, {}).get(stem) for k in ("baseline", "param2_50", "nms_05", "combined")]

    for img, cnt, method_label in zip(panels_img, count_vals, METHOD_LABELS):
        if img is None:
            panel = np.zeros((target_h, PANEL_W, 3), dtype=np.uint8)
        else:
            panel = resize_to_width(img, PANEL_W)
            # 高さを target_h に揃える（crop or pad）
            ph = panel.shape[0]
            if ph > target_h:
                panel = panel[:target_h]
            elif ph < target_h:
                pad = np.zeros((target_h - ph, PANEL_W, 3), dtype=np.uint8)
                panel = np.vstack([panel, pad])

        panel = add_count_badge(panel, cnt, visual_ref)

        # 上部にメソッドラベルバーを付加
        bg = (50, 50, 50)
        fg = (240, 240, 240)
        label_bar = make_label_bar(method_label, PANEL_W, LABEL_H, bg, fg)
        panel = np.vstack([label_bar, panel])
        panels.append(panel)

    # 左端に画像名ラベルを縦書き風に付ける（細い帯）
    strip = np.hstack(panels)

    # 上端にこの画像の ref 情報を 1 行追加
    ref_str = f"visual ref ≈ {visual_ref}" if visual_ref else "no ref"
    info_bar = make_label_bar(
        f"{stem}  |  {ref_str}",
        strip.shape[1], 30, (20, 20, 20), (200, 200, 200)
    )
    strip = np.vstack([info_bar, strip])
    return strip


def make_summary_sheet(stems: list[str], counts: dict[str, dict[str, int]]) -> np.ndarray:
    """EXP-05 の全 8 枚をサムネイルで並べたサマリーシート。"""
    thumb_w = 380
    cols = 4
    rows_n = (len(stems) + cols - 1) // cols

    cells = []
    for stem in stems:
        img = cv2.imread(str(OVERLAY_DIRS["combined"] / f"{stem}_overlay.png"))
        if img is None:
            img = np.zeros((200, thumb_w, 3), dtype=np.uint8)
        thumb = resize_to_width(img, thumb_w)

        cnt = counts.get("combined", {}).get(stem)
        visual_ref = VISUAL_REFS.get(stem)
        thumb = add_count_badge(thumb, cnt, visual_ref)

        short = SHORT_NAMES.get(stem, stem)
        bar = make_label_bar(short, thumb_w, 44, (30, 30, 30), (230, 230, 230))
        cell = np.vstack([bar, thumb])
        cells.append(cell)

    # 全セルの高さを揃える
    max_h = max(c.shape[0] for c in cells)
    padded = []
    for c in cells:
        dh = max_h - c.shape[0]
        if dh > 0:
            pad = np.zeros((dh, c.shape[1], 3), dtype=np.uint8)
            c = np.vstack([c, pad])
        padded.append(c)

    # グリッドに並べる
    grid_rows = []
    for r in range(rows_n):
        row_cells = padded[r * cols: (r + 1) * cols]
        while len(row_cells) < cols:
            row_cells.append(np.zeros_like(padded[0]))
        grid_rows.append(np.hstack(row_cells))

    # タイトルバー
    title = "EXP-05: Combined (param2=50 + NMS threshold=0.5)  |  badge color: green≤3× / yellow≤20× / red>20×"
    title_bar = make_label_bar(title, grid_rows[0].shape[1], 36, (10, 10, 10), (220, 220, 220))
    return np.vstack([title_bar] + grid_rows)


# ─── レポート生成 ─────────────────────────────────────────────────────────────

def write_report(stems: list[str], counts: dict[str, dict[str, int]], timing: dict[str, dict[str, float]]) -> None:
    lines: list[str] = []

    def w(s: str = "") -> None:
        lines.append(s)

    w("# シャボン玉検出 — 手法比較レポート")
    w()
    w("実施日: 2026-05-21  ")
    w("入力: `data/images/bubble-detection/standardized/long-edge-1600-png/` (8 枚)")
    w()
    w("---")
    w()
    w("## 比較した手法")
    w()
    w("| 手法 | 設定 | 変更点 |")
    w("|------|------|--------|")
    w("| **Baseline** | param2=22, NMS なし | スモークテストと同等のデフォルト設定 |")
    w("| **EXP-01** | param2=50, NMS なし | 累積器しきい値を厳しくして弱いエッジ反応を抑制 |")
    w("| **EXP-03** | param2=22, NMS=0.5 | 重複円を後処理で除去（param2 はデフォルトのまま） |")
    w("| **EXP-05** | param2=50, NMS=0.5 | EXP-01 と EXP-03 の組み合わせ（Phase 1 ベスト） |")
    w()
    w("---")
    w()
    w("## 全体サマリー（候補数）")
    w()
    w("バッジ色の凡例: 🟢 ≤3× / 🟡 ≤20× / 🔴 >20×")
    w()

    # サマリーテーブル
    w("| 画像 | 目視正解 | Baseline | EXP-01<br>p2=50 | EXP-03<br>NMS | EXP-05<br>Combined | 改善率 |")
    w("|------|--------:|---------:|----------------:|--------------:|-------------------:|-------:|")

    def badge(count: int | None, ref: int | None) -> str:
        if count is None:
            return "—"
        if ref is None:
            return str(count)
        r = count / ref
        icon = "🟢" if r <= 3 else ("🟡" if r <= 20 else "🔴")
        return f"{icon} {count}"

    for stem in stems:
        ref = VISUAL_REFS.get(stem, 0)
        bl  = counts.get("baseline",  {}).get(stem)
        p50 = counts.get("param2_50", {}).get(stem)
        nms = counts.get("nms_05",    {}).get(stem)
        comb= counts.get("combined",  {}).get(stem)
        improvement = f"{bl/comb:.1f}×↓" if bl and comb and comb > 0 else "—"
        short = stem.replace("soap_bubbles_", "").replace("soap_bubble_", "").replace("_cc_by_sa_4_0", "").replace("_cc_by_sa_3_0", "").replace("_cc_by_2_0", "").replace("_cc0", "").replace("_pd", "")
        w(f"| {short} | {ref} | {badge(bl, ref)} | {badge(p50, ref)} | {badge(nms, ref)} | {badge(comb, ref)} | {improvement} |")

    w()
    w(f"![]({(COMP_DIR / 'summary_best.png').relative_to(OUT_BASE.parent)})")
    w()
    w("---")
    w()
    w("## 画像ごとの比較ストリップ")
    w()
    w("各ストリップ: Original | Baseline | param2=50 | NMS=0.5 | Combined  ")
    w("右下の数字 = 候補数 （バッジ色は上記凡例と同じ）")
    w()

    for stem in stems:
        ref = VISUAL_REFS.get(stem)
        comb = counts.get("combined", {}).get(stem)
        ratio_str = f"{comb/ref:.1f}×" if (comb and ref) else "N/A"
        short = SHORT_NAMES.get(stem, stem).replace("\n", " ")
        w(f"### {short}")
        w()
        w(f"目視正解 ≈ {ref}  |  EXP-05 候補数: {comb}  |  倍率: {ratio_str}")
        w()
        strip_rel = (COMP_DIR / f"strip_{stem}.png").relative_to(OUT_BASE.parent)
        w(f"![]({strip_rel})")
        w()

    w("---")
    w()
    w("## タイミングとメモリ（EXP-05: param2=50 + NMS=0.5）")
    w()
    w("| 画像 | 検出 ms | NMS ms | 合計 ms | RSS MB | 推定 FPS | リアルタイム |")
    w("|------|--------:|-------:|--------:|-------:|---------:|:---:|")

    for stem in stems:
        t = timing.get(stem, {})
        det = t.get("det_ms", 0)
        nms_t = t.get("nms_ms", 0)
        total = t.get("total_ms", det + nms_t)
        rss = t.get("rss_mb", 0)
        fps = 1000 / total if total > 0 else 0
        rt = "✅" if fps >= 10 else ("⚠️" if fps >= 2 else "✗")
        short = stem.replace("soap_bubbles_", "").replace("soap_bubble_", "").replace("_cc_by_sa_4_0", "").replace("_cc_by_sa_3_0", "").replace("_cc_by_2_0", "").replace("_cc0", "").replace("_pd", "")
        w(f"| {short} | {det:.1f} | {nms_t:.1f} | {total:.1f} | {rss:.0f} | {fps:.1f} | {rt} |")

    w()
    w("> **注:** NMS のコストは 0.1〜4ms で実質ゼロ。  ")
    w("> 処理時間は **候補数に正比例** するため、param2 を上げて誤候補を減らすと速度も同時に改善する。  ")
    w("> `master` が遅い（6.5 s）のは画像サイズではなく、誤候補が多い（3339 個）ため。")
    w()
    w("---")
    w()
    w("## 考察と Phase 2 方針")
    w()
    w("### 何が効いたか")
    w()
    w("**param2=50（EXP-01）**")
    w("- 弱い円形エッジ（草木・ハイライト）への反応を大幅に抑制")
    w("- `closeup`（1泡）: 600 → 22 候補")
    w("- 処理時間も同時に短縮（候補数減少に伴う副次効果）")
    w()
    w("**NMS threshold=0.5（EXP-03）**")
    w("- 同一輪郭への重複票を除去")
    w("- `supermacro`（75泡密集）: 1969 → 146 候補（1.9×）")
    w("- 処理コスト: 0.1〜4ms（実質ゼロ）")
    w()
    w("**組み合わせ（EXP-05）**")
    w("- girl_with_machine: **1.2×**（55候補/45泡）")
    w("- supermacro: **1.3×**（98候補/75泡）")
    w("- master: **2.0×**（288候補/145泡）")
    w("- 上記 3 枚はリアルタイムでも実用圏")
    w()
    w("### 何が効かなかったか")
    w()
    w("| 手法 | 結果 | 理由 |")
    w("|------|------|------|")
    w("| maxRadius 制限（EXP-02） | 無効 | 誤候補の大半は小半径 — 上限制限は無意味 |")
    w("| HSV 色マスク（EXP-04） | 無効〜逆効果 | 誤検出はエッジパターン由来であり色ではない |")
    w()
    w("### 残存する失敗パターン")
    w()
    w("| パターン | 代表画像 | EXP-05 倍率 | 原因 |")
    w("|----------|----------|------------:|------|")
    w("| 不定形・巨大泡 | grapevine, giant | 164×, 112× | 円 Hough は非円形に多数の円を当てはめる |")
    w("| 単泡への重複 | closeup, irregular | 8×, 10× | NMS でも完全には排除できない同心円 |")
    w("| 屋外複雑背景 | grassland | 29× | 草木エッジが残存（色マスク無効） |")
    w()
    w("### Phase 2 の方針")
    w()
    w("Phase 2 Gate（8枚中5枚 ≤3×）は **3/8** で未達。代替検出器が必要。")
    w()
    w("- **EXP-06 SimpleBlobDetector**: connectedComponents ベースのため重複票が原理的に発生しない")
    w("- **EXP-07 LoG blob**: スケール正規化により葉テクスチャを泡スケールで blob と誤認しにくい")
    w("- **EXP-08 DoH blob**: LoG より高速で supermacro 密集泡での比較に適する")
    w()
    w("---")
    w()
    w("*生成: `experiments/make_comparison_report.py`*")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"report → {REPORT_PATH}")


# ─── メイン ───────────────────────────────────────────────────────────────────

def main() -> None:
    COMP_DIR.mkdir(parents=True, exist_ok=True)

    counts = load_counts()
    timing = load_timing()
    stems = sorted(VISUAL_REFS.keys())

    # 1. 各画像の比較ストリップ
    for stem in stems:
        print(f"  strip: {stem}")
        strip = make_strip(stem, counts)
        cv2.imwrite(str(COMP_DIR / f"strip_{stem}.png"), strip)

    # 2. EXP-05 サマリーシート
    print("  summary sheet...")
    summary = make_summary_sheet(stems, counts)
    cv2.imwrite(str(COMP_DIR / "summary_best.png"), summary)

    # 3. Markdown レポート
    write_report(stems, counts, timing)

    print(f"\ndone. outputs → {COMP_DIR}")
    print(f"      report  → {REPORT_PATH}")


if __name__ == "__main__":
    main()
