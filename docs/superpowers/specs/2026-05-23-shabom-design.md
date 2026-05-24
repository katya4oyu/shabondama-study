# shabom 設計仕様

**Goal:** `shabom` コマンドで起動するRust TUI。UVCカメラ/画面キャプチャからリアルタイムにシャボン玉を検出・トラッキングし、ratatui + ratatui-imageでオーバーレイ付きプレビューと可変パラメータパネルを表示する。

## アーキテクチャ

3スレッドパイプライン:

```
Captureスレッド (UVC/Screen) ──tx_frame──▶ Detectスレッド (CV + Tracker) ──tx_result──▶ Mainスレッド (ratatui)
```

状態共有: `Arc<Mutex<AppState>>`  
フレーム受け渡し: `mpsc::sync_channel(2)`

## Tech Stack

| クレート | バージョン | 用途 |
|---------|-----------|------|
| opencv | 0.98 | 画像処理, HoughCircles, MOG2 |
| ratatui | 0.30 | TUIレイアウト |
| ratatui-image | 11 | Sixel/Kitty/Halfblock プレビュー |
| crossterm | 0.28 | ターミナル制御 |
| screencapturekit | 6 | macOS画面キャプチャ |
| shiguredo_video_device | 2026.1 | UVCカメラ |
| image | 0.25 | Mat→DynamicImage変換 |
| clap | 4 | CLI引数 |
| anyhow | 1 | エラーハンドリング |

## ディレクトリ構造

```
shabom/src/
├── main.rs            # CLIエントリポイント (clap) + ratatuiイベントループ
├── app.rs             # AppState, FocusPanel, スレッド起動, mat_to_dynamic_image
├── params.rs          # DetectorParams, BubbleMode, Environment, SourceKind, SmokeDetector
├── capture/
│   ├── mod.rs         # CaptureSourceトレイト
│   ├── uvc.rs         # opencv VideoCapture実装
│   └── screen.rs      # screencapturekit実装 (callback+condvar)
├── detect/
│   ├── mod.rs         # Detection型, NMS, Detector, DetectResult
│   ├── smoke.rs       # SmokePipeline (bright/hough/motion)
│   └── transparent.rs # TransparentPipeline (虹色マスク+HoughCircles)
├── track/
│   └── mod.rs         # BubbleTrack, Tracker (最近傍マッチング)
└── ui/
    ├── mod.rs         # render() 60/40分割レイアウト + ステータスバー
    ├── preview.rs     # ratatui-image StatefulImage プレビューペイン
    └── controls.rs    # MODE/PARAMS/TRACKS/STATSコントロールパネル
```

## 検出モード

### Smoke (スモーク泡)

| サブモード | アルゴリズム |
|-----------|------------|
| bright | HSV低彩度/高輝度マスク → 輪郭抽出 → NMS |
| hough | HoughCircles + 輝度フィルタ (平均輝度/ローカルコントラスト) |
| motion | MOG2背景差分 → モルフォロジーOpen → 輪郭抽出 |

### Transparent (透明泡)

1. HSV色相チャンネルのSobel勾配で虹色エッジ検出
2. パステルマスク (彩度・輝度範囲) とAND
3. マスク済みグレースケールにHoughCircles適用

## TUIレイアウト

```
┌─────────────────────────────────────────────────────────────────┐
│                              │ ◆ MODE                          │
│   PREVIEW (60%)              │  Bubble: [Smoke*] [Trans ]      │
│   ratatui-image              │  Env:    [In*  ] [Out  ]        │
│   Sixel/Kitty/Halfblock      │  Src:    [UVC* ] [Scrn ]        │
│                              │  Det:    [bright*][hough][motion]│
│   ○ #1                       │ ◆ PARAMS (bright)               │
│   ◎ #2                       │  min_value  180                 │
│                              │  max_sat     80                 │
│                              │  nms_thresh 0.50                │
│                              │  min_area   500                 │
│                              │ ◆ TRACKS                        │
│                              │  #1  x: 320 y: 240 r: 45 age:8  │
│                              │ ◆ STATS                         │
│                              │  Det:3  Tracks:2  Frame:8.7ms   │
├──────────────────────────────┴─────────────────────────────────┤
│ Tab:移動  ↑↓:項目  ←→:値変更  m:モード  e:環境  s:ソース  q:終了│
└─────────────────────────────────────────────────────────────────┘
```

## キーバインド

| キー | 動作 |
|------|------|
| `q` / `Ctrl+c` | 終了 |
| `Tab` | Preview↔Controls フォーカス切替 |
| `↑` / `↓` | Controlsパネル内パラメータ選択 |
| `←` / `→` (または `h` / `l`) | 選択中パラメータの値変更 |
| `m` | BubbleModeトグル (Smoke↔Transparent) |
| `e` | 環境トグル (Indoor↔Outdoor) |
| `s` | ソーストグル (UVC↔Screen) ※スレッド再起動未実装 |
| `d` | Detectorサブモードトグル (bright→hough→motion→bright) |

## DetectorParams プリセット

| mode / env | nms_threshold | hue_grad_threshold |
|-----------|--------------|-------------------|
| Smoke / Indoor | 0.50 | 15 |
| Smoke / Outdoor | 0.85 | 15 |
| Transparent / Indoor | 0.50 | 15 |
| Transparent / Outdoor | 0.50 | 10 |

## トラッカー仕様

- 最近傍マッチング: 予測位置からMAX_DIST=100px以内の検出と関連付け
- カルマンフィルタなし: 速度 (vx, vy) でpredict()
- MAX_MISS=5フレーム不検出でトラック削除

## 既知の制約

- ソース切替 (`s` キー) はスレッドを再起動しないため実際には切り替わらない
- ratatui-image の画像表示は Sixel/Kitty 対応端末 (iTerm2/WezTerm/Kitty) が必要。非対応端末はハーフブロックにフォールバック
- MOG2は起動直後は背景モデル未学習のため最初の数秒は誤検出が多い
- screencapturekit v6のAPIはcallback+condvar方式で実装
