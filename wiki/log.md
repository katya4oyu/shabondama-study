# Wiki Log

## [2026-05-21] init

- Created the initial LLM Wiki skeleton.

## [2026-05-21] maintenance

- Added experiment knowledge workflow guidance.
- Added the no-orphan-page rule to wiki and agent instructions.
- Linked the new workflow page from the wiki index.

## [2026-05-21] ingest

- Added [Project purpose](./pages/project-purpose.md) for repository scope,
  lightweight-method bias, and non-goals.
- Added [Toolchain and task workflow](./pages/toolchain-and-task-workflow.md)
  for `uv`, `mise`, and repeatable experiment commands.
- Updated the experiment workflow, wiki index, and project knowledge map so the
  new pages are reachable and usable.

## [2026-05-21] maintenance

- Recorded the shared-code bias: keep common code at utility level only, avoid
  framework extraction and cross-script compatibility work for experimental
  algorithms.

## [2026-05-21] maintenance

- Clarified `uv --exclude-newer` policy: use it when resolving dependencies, not
  for normal locked runs.
- Switched routine `mise` tasks and README commands to `uv --locked`.

## [2026-05-21] maintenance

- Checked official uv documentation for locking, syncing, resolution, and CLI
  flags.
- Moved the dependency-resolution cutoff into `[tool.uv] exclude-newer` so
  `uv add` and `uv lock` use the project policy by default.
- Added official uv reference links to the toolchain workflow page.

## [2026-05-21] maintenance

- Added [Evidence-based agent workflow](./pages/evidence-based-agent-workflow.md)
  to capture the operating principle behind the uv correction: verify tool
  behavior with current evidence and preserve the lesson, not just the patch.
- Linked the workflow from the wiki index, project knowledge map, toolchain page,
  and agent instructions.

## [2026-05-21] ingest

- Added a licensed Wikimedia Commons still-image set under
  `data/images/bubble-detection/` for bubble-detection validation.
- Recorded source URLs, licenses, dimensions, and condition tags in
  `data/images/bubble-detection/manifest.json` and summarized the set in
  [Bubble detection test assets](./pages/bubble-detection-test-assets.md).
- Revised the asset intake rule after visual review: downloaded images must be
  opened before acceptance, condition tags must match actual pixels, and
  unsuitable human-subject fixtures are rejected from the accepted set.
- Added a format/resolution design for bubble-detection assets: keep ignored
  source originals separate from generated standardized detector inputs, use
  PNG/RGB with EXIF orientation applied, and cap the standard tier at long edge
  1600 px without upscaling.

## [2026-05-21] ingest

- Ran the current `detect.py` HoughCircles detector against local
  `data/images/bubble-detection/*.jpg` validation images.
- Wrote raw detection logs, overlay images, and a contact sheet under
  `data/outputs/bubble-detection-overlays/`.
- Added `data/outputs/bubble-detection-report.md` and updated
  [Bubble detection test assets](./pages/bubble-detection-test-assets.md) with
  the false-positive baseline and next experiment direction.

## [2026-05-21] experiment — Phase 1 HoughCircles チューニング

- 実験スクリプト EXP-00〜05 を `experiments/` に作成。
- EXP-00: standardized PNG でのベースライン計測（EXP-00 counts.json）。
- EXP-01（param2 スイープ）、EXP-02（maxRadius 制限）、EXP-03（NMS）、EXP-04（色マスク）を並行実施。
- **有効:** param2=50（closeup 600→22）、NMS threshold=0.5（supermacro 1969→146）。
- **無効:** maxRadius 制限（誤候補は小半径が主体）、HSV 色マスク（一部で悪化）。
- EXP-05: param2=50 + NMS 0.5 の組み合わせ → 8 枚中 3 枚が ≤3×（girl 1.2×, supermacro 1.3×, master 2.0×）。
- Phase 2 Gate（5/8 ≤3×）未達。代替検出器（EXP-06〜08）へ進む。
- 知見を [HoughCircles チューニング Phase 1](./pages/hough-tuning-phase-1.md) に記録。

## [2026-05-21] scope — 検出対象の定義を明確化

- `supermacro` をスコープ外に分類: 泡膜断面のマクロ写真であり、浮遊するシャボン玉ではない。
- `giant_bubble`・`irregular_bubble` をエッジケースに分類: ストレステストとして参照するが主目標ではない。
- 残り 5 枚（master, closeup, algerian_grassland, grapevine, girl_with_machine）を primary に分類。
- `manifest.json` に `detection_scope` / `detection_scope_reason` フィールドを追加。
- [Bubble detection test assets](./pages/bubble-detection-test-assets.md) にスコープ分類セクションを追記。
- 再評価: EXP-05 は primary 5 枚中 2 枚が ≤3×。残る 3 枚の失敗原因は背景分離であり、検出器の種類ではない。

## [2026-05-22] design — リアルタイムパイプラインと Rust 化

- スモーク入りシャボン玉を主対象として確定したことでリアルタイム検出が現実的な目標になった。
- 推奨パイプライン（MOG2 → SimpleBlobDetector → NMS → SORT）の速度見積もりを整理: Python ~15ms, Rust ~8ms。
- Rust 移行計画を記録: opencv-rust + nalgebra + lapjv、Azure Kinect の libk4a FFI、段階移行方針。
- スモーク泡テストアセットの取得方針を追記: 自撮り / YouTube CC 動画フレーム抽出（yt-dlp + ffmpeg）/ Flickr CC 検索。
- [リアルタイム検出パイプラインと Rust 化](./pages/realtime-pipeline-and-rust.md) を新規作成。
- [Bubble detection test assets](./pages/bubble-detection-test-assets.md) にスモーク泡取得セクションを追加。

## [2026-05-21] experiment — EXP-10 虹色マスク

- EXP-10（薄膜干渉マスク）を実施。hue_gradient / pastel / and / or の 4 モードをスイープ。
- **and モード（hue_grad ∩ pastel）が最良**: master 1.0×（完璧）、girl 1.1×、algerian 5.3×（29× から 82% 削減）。
- grapevine は 164× → 26× に改善するも依然高い。つる・葉の輪郭が hue_grad を通過するため。
- supermacro は 0% マスクで検出不可（スコープ外なので無影響）。
- メモリ 563MB。速度は master 等大画像で最大 6.7 秒（numpy diff コスト）。
- [代替検出器・前景分離 Phase 2](./pages/alternative-detectors-phase-2.md) に EXP-10 結果を追記。

## [2026-05-21] experiment — Phase 2 代替検出器・前景分離

- EXP-06（SimpleBlobDetector）、EXP-07（LoG）、EXP-08（DoH）を並行実施。EXP-09（Depth Anything V2 Small）を追加実施。
- **EXP-06**: 10〜43ms・91MB。algerian_grassland 2.7× など孤立泡は改善。密集泡は検出漏れ。HoughCircles と得意不得意が相補的。
- **EXP-07 LoG**: 棄却。最大 21 秒・793MB、精度も HoughCircles 以下。
- **EXP-08 DoH**: 棄却。SimpleBlobDetector より遅く重く、優位性なし。
- **EXP-09 Depth Anything**: algerian 29×→25×、grapevine 164×→124× と微改善のみ。メモリ ~1GB。根本原因: 透明な泡に背景の深度が割り当てられるため深度マスクで泡ごと消える。
- **Phase 2 の結論**: 背景分離の困難さは検出器ではなく「透明物体」という対象の性質に由来。静止画の単一フレームでは構造的に限界がある。
- 知見を [代替検出器・前景分離 Phase 2](./pages/alternative-detectors-phase-2.md) に記録。
