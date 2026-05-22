---
title: Bubble Detection Test Assets
created_at: 2026-05-21
updated_at: 2026-05-21
status: active
kind: source
---

# Bubble Detection Test Assets

The first reusable still-image asset set lives in
`data/images/bubble-detection/`.

The asset directory contains:

- `ASSETS.md`: human-readable list of files, license notes, and useful visual
  conditions.
- `manifest.json`: machine-readable source URLs, licenses, dimensions, and
  condition tags.
- downloaded JPEG files from Wikimedia Commons.
- `standardized/long-edge-1600-png/`: generated detector inputs with EXIF
  orientation applied, RGB color, PNG format, and max long edge 1600 px.

## Selection Principle

The set is for checking whether candidate bubble detectors survive obvious
visual shifts, not for claiming benchmark coverage. Public Domain and CC0 images
were preferred. CC BY and CC BY-SA images were added only where they covered
important conditions missing from the Public Domain / CC0 subset.

## Condition Axes

The initial research treated these as likely to affect detection precision:

- bubble count: single, few, many, dense cluster
- bubble scale: small, medium, large, macro
- human presence: none or visible person
- scene: indoor, outdoor, close-up/studio-like, snow/frozen
- background brightness: dark, mixed, bright
- background complexity: plain, textured, cluttered
- appearance: round or irregular shape, transparent rim, iridescent film,
  frozen/opaque texture

## Current Coverage

The saved set includes close-up dense bubbles, a large outdoor
street-performance scene with people, an irregular bubble, a single outdoor
close-up, a clothed child blowing bubbles in grass, a giant bubble with an adult
performer, a single garden bubble against leafy clutter, and a clothed child
using a bubble machine with many small bubbles.

This is enough to begin smoke-testing false positives and missed detections
across obvious condition changes. It is not yet balanced: it lacks annotated
ground truth, video frames, indoor scenes verified by visual review, and
systematic background distractors.

## Review Discipline

Image acquisition is part of the experiment setup. Do not accept images from
title or source metadata alone. Open the downloaded file, check that the actual
pixels match the intended condition tags, and record the visual review result in
`manifest.json`.

Reject images whose visible content makes the condition tags misleading, whose
bubble boundary is not useful for the detector being tested, or whose human
subject matter is unsuitable for a validation fixture.

## Format And Resolution

Do not feed arbitrary downloaded files directly into comparable experiments.
Use `scripts/prepare_bubble_detection_assets.py` to generate the standardized
input tier from the accepted originals.

The current standard tier is PNG, RGB, EXIF-normalized, and max long edge 1600
px without upscaling smaller images. PNG is chosen for generated inputs to avoid
adding another lossy compression pass; source originals remain available for
provenance and future high-resolution variants.

## Reuse Notes

Keep source page URLs and license URLs with any copied subset. For CC BY and
CC BY-SA files, include attribution when publishing results, distributing a
derived dataset, or showing derived outputs outside local experiments.

## スモーク入りシャボン玉アセットの取得方針

### 対象の特性

