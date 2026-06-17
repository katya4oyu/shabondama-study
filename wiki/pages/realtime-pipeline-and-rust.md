---
title: リアルタイム検出パイプラインと Rust 化
created_at: 2026-05-22
updated_at: 2026-05-23
status: active
kind: design
---

# リアルタイム検出パイプラインと Rust 化

Phase 1〜2 の実験でスモーク入りシャボン玉が主な対象となることが確定した。
不透明な白球体への絞り込みにより検出難易度が大幅に下がり、
リアルタイム追跡が現実的な目標となった。

## 推奨パイプライン（スモーク泡対象）

```
IR カメラ（Azure Kinect 等）
    ↓
MOG2 背景差分（静止した草・葉を背景モデルとして学習）
    ↓
SimpleBlobDetector または 輝度閾値 + findContours + 真円度フィルタ
    ↓
NMS（重複円除去）
    ↓
SORT トラッカー（Kalman filter + Hungarian matching）
    ↓
ID 付き円リスト { id, x, y, r, vx, vy }
```

スモーク泡は IR 輝度画像で**明るい白球体**として現れるため、
透明泡で問題だった背景分離が自明になる。

## EXP-11: RGB 動画での初期トラッキング検証

2026-05-23 に、ユーザー提供の Downloads 配下 mp4 3 本をテスト素材として
`experiments/exp_11_video_tracking.py` を追加した。処理は軽量な
MOG2 背景差分 → 輪郭フィルタ → 最近傍トラック割当で、SORT 実装前の
ベースラインとして使う。

実行コマンド:

```sh
uv run --locked python experiments/exp_11_video_tracking.py \
  /Users/yykt/Downloads/62455-504643668_medium.mp4 \
  /Users/yykt/Downloads/9695192-hd_1080_1920_25fps.mp4 \
  /Users/yykt/Downloads/326932_medium.mp4 \
```

出力:

- `data/outputs/exp-11-video-tracking/summary.json`
- `data/outputs/exp-11-video-tracking/*_tracked.mp4`

初回結果（long edge 960, フル尺）:

| video | source | mean ms/frame | mean detections/frame | max active tracks |
|---|---:|---:|---:|---:|
| `62455-504643668_medium.mp4` | 1280x720 29.97fps | 11.7 | 42.48 | 129 |
| `9695192-hd_1080_1920_25fps.mp4` | 1080x1920 25fps | 7.5 | 7.34 | 54 |
| `326932_medium.mp4` | 2580x1440 30fps | 17.0 | 13.92 | 60 |

速度は Python + OpenCV でも 30fps 目標に収まるが、`62455` は候補数と
トラック数が多すぎる。背景差分が泡以外の動きや細かなハイライトも拾っている
可能性が高いため、次は注釈動画を目視し、`min_area` / `min_circularity` /
`var_threshold` と ROI を素材別に詰める。

### 背景差分なしの bright モード

スモーク入り泡では背景差分よりも、白く明るい円を直接検出する方が自然な場合がある。
背景差分は「動いたもの」を拾うため、泡が割れた後の煙、カメラ揺れ、背景の反射や
髪・葉の動きも候補になりうる。そこで `--detector bright` を追加し、
HSV の低彩度・高輝度マスク（default: `min_value=180`, `max_saturation=80`）を
同じ輪郭フィルタとトラッカーに流す比較を作った。

```sh
uv run --locked python experiments/exp_11_video_tracking.py \
  /Users/yykt/Downloads/62455-504643668_medium.mp4 \
  /Users/yykt/Downloads/9695192-hd_1080_1920_25fps.mp4 \
  /Users/yykt/Downloads/326932_medium.mp4 \
  --detector bright \
  --output-dir data/outputs/exp-11-video-tracking-bright
```

出力:

- `data/outputs/exp-11-video-tracking-bright/summary.json`
- `data/outputs/exp-11-video-tracking-bright/*_bright_tracked.mp4`
- `data/outputs/exp-11-video-tracking-bright/mask-samples/*.jpg`

| video | mean ms/frame | mean detections/frame | max active tracks |
|---|---:|---:|---:|
| `62455-504643668_medium.mp4` | 7.5 | 44.12 | 94 |
| `9695192-hd_1080_1920_25fps.mp4` | 4.1 | 2.10 | 11 |
| `326932_medium.mp4` | 14.2 | 18.67 | 37 |

初期比較では、`9695192` は bright が明確に良い。`62455` は候補数がほぼ同じで、
背景や白い領域が多い可能性がある。`326932` は候補数は増えたがトラック数は減ったため、
注釈動画とマスクサンプルの目視で、煙・背景白・実泡のどれを拾っているか切り分ける。

### 大きなぼけた白球の失敗原因

`9695192` の 7 秒付近にある大きく明瞭な白球は、bright contour モードでは
安定して拾えなかった。原因は、白球全体が二値化後に一つのきれいな塊にならず、
明るい縁・煙・床側の白領域へ分かれるため。contour モードは「白い塊の外接円」を
見るだけなので、ぼけた球の輪郭円そのものを探せない。

このケースでは HoughCircles が合う。`--detector hough` を追加し、
該当フレームでは中心およそ `(212, 351)`, 半径 `70` の円として大玉を検出できた。
`9695192` フル尺では mean 1.87 detections/frame, max 8 active tracks, 6.8ms/frame。

当面の方針:

- スモーク泡の主検出は `hough` または `bright + hough` の併用を優先する。
- `bright contour` は小さな白塊・煙・床反射に引っ張られやすいため単独主線にしない。
- 背景差分は、検出対象を決める処理ではなく、追跡後の補助特徴として扱う。

### 煙の丸い濃淡を Hough が拾う問題

`9695192` の 9 秒付近では、Hough が煙や床側の白い塊に大きな円を当てる誤検知が出た。
候補の輝度統計を見ると、本物の白球は円内平均輝度 `182.9`、高輝度画素率 `0.77`。
一方、煙由来の大円は平均 `136〜143`、高輝度画素率 `0.04〜0.16` 程度だった。

対策として Hough 候補後に以下を追加した:

- `--min-inner-mean-value`: 円内側 65% の平均輝度を要求する。
- `--min-bright-fraction`: 円内の高輝度画素率を要求する。
- `--nms-threshold`: 同じ玉に複数円が乗る候補を大きい円優先で統合する。

試行コマンド:

```sh
uv run --locked python experiments/exp_11_video_tracking.py \
  /Users/yykt/Downloads/9695192-hd_1080_1920_25fps.mp4 \
  --detector hough \
  --min-inner-mean-value 165 \
  --min-bright-fraction 0.25 \
  --output-dir data/outputs/exp-11-video-tracking-hough-filtered-nms
```

結果は mean 0.29 detections/frame, max 2 active tracks, 7.0ms/frame。煙誤検知は
かなり落ちるが、暗い/半透明な玉を落とす可能性があるため、素材別に
`min-inner-mean-value` と `min-bright-fraction` を調整する。

ただし frame 451 付近の灰色っぽい玉はこの絶対輝度フィルタで漏れた。
煙と暗めの玉を分けるには、絶対輝度より局所特徴が有効だった。

- `--min-local-contrast`: 円の内側が外側リングより明るいことを要求する。
- `--min-highlight-value`: 円内 99 パーセンタイル輝度を要求し、玉の縁ハイライトを使う。

試行コマンド:

```sh
uv run --locked python experiments/exp_11_video_tracking.py \
  /Users/yykt/Downloads/9695192-hd_1080_1920_25fps.mp4 \
  --detector hough \
  --hough-param2 16 \
  --min-mean-value 70 \
  --min-local-contrast 25 \
  --min-highlight-value 195 \
  --nms-threshold 0.85 \
  --output-dir data/outputs/exp-11-video-tracking-hough-contrast-highlight
```

この設定では frame 231 の煙寄り候補は 1 件まで減り、frame 451 の玉は 4 件拾えた。
フル尺は mean 1.11 detections/frame, max 4 active tracks, 9.7ms/frame。

### iPhone 実写素材 `20260523_tabaco_iphone`