スモーク入りシャボン玉（例: [toomo.net BubbleFog](https://www.toomo.net/bubblefog.html)）は
内部にフォグマシン由来の霧（水滴または glycol 液滴）が充填されており、
通常の透明シャボン玉と異なり**不透明な白/灰色の球体**として撮影される。

可視光・NIR 両方で明確な球形シルエットが得られるため、
Phase 1〜2 で問題となった「背景透過による検出困難」が解消される。

### フリーアセットの現状

Wikimedia Commons には専用カテゴリが存在しない（2026-05-22 時点）。
スモーク泡は演出・パフォーマンス用途で使われるためフリー素材の流通が少ない。

### 取得手段

**手段 1（推奨）: 自分で撮影**

手持ちの IR カメラまたはスマホで 1 枚撮るだけで実験開始できる。
最も品質・条件をコントロールしやすい。

**手段 2: YouTube CC ライセンス動画からフレーム抽出**

```bash
# CC BY ライセンス動画を検索（YouTube Data API または手動）
# 検索キーワード: "bubble fog" "smoke bubble" "fog bubble" "シャボン玉 スモーク"
# ライセンスフィルター: Creative Commons のみ

# yt-dlp でダウンロード（CC ライセンス確認後）
uv run yt-dlp --write-info-json -f "bestvideo[ext=mp4]" "VIDEO_URL"

# 特定フレームを抽出（例: 1fps）
ffmpeg -i video.mp4 -vf fps=1 frames/frame_%04d.png
```

**手段 3: Flickr CC 検索**

```
https://flickr.com/search/?text=bubble+fog&license=2,3,4,5,6,9
```

`license=` パラメータ: 2=CC BY, 3=CC BY-NC, 4=CC BY-SA, 5=CC BY-NC-SA, 6=CC BY-ND, 9=CC0

### アセット受け入れ基準（スモーク泡向け）

既存の透明泡と同じ [Review Discipline](#review-discipline) に加え:

- スモークが十分に充填されて球形が不透明に見えること（半透明可、完全透明は不可）
- 可視光または NIR での鮮明なシルエットがあること
- 撮影条件（屋外/屋内、背景）を manifest に記録すること

## 2026-05-21 Detection Scope Classification

Phase 1〜2 の実験結果を踏まえ、各画像の検出スコープを分類した。`manifest.json` の `detection_scope` フィールドに記録済み。

| 区分 | 画像 | 理由 |
|------|------|------|
| **primary** | master, closeup, algerian_grassland, grapevine, girl_with_machine | 典型的な浮遊シャボン玉シーン。主要評価対象 |
| **edge_case** | giant_bubble, irregular_bubble | 人間サイズ・不定形。ロバスト性テストとして参照するが主目標ではない |
| **out_of_scope** | supermacro | 泡膜の断面マクロ写真。浮遊するシャボン玉ではない。検出指標として参照しない |

この分類により、Phase 1 EXP-05（param2=50 + NMS=0.5）の実力は **primary 5 枚中 2 枚が ≤3×** と再評価される。
残る 3 枚（algerian_grassland 29×, closeup 8×, grapevine 164×）はいずれも複雑背景由来の誤検出であり、
検出器の種類ではなく**背景分離**が次の課題である。

## 2026-05-21 Detector Smoke Test

The first broad run of `src/shabondama_study/detect.py` used every local JPEG in
`data/images/bubble-detection/` and wrote overlays to
`data/outputs/bubble-detection-overlays/`.

The accepted validation images produced very high raw candidate counts compared
with a rough visual target count. Visual count means each visually separable
soap bubble, or closed macro bubble cell, is counted once; a giant connected
film is counted as one object.

| Image | Rough visual count | Detector candidates |
| --- | ---: | ---: |
| `soap_bubbles_supermacro_pd.jpg` | about 75 | 1969 |
| `master_of_soapbubbles_cc0.jpg` | about 145 | 13699 |
| `irregular_bubble_cc0.jpg` | 1 | 781 |
| `soap_bubble_closeup_cc_by_2_0.jpg` | 1 | 631 |
| `soap_bubbles_algerian_grassland_cc_by_sa_4_0.jpg` | about 3 | 5280 |
| `giant_bubble_cc_by_sa_3_0.jpg` | 1 | 5509 |
| `soap_bubble_grapevine_cc_by_sa_3_0.jpg` | 1 | 3941 |
| `girl_with_soap_bubble_machine_cc_by_2_0.jpg` | about 45 | 881 |

Reusable lesson: raw HoughCircles output is too permissive for these assets.
Use this run as a false-positive baseline, not as evidence of detector quality.
The next useful step is to run on the standardized long-edge-1600 inputs and add
candidate ranking, overlap suppression, or stronger foreground masking before
trying to interpret counts as detections.