2026-05-23 に `data/inputs/20260523_tabaco_iphone` の iPhone 撮影素材
（`IMG_5794.HEIC`, `IMG_5795.MOV`, `IMG_5796.MOV`, `IMG_5797.MOV`）を処理した。
HEIC は参照用に JPEG へ変換し、MOV 3 本は EXP-11 の `bright` モードで追跡した。

出力:

- `data/outputs/20260523-tabaco-iphone-bright-tracking/report.md`
- `data/outputs/20260523-tabaco-iphone-bright-tracking/summary.json`
- `data/outputs/20260523-tabaco-iphone-bright-tracking/*_bright_tracked.mp4`
- `data/outputs/20260523-tabaco-iphone-bright-tracking/contact_sheet.jpg`

プレビュー比較では、`motion` は手・カメラ・背景の動きも拾って約 26〜28 detections/frame、
`hough` は今回の素材では遅く誤候補も多く約 19〜45 detections/frame だった。
`bright` は約 5〜11 detections/frame まで候補を絞れたため、本実行に使った。

本実行コマンド:

```sh
mise exec -- uv run --locked python experiments/exp_11_video_tracking.py \
  data/inputs/20260523_tabaco_iphone/IMG_5795.MOV \
  data/inputs/20260523_tabaco_iphone/IMG_5796.MOV \
  data/inputs/20260523_tabaco_iphone/IMG_5797.MOV \
  --detector bright \
  --long-edge 960 \
  --min-area 120 \
  --max-area 16000 \
  --min-circularity 0.25 \
  --min-value 145 \
  --max-saturation 135 \
  --max-match-distance 60 \
  --max-missed 10 \
  --min-hits 4 \
  --output-dir data/outputs/20260523-tabaco-iphone-bright-tracking
```

| video | frames | mean ms/frame | mean detections/frame | max active tracks | confirmed tracks at end |
|---|---:|---:|---:|---:|---:|
| `IMG_5795.MOV` | 340 | 15.6 | 9.14 | 33 | 4 |
| `IMG_5796.MOV` | 208 | 17.6 | 5.90 | 23 | 9 |
| `IMG_5797.MOV` | 49 | 31.5 | 10.43 | 25 | 13 |

今回の素材では `bright` が定性的な追跡確認には十分だった。ただし、数値は真の泡数ではない。
明るい煙片、反射、白い背景領域、結合した煙塊も contour の外接円として検出される。
次に精度を詰めるなら、ROI 制限または `bright` 候補に対する円形/輪郭エッジ検証を追加する。

### EXP-11 hybrid 試作: bright/blob + ROI Hough + score NMS

2026-05-24 に `exp_11_video_tracking.py` へ `--detector hybrid` を追加した。
狙いは、既存 wiki の知見を単体検出器比較ではなくパイプラインに統合すること。

処理:

1. 低彩度・高輝度の `bright_mask` を作る。
2. bright mask の contour から blob 候補を作る。
3. bright mask の padded ROI 内だけで HoughCircles を実行する。
4. 各候補に `bright_overlap` / `local_contrast` / `highlight_percentile` /
   `bright_fraction` / `motion_support` から score を付ける。
5. 半径優先ではなく score 優先 NMS をかける。
6. 既存の centroid tracker に流す。

追加テスト:

```sh
mise exec -- uv run --locked python tests/test_exp_11_video_tracking.py
```

比較出力:

- `data/outputs/20260523-tabaco-iphone-hybrid-comparison-report.md`
- `data/outputs/20260523-tabaco-iphone-bright-strict-preview/`
- `data/outputs/20260523-tabaco-iphone-hybrid-strict-preview/`

同一条件（`--frame-stride 3 --max-frames 120 --long-edge 720`）での比較:

| detector | `IMG_5795` mean det / ms | `IMG_5796` mean det / ms | `IMG_5797` mean det / ms |
|---|---:|---:|---:|
| strict bright | 7.46 / 55.5 | 2.41 / 118.6 | 4.35 / 84.0 |
| strict hybrid | 11.21 / 251.7 | 2.63 / 241.4 | 4.82 / 183.0 |

結論: hybrid の統合点はできたが、この初期版をデフォルトにする根拠はない。
今回の iPhone 屋外素材では、毎フレーム Hough 補助を入れると速度が 2〜4 倍悪化し、
`IMG_5795` では候補数も増える。次は Hough を毎フレームの主経路にせず、
bright/blob track が弱い・新規出現・missed 後の再捕捉などに限定する
「rescue pass」として使うべき。

## 速度見積もり

Apple Silicon Mac 上での目安：

| ステップ | Python + OpenCV | Rust + opencv-rs |
|---------|:-----------:|:-------------:|
| MOG2 背景差分 | ~5 ms | ~3 ms |
| SimpleBlobDetector | ~10 ms | ~5 ms |
| NMS | ~0.1 ms | ~0.05 ms |
| SORT トラッカー | ~1 ms | ~0.2 ms |
| **合計** | **~15 ms** | **~8 ms** |

30 fps（33 ms/frame）は両方余裕。Rust は非 OpenCV 部分のアロケーション・ディスパッチオーバーヘッドがほぼゼロになるため約 2× の改善が見込める。

## Azure Kinect の IR 輝度画像

深度計測（ToF）ではなく **IR 強度画像（IR intensity frame）** を使う。
透明泡は ToF で失敗するが、スモーク泡は不透明なため ToF 深度も使える。

- IR 強度: 球面の鏡面反射 + スモーク内部散乱 → 明るい白円
- ToF 深度（スモーク泡のみ）: 3D 位置 (x, y, z) まで取得可能

## SORT トラッカー設計

SORT (Simple Online and Realtime Tracking) は約 200 行の軽量実装。

**状態ベクトル:** `[x, y, r, vx, vy, vr]`（位置・半径・各速度）

**フロー:**
1. Kalman filter で次フレームの位置を予測
2. 検出円と予測位置の IoU 行列を計算
3. Hungarian matching で検出 ↔ トラック割り当て
4. 未マッチ検出 → 新トラック生成
5. `max_age` フレーム未マッチのトラック → 削除

シャボン玉は移動が比較的遅い（〜2 m/s）ため、単純な centroid 追跡でも十分な場面は多い。

## Rust 実装

### 依存クレート

```toml
[dependencies]
opencv = { version = "0.94", features = ["videoio", "imgproc", "video", "features2d"] }
nalgebra = "0.33"   # Kalman filter の行列演算
lapjv = "0.1"       # Hungarian algorithm（SORT のマッチング）
```

### Python → Rust の対応表

| Python (cv2) | Rust (opencv crate) |
|---|---|
| `cv2.createBackgroundSubtractorMOG2` | `video::create_background_subtractor_mog2` |
| `cv2.SimpleBlobDetector_create` | `features2d::SimpleBlobDetector::create` |
| `cv2.HoughCircles` | `imgproc::hough_circles` |
| `cv2.findContours` | `imgproc::find_contours` |
| `cv2.VideoCapture` | `videoio::VideoCapture` |

### Azure Kinect IR 取得（Rust）

公式の `libk4a`（C API）を FFI 経由で呼ぶのが最も確実。
非公式の `k4a` crate も存在するが成熟度は低い。

```rust
// sys クレートを自作して libk4a を呼ぶパターン
extern "C" {
    fn k4a_device_open(index: u32, device_handle: *mut k4a_device_t) -> k4a_result_t;
    fn k4a_capture_get_ir_image(capture_handle: k4a_capture_t) -> k4a_image_t;
}
```

### ディレクトリ構成（将来）

```
shabondama-study/
    experiments/       ← Python 実験スクリプト（現状維持）
    src/               ← Python パッケージ（現状維持）
    detector/          ← Rust クレート（将来）
        src/
            main.rs
            pipeline.rs    # MOG2 → Blob → NMS
            tracker.rs     # SORT 実装
            k4a_sys/       # libk4a FFI バインディング
```

## 移行戦略

**Python でアルゴリズムを確定してから Rust に移植する。**

最初から Rust で書くと試行錯誤のコスト（コンパイル時間・型エラー）が高い。
実験環境（Python + OpenCV）でパラメータが安定したら Rust に移す。

段階移行として、Rust クレートを C ABI でビルドして Python から `ctypes` で呼び出す方法もある（`#[no_mangle] pub extern "C" fn detect(...)`）。
