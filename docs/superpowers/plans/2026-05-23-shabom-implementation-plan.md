# shabom — リアルタイムシャボン玉検出TUI 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `shabom` コマンドで起動するRust TUI。UVCカメラ/画面キャプチャからリアルタイムにシャボン玉を検出・トラッキングし、ratatui + ratatui-imageでオーバーレイ付きプレビューと可変パラメータパネルを表示する。

**Architecture:** Captureスレッド(映像取得) → Detectスレッド(opencv-rs CV + tracker) → Mainスレッド(ratatui描画) の3スレッドパイプライン。`Arc<Mutex<AppState>>` で状態共有、mpscチャンネルでフレーム受け渡し。

**Tech Stack:** Rust, opencv-rs 0.94, ratatui 0.29, ratatui-image 6.x, shiguredo-video-device, screencapturekit, crossterm 0.28, tokio 1.x, clap 4.x, image 0.25

---

## 設計仕様（実装開始前に `docs/superpowers/specs/2026-05-23-shabom-design.md` に保存してコミットすること）

### ディレクトリ構造

```
shabondama-study/
└── shabom/
    ├── Cargo.toml
    └── src/
        ├── main.rs            # CLIエントリポイント (clap)
        ├── app.rs             # AppState, イベントループ, スレッド起動
        ├── params.rs          # DetectorParams, BubbleMode, 環境プリセット
        ├── capture/
        │   ├── mod.rs         # CaptureSourceトレイト
        │   ├── uvc.rs         # shiguredo-video-device実装
        │   └── screen.rs      # screencapturekit実装
        ├── detect/
        │   ├── mod.rs         # Detectorトレイト, Detection型, NMS
        │   ├── smoke.rs       # スモーク泡パイプライン (bright/hough/motion)
        │   └── transparent.rs # 透明泡パイプライン (hough+虹色マスク)
        ├── track/
        │   └── mod.rs         # BubbleTrack, 最近傍トラッカー
        └── ui/
            ├── mod.rs         # TUIレイアウト (ratatui)
            ├── preview.rs     # ratatui-imageプレビューペイン
            └── controls.rs    # コントロールパネル, キーバインド
```

### 全体データフロー

```
Captureスレッド                 Detectスレッド               Mainスレッド
─────────────                 ──────────────               ────────────
UVC/Screen取得                 frame受信
  ↓                             ↓
Mat取得 ─── tx_frame ────▶  CV処理 (smoke/transparent)
                               NMS
                               Tracker更新
                               annotated frame描画 ─── tx_result ────▶ AppState更新
                                                                          ratatui再描画
```

### TUIレイアウト

```
┌─── shabom ──────────────────────────────────────────────────────────┐
│ [UVC: FaceTime HD] ▶ [Smoke] ▶ [Indoor] ▶ [bright]    FPS: 28.4    │
├───────────────────────────────────┬─────────────────────────────────┤
│                                   │ ◆ MODE                          │
│                                   │  Bubble: [Smoke] [Trans]        │
│   PREVIEW (ratatui-image)         │  Env:    [In   ] [Out  ]        │
│   Sixel/Kitty プロトコル          │  Src:    [UVC  ] [Scrn ]        │
│                                   │  Det:    [bright][hough][motion] │
│   ○ #1 (x:320 y:240 r:45)        │                                 │
│       ◎ #2 (x:180 y:310 r:32)   │ ◆ PARAMS (bright)               │
│                                   │  min_value  ━━━━━━━━━┥ 180     │
│                                   │  max_sat    ━━━━━━━━━┥  80     │
│                                   │  nms_thresh ━━━━━━━━━┥ 0.85   │
│                                   │  min_area   ━━━━━━━━━┥ 500    │
│                                   │                                 │
│                                   │ ◆ TRACKS                       │
│                                   │  #1  x:320 y:240 r:45  age:8   │
│                                   │  #2  x:180 y:310 r:32  age:3   │
│                                   │                                 │
│                                   │ ◆ STATS                        │
│                                   │  Det:3  Tracks:2  Frame:8.7ms  │
├───────────────────────────────────┴─────────────────────────────────┤
│ Tab:移動  ↑↓:項目選択  ←→:値変更  m:モード  e:環境  s:ソース  q:終了│
└─────────────────────────────────────────────────────────────────────┘
```

### キーバインド

| キー | 動作 |
|------|------|
| `q` / `Ctrl+c` | 終了 |
| `Tab` / `Shift+Tab` | プレビュー↔コントロールパネル切替 |
| `↑↓` | コントロールパネル内の項目選択 |
| `←→` (または `h`/`l`) | 選択中パラメータの値変更 |
| `m` | BubbleModeトグル (Smoke↔Transparent) |
| `e` | 環境トグル (Indoor↔Outdoor) |
| `s` | ソーストグル (UVC↔Screen) |
| `d` | Detectorサブモードトグル (bright→hough→motion→bright) |

---

## セルフレビューで発見した修正点

実装前に以下の点を注意すること：

1. **命名衝突**: `params.rs` の `CaptureSource` enum は `capture::CaptureSource` トレイトと名前が衝突する。`params.rs` 内では `SourceKind { Uvc, Screen }` に名前変更し、全参照箇所でも `SourceKind` を使うこと。

2. **存在しないメソッド**: `Mat::try_into_image()` は opencv-rs には存在しない。Task 12 の main.rs で呼んでいる箇所を `mat_to_dynamic_image(&detect_result.annotated)?` に置き換えること。

3. **`FocusPanel` のインポート**: `ui/controls.rs` で `FocusPanel` を使う箇所に `use crate::app::FocusPanel;` を先頭に追加すること。

4. **`DetectResult.annotated` の型**: `Detector::process()` が返す `DetectResult` の `annotated` フィールドは `opencv::core::Mat` 型。Task 12 でこれを `mat_to_dynamic_image()` に渡してから `picker.new_resize_protocol()` に渡すこと。

---

## 実装タスク

---

### Task 1: Cargoプロジェクトスケルトン

**Files:**
- Create: `shabom/Cargo.toml`
- Create: `shabom/src/main.rs`

- [ ] **Step 1: `shabom/Cargo.toml` を作成**

```toml
[package]
name = "shabom"
version = "0.1.0"
edition = "2021"

[[bin]]
name = "shabom"
path = "src/main.rs"

[dependencies]
anyhow = "1"
clap = { version = "4", features = ["derive"] }
crossterm = "0.28"
image = "0.25"
opencv = { version = "0.94", features = [
    "videoio", "imgproc", "video", "features2d"
] }
ratatui = "0.29"
ratatui-image = { version = "6", features = ["sixel", "kitty-protocol"] }
screencapturekit = "0.3"
shiguredo-video-device = "0.1"
tokio = { version = "1", features = ["rt-multi-thread", "sync", "macros"] }

[dev-dependencies]
approx = "0.5"
```

> **注意**: `shiguredo-video-device` と `screencapturekit` のバージョンは `cargo search` で確認してから固定すること。

- [ ] **Step 2: `shabom/src/main.rs` を作成（clap引数定義）**

```rust
use clap::Parser;

#[derive(Parser, Debug)]
#[command(name = "shabom", about = "Real-time bubble detection TUI")]
pub struct Args {
    /// 初期映像ソース
    #[arg(long, default_value = "uvc")]
    pub source: String,

    /// 初期検出モード
    #[arg(long, default_value = "smoke")]
    pub mode: String,

    /// 初期環境
    #[arg(long, default_value = "indoor")]
    pub env: String,

    /// 初期Detectorサブモード
    #[arg(long, default_value = "bright")]
    pub detector: String,

    /// UVCデバイス番号
    #[arg(long, default_value_t = 0)]
    pub device: u32,

    /// キャプチャFPS上限
    #[arg(long, default_value_t = 30)]
    pub fps: u32,
}

fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    println!("shabom starting: source={} mode={} env={}", args.source, args.mode, args.env);
    Ok(())
}
```

- [ ] **Step 3: ビルド確認**

```bash
cd shabom
cargo build 2>&1 | head -30
```

Expected: 依存クレートのダウンロードとコンパイル。エラーなし（opencvのシステムライブラリが見つからない場合は `brew install opencv` を実行）。

- [ ] **Step 4: コミット**

```bash
git add shabom/
git commit -m "feat(shabom): add Rust project skeleton with clap CLI"
```

---

### Task 2: コア型定義 (`params.rs`)

**Files:**
- Create: `shabom/src/params.rs`
- Modify: `shabom/src/main.rs` (mod追加)

- [ ] **Step 1: テストを書く**

`shabom/src/params.rs` を作成:

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BubbleMode { Smoke, Transparent }

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Environment { Indoor, Outdoor }

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CaptureSource { Uvc, Screen }

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SmokeDetector { Bright, Hough, Motion }

#[derive(Debug, Clone)]
pub struct DetectorParams {
    // Smoke/bright
    pub min_value: i32,
    pub max_saturation: i32,
    // Smoke/hough
    pub hough_param2: i32,
    pub min_mean_value: f64,
    pub min_local_contrast: f64,
    pub min_highlight_value: i32,
    // MOG2
    pub mog2_history: i32,
    pub mog2_var_threshold: f64,
    // 共通
    pub nms_threshold: f32,
    pub min_area: f32,
    pub min_circularity: f32,
    pub min_radius: i32,
    pub max_radius: i32,
    // Transparent
    pub hue_grad_threshold: i32,
    pub pastel_s_min: i32,
    pub pastel_s_max: i32,
    pub pastel_v_min: i32,
    pub transparent_param2: i32,
    pub transparent_nms: f32,
    // サブモード
    pub smoke_detector: SmokeDetector,
}

impl DetectorParams {
    pub fn preset(mode: BubbleMode, env: Environment) -> Self {
        match (mode, env) {
            (BubbleMode::Smoke, Environment::Indoor) => Self {
                min_value: 180,
                max_saturation: 80,
                hough_param2: 30,
                min_mean_value: 70.0,
                min_local_contrast: 25.0,
                min_highlight_value: 195,
                mog2_history: 200,
                mog2_var_threshold: 16.0,
                nms_threshold: 0.5,
                min_area: 500.0,
                min_circularity: 0.7,
                min_radius: 8,
                max_radius: 240,
                hue_grad_threshold: 15,
                pastel_s_min: 20,
                pastel_s_max: 160,
                pastel_v_min: 80,
                transparent_param2: 50,
                transparent_nms: 0.5,
                smoke_detector: SmokeDetector::Bright,
            },
            (BubbleMode::Smoke, Environment::Outdoor) => {
                let mut p = Self::preset(BubbleMode::Smoke, Environment::Indoor);
                p.hough_param2 = 40;
                p.nms_threshold = 0.85;
                p.mog2_history = 100;
                p
            },
            (BubbleMode::Transparent, Environment::Indoor) => {
                let mut p = Self::preset(BubbleMode::Smoke, Environment::Indoor);
                p.transparent_param2 = 50;
                p.transparent_nms = 0.5;
                p.nms_threshold = 0.5;
                p
            },
            (BubbleMode::Transparent, Environment::Outdoor) => {
                let mut p = Self::preset(BubbleMode::Transparent, Environment::Indoor);
                p.hue_grad_threshold = 10;
                p
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn smoke_indoor_preset_has_correct_min_value() {
        let p = DetectorParams::preset(BubbleMode::Smoke, Environment::Indoor);
        assert_eq!(p.min_value, 180);
        assert_eq!(p.max_saturation, 80);
        assert_eq!(p.nms_threshold, 0.5);
    }

    #[test]
    fn smoke_outdoor_has_higher_nms_than_indoor() {
        let indoor = DetectorParams::preset(BubbleMode::Smoke, Environment::Indoor);
        let outdoor = DetectorParams::preset(BubbleMode::Smoke, Environment::Outdoor);
        assert!(outdoor.nms_threshold > indoor.nms_threshold);
    }

    #[test]
    fn transparent_outdoor_has_lower_hue_grad_threshold() {
        let indoor = DetectorParams::preset(BubbleMode::Transparent, Environment::Indoor);
        let outdoor = DetectorParams::preset(BubbleMode::Transparent, Environment::Outdoor);
        assert!(outdoor.hue_grad_threshold < indoor.hue_grad_threshold);
    }
}
```

- [ ] **Step 2: `main.rs` に `mod params;` を追加**

```rust
mod params;

use clap::Parser;
// ... (残りのmain.rsは変更なし)
```

- [ ] **Step 3: テストを実行して全パスを確認**

```bash
cd shabom
cargo test params 2>&1
```

Expected: `3 tests passed`

- [ ] **Step 4: コミット**

```bash
git add shabom/src/params.rs shabom/src/main.rs
git commit -m "feat(shabom): add DetectorParams with mode/env presets"
```

---

### Task 3: NMS ユーティリティ (`detect/mod.rs`)

**Files:**
- Create: `shabom/src/detect/mod.rs`
- Modify: `shabom/src/main.rs` (mod追加)

- [ ] **Step 1: テストを書く**

`shabom/src/detect/mod.rs` を作成:

```rust
pub mod smoke;
pub mod transparent;

/// 検出された円候補
#[derive(Debug, Clone, PartialEq)]
pub struct Detection {
    pub x: f32,
    pub y: f32,
    pub r: f32,
    /// 内部スコア（面積でよい）
    pub score: f32,
}

impl Detection {
    pub fn new(x: f32, y: f32, r: f32) -> Self {
        Self { x, y, r, score: std::f32::consts::PI * r * r }
    }
}

/// 円同士の距離ベースNMS（distが閾値*(r1+r2)未満なら抑制）
pub fn nms(mut circles: Vec<Detection>, threshold: f32) -> Vec<Detection> {
    circles.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap());
    let mut kept: Vec<Detection> = Vec::new();
    'outer: for c in circles {
        for k in &kept {
            let dx = c.x - k.x;
            let dy = c.y - k.y;
            let dist = (dx * dx + dy * dy).sqrt();
            if dist < threshold * (c.r + k.r) {
                continue 'outer;
            }
        }
        kept.push(c);
    }
    kept
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nms_keeps_non_overlapping_circles() {
        let circles = vec![
            Detection::new(100.0, 100.0, 20.0),
            Detection::new(300.0, 300.0, 20.0),
        ];
        let result = nms(circles, 0.5);
        assert_eq!(result.len(), 2);
    }

    #[test]
    fn nms_removes_heavily_overlapping_circle() {
        let circles = vec![
            Detection::new(100.0, 100.0, 30.0),
            Detection::new(105.0, 105.0, 25.0), // ほぼ同じ位置
        ];
        let result = nms(circles, 0.5);
        assert_eq!(result.len(), 1);
    }

    #[test]
    fn nms_keeps_larger_circle_when_overlapping() {
        let circles = vec![
            Detection::new(100.0, 100.0, 15.0),
            Detection::new(102.0, 102.0, 30.0), // 大きい方
        ];
        // score=π*r^2 なので大きい方が先に残る
        let result = nms(circles, 0.5);
        assert_eq!(result.len(), 1);
        assert_eq!(result[0].r, 30.0);
    }

    #[test]
    fn nms_empty_input_returns_empty() {
        let result = nms(vec![], 0.5);
        assert!(result.is_empty());
    }
}
```

- [ ] **Step 2: `main.rs` に `mod detect;` を追加**

```rust
mod detect;
mod params;
```

- [ ] **Step 3: `detect/smoke.rs` と `detect/transparent.rs` のスタブを作成**

`shabom/src/detect/smoke.rs`:
```rust
// smoke pipeline – implemented in Task 7
```

`shabom/src/detect/transparent.rs`:
```rust
// transparent pipeline – implemented in Task 8
```

- [ ] **Step 4: テストを実行**

```bash
cd shabom
cargo test detect 2>&1
```

Expected: `4 tests passed`

- [ ] **Step 5: コミット**

```bash
git add shabom/src/detect/
git commit -m "feat(shabom): add Detection type and NMS utility with tests"
```

---

### Task 4: 最近傍トラッカー (`track/mod.rs`)

**Files:**
- Create: `shabom/src/track/mod.rs`
- Modify: `shabom/src/main.rs` (mod追加)

EXP-11の `NearestNeighborTracker` をRustに移植する。

- [ ] **Step 1: テストを書く**

`shabom/src/track/mod.rs` を作成:

```rust
use crate::detect::Detection;

const MAX_MISS: u32 = 5;
const MAX_DIST: f32 = 100.0;

#[derive(Debug, Clone)]
pub struct BubbleTrack {
    pub id: u32,
    pub x: f32,
    pub y: f32,
    pub r: f32,
    pub vx: f32,
    pub vy: f32,
    pub age: u32,
    pub miss_count: u32,
}

impl BubbleTrack {
    fn new(id: u32, det: &Detection) -> Self {
        Self { id, x: det.x, y: det.y, r: det.r, vx: 0.0, vy: 0.0, age: 1, miss_count: 0 }
    }

    fn update(&mut self, det: &Detection) {
        self.vx = det.x - self.x;
        self.vy = det.y - self.y;
        self.x = det.x;
        self.y = det.y;
        self.r = det.r;
        self.age += 1;
        self.miss_count = 0;
    }

    fn predict(&self) -> (f32, f32) {
        (self.x + self.vx, self.y + self.vy)
    }
}

pub struct Tracker {
    tracks: Vec<BubbleTrack>,
    next_id: u32,
}

impl Tracker {
    pub fn new() -> Self {
        Self { tracks: Vec::new(), next_id: 1 }
    }

    pub fn update(&mut self, detections: &[Detection]) -> Vec<BubbleTrack> {
        let mut matched_det = vec![false; detections.len()];
        let mut matched_track = vec![false; self.tracks.len()];

        // 各トラックに最近傍の検出を割り当て
        for (ti, track) in self.tracks.iter_mut().enumerate() {
            let (px, py) = track.predict();
            let best = detections.iter().enumerate()
                .filter(|(di, _)| !matched_det[*di])
                .min_by(|(_, a), (_, b)| {
                    let da = (a.x - px).hypot(a.y - py);
                    let db = (b.x - px).hypot(b.y - py);
                    da.partial_cmp(&db).unwrap()
                });

            if let Some((di, det)) = best {
                let dist = (det.x - px).hypot(det.y - py);
                if dist < MAX_DIST {
                    track.update(det);
                    matched_det[di] = true;
                    matched_track[ti] = true;
                }
            }
        }

        // マッチしなかったトラックのmiss_countをインクリメント
        for (ti, track) in self.tracks.iter_mut().enumerate() {
            if !matched_track[ti] {
                track.miss_count += 1;
            }
        }

        // miss_count > MAX_MISS のトラックを削除
        self.tracks.retain(|t| t.miss_count <= MAX_MISS);

        // 未マッチの検出を新規トラックとして追加
        for (di, det) in detections.iter().enumerate() {
            if !matched_det[di] {
                let id = self.next_id;
                self.next_id += 1;
                self.tracks.push(BubbleTrack::new(id, det));
            }
        }

        self.tracks.clone()
    }

    pub fn active_tracks(&self) -> &[BubbleTrack] {
        &self.tracks
    }
}

impl Default for Tracker {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn det(x: f32, y: f32, r: f32) -> Detection {
        Detection::new(x, y, r)
    }

    #[test]
    fn new_detection_creates_track_with_id_1() {
        let mut tracker = Tracker::new();
        let tracks = tracker.update(&[det(100.0, 100.0, 20.0)]);
        assert_eq!(tracks.len(), 1);
        assert_eq!(tracks[0].id, 1);
    }

    #[test]
    fn close_detection_continues_existing_track() {
        let mut tracker = Tracker::new();
        tracker.update(&[det(100.0, 100.0, 20.0)]);
        let tracks = tracker.update(&[det(105.0, 105.0, 20.0)]);
        assert_eq!(tracks.len(), 1);
        assert_eq!(tracks[0].id, 1);
        assert_eq!(tracks[0].age, 2);
    }

    #[test]
    fn far_detection_creates_new_track() {
        let mut tracker = Tracker::new();
        tracker.update(&[det(100.0, 100.0, 20.0)]);
        let tracks = tracker.update(&[det(500.0, 500.0, 20.0)]);
        assert_eq!(tracks.len(), 2);
    }

    #[test]
    fn track_removed_after_max_miss_frames() {
        let mut tracker = Tracker::new();
        tracker.update(&[det(100.0, 100.0, 20.0)]);
        for _ in 0..=MAX_MISS {
            tracker.update(&[]);
        }
        assert!(tracker.active_tracks().is_empty());
    }

    #[test]
    fn two_detections_get_different_ids() {
        let mut tracker = Tracker::new();
        let tracks = tracker.update(&[det(100.0, 100.0, 20.0), det(300.0, 300.0, 20.0)]);
        assert_eq!(tracks.len(), 2);
        assert_ne!(tracks[0].id, tracks[1].id);
    }
}
```

- [ ] **Step 2: `main.rs` に `mod track;` を追加**

```rust
mod detect;
mod params;
mod track;
```

- [ ] **Step 3: テストを実行**

```bash
cd shabom
cargo test track 2>&1
```

Expected: `5 tests passed`

- [ ] **Step 4: コミット**

```bash
git add shabom/src/track/
git commit -m "feat(shabom): add nearest-neighbor bubble tracker with tests"
```

---

### Task 5: Captureトレイト + UVC実装 (`capture/`)

**Files:**
- Create: `shabom/src/capture/mod.rs`
- Create: `shabom/src/capture/uvc.rs`
- Modify: `shabom/src/main.rs` (mod追加)

- [ ] **Step 1: CaptureSourceトレイトを定義する**

`shabom/src/capture/mod.rs`:

```rust
pub mod screen;
pub mod uvc;

use opencv::core::Mat;

/// フレーム取得の抽象化トレイト
pub trait CaptureSource: Send {
    /// 次のフレームを取得する（ブロッキング）
    fn next_frame(&mut self) -> anyhow::Result<Mat>;
    /// デバイス名を返す（UI表示用）
    fn name(&self) -> &str;
}
```

- [ ] **Step 2: UVC実装を作成する**

`shabom/src/capture/uvc.rs`:

```rust
use super::CaptureSource;
use anyhow::Context;
use opencv::{core::Mat, videoio::{self, VideoCapture, CAP_ANY}};

pub struct UvcCapture {
    cap: VideoCapture,
    device_name: String,
}

impl UvcCapture {
    pub fn new(device_index: u32) -> anyhow::Result<Self> {
        let mut cap = VideoCapture::new(device_index as i32, CAP_ANY)
            .context("VideoCapture::new failed")?;
        if !cap.is_opened()? {
            anyhow::bail!("UVC device {} could not be opened", device_index);
        }
        // FPSを30に設定（ベストエフォート）
        let _ = cap.set(videoio::CAP_PROP_FPS, 30.0);
        let name = format!("UVC:{}", device_index);
        Ok(Self { cap, device_name: name })
    }
}

impl CaptureSource for UvcCapture {
    fn next_frame(&mut self) -> anyhow::Result<Mat> {
        let mut frame = Mat::default();
        self.cap.read(&mut frame).context("VideoCapture::read failed")?;
        if frame.empty() {
            anyhow::bail!("empty frame from UVC device");
        }
        Ok(frame)
    }

    fn name(&self) -> &str {
        &self.device_name
    }
}
```

- [ ] **Step 3: `main.rs` に `mod capture;` を追加して動作確認**

```rust
mod capture;
mod detect;
mod params;
mod track;
```

```bash
cd shabom
cargo build 2>&1
```

Expected: コンパイル成功（スタブのscreen.rsが未実装でも可）。

- [ ] **Step 4: `capture/screen.rs` のスタブを作成（Task 6で実装）**

`shabom/src/capture/screen.rs`:

```rust
use super::CaptureSource;
use opencv::core::Mat;

pub struct ScreenCapture {
    name: String,
}

impl ScreenCapture {
    pub fn new() -> anyhow::Result<Self> {
        // TODO: Task 6で実装
        anyhow::bail!("ScreenCapture not yet implemented")
    }
}

impl CaptureSource for ScreenCapture {
    fn next_frame(&mut self) -> anyhow::Result<Mat> {
        anyhow::bail!("ScreenCapture not yet implemented")
    }

    fn name(&self) -> &str {
        &self.name
    }
}
```

- [ ] **Step 5: コミット**

```bash
git add shabom/src/capture/
git commit -m "feat(shabom): add CaptureSource trait and UVC implementation"
```

---

### Task 6: ScreenCapture実装 (`capture/screen.rs`)

**Files:**
- Modify: `shabom/src/capture/screen.rs`

> **注意**: `screencapturekit` クレートのAPIは `cargo doc --open` で確認してから実装すること。以下は典型的なパターン。

- [ ] **Step 1: screencapturekit crateのAPIを確認する**

```bash
cd shabom
cargo doc --open -p screencapturekit 2>&1
```

`SCStream` または `SCScreenshot` を使ってフレームを取得するAPIを確認する。

- [ ] **Step 2: ScreenCaptureを実装する**

`shabom/src/capture/screen.rs` を更新:

```rust
use super::CaptureSource;
use anyhow::Context;
use opencv::core::Mat;
use opencv::imgproc;

pub struct ScreenCapture {
    name: String,
    // screencapturekit crateの実際の型に合わせて変更する
    // 例: stream: screencapturekit::SCStream,
}

impl ScreenCapture {
    pub fn new() -> anyhow::Result<Self> {
        // screencapturekit APIを使って画面キャプチャを初期化
        // クレートのドキュメントに従って実装する
        // 例:
        // let stream = screencapturekit::SCStream::new(...)?;
        Ok(Self { name: "Screen".to_string() })
    }

    /// RGBAバイト列をopencv Matに変換する
    fn rgba_to_bgr_mat(data: &[u8], width: u32, height: u32) -> anyhow::Result<Mat> {
        let rgba = Mat::from_slice_rows_cols(
            data,
            height as i32,
            width as i32 * 4, // RGBA = 4 channels
        )?;
        // RGBA → BGR変換
        let mut bgr = Mat::default();
        imgproc::cvt_color(&rgba, &mut bgr, imgproc::COLOR_RGBA2BGR, 0)?;
        Ok(bgr)
    }
}

impl CaptureSource for ScreenCapture {
    fn next_frame(&mut self) -> anyhow::Result<Mat> {
        // screencapturekit APIで次のフレームを取得し
        // rgba_to_bgr_mat() でMat変換して返す
        anyhow::bail!("ScreenCapture: implement using screencapturekit API")
    }

    fn name(&self) -> &str {
        &self.name
    }
}
```

- [ ] **Step 3: ビルド確認**

```bash
cd shabom
cargo build 2>&1
```

- [ ] **Step 4: コミット**

```bash
git add shabom/src/capture/screen.rs
git commit -m "feat(shabom): add ScreenCapture skeleton via screencapturekit"
```

---

### Task 7: スモーク泡パイプライン (`detect/smoke.rs`)

**Files:**
- Modify: `shabom/src/detect/smoke.rs`

EXP-11の `bright` / `hough` / `motion` モードをRustに移植。

- [ ] **Step 1: `detect/smoke.rs` を実装する**

```rust
use crate::{detect::{Detection, nms}, params::DetectorParams};
use anyhow::Context;
use opencv::{
    core::{self, Mat, Point, Rect, Scalar, Size, Vector},
    imgproc,
    prelude::*,
    video,
};

pub struct SmokePipeline {
    mog2: video::BackgroundSubtractorMOG2,
}

impl SmokePipeline {
    pub fn new(params: &DetectorParams) -> anyhow::Result<Self> {
        let mog2 = video::create_background_subtractor_mog2(
            params.mog2_history,
            params.mog2_var_threshold,
            false,
        )?;
        Ok(Self { mog2 })
    }

    /// bright モード: HSV低彩度/高輝度マスク
    pub fn detect_bright(&self, frame: &Mat, params: &DetectorParams) -> anyhow::Result<Vec<Detection>> {
        let mut hsv = Mat::default();
        imgproc::cvt_color(frame, &mut hsv, imgproc::COLOR_BGR2HSV, 0)?;

        // 低彩度 + 高輝度マスク
        let lower = Scalar::new(0.0, 0.0, params.min_value as f64, 0.0);
        let upper = Scalar::new(180.0, params.max_saturation as f64, 255.0, 0.0);
        let mut mask = Mat::default();
        core::in_range(&hsv, &lower, &upper, &mut mask)?;

        self.contour_to_detections(&mask, params)
    }

    /// hough モード: HoughCircles + 輝度フィルタ
    pub fn detect_hough(&self, frame: &Mat, params: &DetectorParams) -> anyhow::Result<Vec<Detection>> {
        let mut gray = Mat::default();
        imgproc::cvt_color(frame, &mut gray, imgproc::COLOR_BGR2GRAY, 0)?;

        let mut blurred = Mat::default();
        imgproc::gaussian_blur(&gray, &mut blurred, Size::new(9, 9), 2.0, 2.0, core::BORDER_DEFAULT)?;

        let mut circles: Vector<core::Vec3f> = Vector::new();
        imgproc::hough_circles(
            &blurred,
            &mut circles,
            imgproc::HOUGH_GRADIENT,
            1.0,
            (params.min_radius * 2) as f64,
            200.0,
            params.hough_param2 as f64,
            params.min_radius,
            params.max_radius,
        )?;

        let rows = frame.rows();
        let cols = frame.cols();
        let mut detections = Vec::new();

        for c in &circles {
            let (cx, cy, r) = (c[0], c[1], c[2]);

            // 輝度フィルタ: 円内平均輝度, ローカルコントラスト, ハイライト
            let x0 = ((cx - r) as i32).max(0);
            let y0 = ((cy - r) as i32).max(0);
            let x1 = ((cx + r) as i32).min(cols);
            let y1 = ((cy + r) as i32).min(rows);
            if x1 <= x0 || y1 <= y0 { continue; }

            let roi = Mat::roi(frame, Rect::new(x0, y0, x1 - x0, y1 - y0))?;
            let mean_val = core::mean(&roi, &core::no_array())?;
            let mean_v = (mean_val[0] + mean_val[1] + mean_val[2]) / 3.0;

            if mean_v < params.min_mean_value { continue; }

            // 外周リングとの輝度差（ローカルコントラスト）
            let ring_size = (r * 0.3) as i32;
            let rx0 = (x0 - ring_size).max(0);
            let ry0 = (y0 - ring_size).max(0);
            let rx1 = (x1 + ring_size).min(cols);
            let ry1 = (y1 + ring_size).min(rows);
            if rx1 <= rx0 || ry1 <= ry0 { continue; }

            let outer_roi = Mat::roi(frame, Rect::new(rx0, ry0, rx1 - rx0, ry1 - ry0))?;
            let outer_mean = core::mean(&outer_roi, &core::no_array())?;
            let outer_v = (outer_mean[0] + outer_mean[1] + outer_mean[2]) / 3.0;
            if mean_v - outer_v < params.min_local_contrast { continue; }

            detections.push(Detection::new(cx, cy, r));
        }

        let detections = nms(detections, params.nms_threshold);
        Ok(detections)
    }

    /// motion モード: MOG2背景差分
    pub fn detect_motion(&mut self, frame: &Mat, params: &DetectorParams) -> anyhow::Result<Vec<Detection>> {
        let mut fg_mask = Mat::default();
        self.mog2.apply(frame, &mut fg_mask, -1.0)?;

        // モルフォロジー処理でノイズ除去
        let kernel = imgproc::get_structuring_element(
            imgproc::MORPH_ELLIPSE,
            Size::new(5, 5),
            Point::new(-1, -1),
        )?;
        imgproc::morphology_ex(&fg_mask.clone(), &mut fg_mask, imgproc::MORPH_OPEN, &kernel, Point::new(-1, -1), 2, core::BORDER_DEFAULT, Scalar::default())?;

        self.contour_to_detections(&fg_mask, params)
    }

    fn contour_to_detections(&self, mask: &Mat, params: &DetectorParams) -> anyhow::Result<Vec<Detection>> {
        let mut contours: Vector<Vector<Point>> = Vector::new();
        imgproc::find_contours(
            mask,
            &mut contours,
            imgproc::RETR_EXTERNAL,
            imgproc::CHAIN_APPROX_SIMPLE,
            Point::default(),
        )?;

        let mut detections = Vec::new();
        for contour in &contours {
            let area = imgproc::contour_area(&contour, false)?;
            if area < params.min_area as f64 { continue; }

            let perimeter = imgproc::arc_length(&contour, true)?;
            if perimeter == 0.0 { continue; }
            let circularity = (4.0 * std::f64::consts::PI * area) / (perimeter * perimeter);
            if circularity < params.min_circularity as f64 { continue; }

            let moments = imgproc::moments(&contour, false)?;
            if moments.m00 == 0.0 { continue; }
            let cx = (moments.m10 / moments.m00) as f32;
            let cy = (moments.m01 / moments.m00) as f32;
            let r = (area / std::f64::consts::PI).sqrt() as f32;

            detections.push(Detection::new(cx, cy, r));
        }

        Ok(nms(detections, params.nms_threshold))
    }
}
```

- [ ] **Step 2: ビルド確認**

```bash
cd shabom
cargo build 2>&1
```

Expected: コンパイル成功。

- [ ] **Step 3: コミット**

```bash
git add shabom/src/detect/smoke.rs
git commit -m "feat(shabom): implement smoke bubble detection pipeline (bright/hough/motion)"
```

---

### Task 8: 透明泡パイプライン (`detect/transparent.rs`)

**Files:**
- Modify: `shabom/src/detect/transparent.rs`

EXP-10の虹色マスク（AND mode）+ HoughCircles をRustに移植。

- [ ] **Step 1: `detect/transparent.rs` を実装する**

```rust
use crate::{detect::{Detection, nms}, params::DetectorParams};
use opencv::{
    core::{self, Mat, Point, Scalar, Size, Vector},
    imgproc,
    prelude::*,
};

pub struct TransparentPipeline;

impl TransparentPipeline {
    pub fn new() -> Self { Self }

    pub fn detect(&self, frame: &Mat, params: &DetectorParams) -> anyhow::Result<Vec<Detection>> {
        let mut hsv = Mat::default();
        imgproc::cvt_color(frame, &mut hsv, imgproc::COLOR_BGR2HSV, 0)?;

        // hue_grad マスク: 色相チャンネルのSobelで大きな勾配を持つ領域
        let mut channels: Vector<Mat> = Vector::new();
        core::split(&hsv, &mut channels)?;
        let hue = channels.get(0)?;

        let mut hue_f32 = Mat::default();
        hue.convert_to(&mut hue_f32, core::CV_32F, 1.0, 0.0)?;

        let mut sobel_x = Mat::default();
        let mut sobel_y = Mat::default();
        imgproc::sobel(&hue_f32, &mut sobel_x, core::CV_32F, 1, 0, 3, 1.0, 0.0, core::BORDER_DEFAULT)?;
        imgproc::sobel(&hue_f32, &mut sobel_y, core::CV_32F, 0, 1, 3, 1.0, 0.0, core::BORDER_DEFAULT)?;

        let mut grad_mag = Mat::default();
        core::add_weighted(&sobel_x.abs(), 0.5, &sobel_y.abs(), 0.5, 0.0, &mut grad_mag, -1)?;

        let mut hue_grad_mask_f32 = Mat::default();
        core::compare(&grad_mag, &Scalar::from(params.hue_grad_threshold as f64), &mut hue_grad_mask_f32, core::CMP_GT)?;
        let mut hue_grad_mask = Mat::default();
        hue_grad_mask_f32.convert_to(&mut hue_grad_mask, core::CV_8U, 1.0, 0.0)?;

        // 膨張 + クローズで領域を繋ぐ
        let kernel = imgproc::get_structuring_element(imgproc::MORPH_ELLIPSE, Size::new(5, 5), Point::new(-1, -1))?;
        imgproc::dilate(&hue_grad_mask.clone(), &mut hue_grad_mask, &kernel, Point::new(-1, -1), 2, core::BORDER_DEFAULT, Scalar::default())?;
        imgproc::morphology_ex(&hue_grad_mask.clone(), &mut hue_grad_mask, imgproc::MORPH_CLOSE, &kernel, Point::new(-1, -1), 2, core::BORDER_DEFAULT, Scalar::default())?;

        // pastelマスク: S:[pastel_s_min, pastel_s_max] V:[pastel_v_min, 255]
        let lower = Scalar::new(0.0, params.pastel_s_min as f64, params.pastel_v_min as f64, 0.0);
        let upper = Scalar::new(180.0, params.pastel_s_max as f64, 255.0, 0.0);
        let mut pastel_mask = Mat::default();
        core::in_range(&hsv, &lower, &upper, &mut pastel_mask)?;

        // AND モード: 両マスクの積
        let mut combined = Mat::default();
        core::bitwise_and(&hue_grad_mask, &pastel_mask, &mut combined, &core::no_array())?;

        // HoughCircles
        let mut gray = Mat::default();
        imgproc::cvt_color(frame, &mut gray, imgproc::COLOR_BGR2GRAY, 0)?;

        // combinedマスクで絞り込み
        let mut masked_gray = Mat::default();
        core::bitwise_and(&gray, &combined, &mut masked_gray, &core::no_array())?;

        let mut blurred = Mat::default();
        imgproc::gaussian_blur(&masked_gray, &mut blurred, Size::new(9, 9), 2.0, 2.0, core::BORDER_DEFAULT)?;

        let mut circles: Vector<core::Vec3f> = Vector::new();
        imgproc::hough_circles(
            &blurred,
            &mut circles,
            imgproc::HOUGH_GRADIENT,
            1.0,
            (params.min_radius * 2) as f64,
            200.0,
            params.transparent_param2 as f64,
            params.min_radius,
            params.max_radius,
        )?;

        let detections: Vec<Detection> = circles.iter()
            .map(|c| Detection::new(c[0], c[1], c[2]))
            .collect();

        Ok(nms(detections, params.transparent_nms))
    }
}

impl Default for TransparentPipeline {
    fn default() -> Self { Self::new() }
}
```

- [ ] **Step 2: ビルド確認**

```bash
cd shabom
cargo build 2>&1
```

- [ ] **Step 3: コミット**

```bash
git add shabom/src/detect/transparent.rs
git commit -m "feat(shabom): implement transparent bubble detection (iridescence mask + HoughCircles)"
```

---

### Task 9: アノテーション描画 + Detectスレッド統合 (`detect/mod.rs` 拡張)

**Files:**
- Modify: `shabom/src/detect/mod.rs`

検出結果をMatに描画してAnnotated Frameを生成する関数と、モードに応じたディスパッチを追加する。

- [ ] **Step 1: `detect/mod.rs` にAnnotatedFrame・Detectorディスパッチを追加する**

`detect/mod.rs` の末尾に追記:

```rust
use crate::{
    params::{BubbleMode, DetectorParams, SmokeDetector},
    track::BubbleTrack,
};
use opencv::{
    core::{self, Mat, Point, Scalar},
    imgproc,
    prelude::*,
};

pub use smoke::SmokePipeline;
pub use transparent::TransparentPipeline;

pub struct DetectResult {
    pub tracks: Vec<BubbleTrack>,
    pub annotated: Mat,
    pub raw_count: usize,
}

pub struct Detector {
    smoke: SmokePipeline,
    transparent: TransparentPipeline,
    pub tracker: crate::track::Tracker,
}

impl Detector {
    pub fn new(params: &DetectorParams) -> anyhow::Result<Self> {
        Ok(Self {
            smoke: SmokePipeline::new(params)?,
            transparent: TransparentPipeline::new(),
            tracker: crate::track::Tracker::new(),
        })
    }

    pub fn process(&mut self, frame: &Mat, params: &DetectorParams, mode: BubbleMode) -> anyhow::Result<DetectResult> {
        let detections = match mode {
            BubbleMode::Smoke => match params.smoke_detector {
                SmokeDetector::Bright => self.smoke.detect_bright(frame, params)?,
                SmokeDetector::Hough => self.smoke.detect_hough(frame, params)?,
                SmokeDetector::Motion => self.smoke.detect_motion(frame, params)?,
            },
            BubbleMode::Transparent => self.transparent.detect(frame, params)?,
        };

        let raw_count = detections.len();
        let tracks = self.tracker.update(&detections);

        // アノテーション描画
        let mut annotated = frame.clone();
        for track in &tracks {
            let center = Point::new(track.x as i32, track.y as i32);
            let radius = track.r as i32;
            // 円
            imgproc::circle(&mut annotated, center, radius, Scalar::new(0.0, 255.0, 0.0, 0.0), 2, imgproc::LINE_AA, 0)?;
            // ID ラベル
            let label = format!("#{}", track.id);
            imgproc::put_text(
                &mut annotated,
                &label,
                Point::new(center.x - radius, center.y - radius - 5),
                imgproc::FONT_HERSHEY_SIMPLEX,
                0.6,
                Scalar::new(0.0, 255.0, 0.0, 0.0),
                1,
                imgproc::LINE_AA,
                false,
            )?;
        }

        Ok(DetectResult { tracks, annotated, raw_count })
    }
}
```

- [ ] **Step 2: ビルド確認**

```bash
cd shabom
cargo build 2>&1
```

- [ ] **Step 3: コミット**

```bash
git add shabom/src/detect/mod.rs
git commit -m "feat(shabom): add Detector dispatcher and annotated frame rendering"
```

---

### Task 10: AppState + スレッドパイプライン (`app.rs`)

**Files:**
- Create: `shabom/src/app.rs`
- Modify: `shabom/src/main.rs`

- [ ] **Step 1: `app.rs` を実装する**

```rust
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use anyhow::Context;
use image::DynamicImage;
use opencv::prelude::*;

use crate::{
    capture::CaptureSource,
    detect::{DetectResult, Detector},
    params::{BubbleMode, CaptureSource as CaptSrc, DetectorParams, Environment, SmokeDetector},
    track::BubbleTrack,
};

#[derive(Clone, Debug)]
pub struct AppState {
    pub mode: BubbleMode,
    pub env: Environment,
    pub source: CaptSrc,
    pub params: DetectorParams,
    pub tracks: Vec<BubbleTrack>,
    pub latest_frame: Option<DynamicImage>,
    pub fps: f64,
    pub frame_ms: f64,
    pub raw_count: usize,
}

impl AppState {
    pub fn new(mode: BubbleMode, env: Environment, source: CaptSrc) -> Self {
        Self {
            params: DetectorParams::preset(mode, env),
            mode,
            env,
            source,
            tracks: Vec::new(),
            latest_frame: None,
            fps: 0.0,
            frame_ms: 0.0,
            raw_count: 0,
        }
    }

    pub fn apply_preset(&mut self) {
        let current_detector = self.params.smoke_detector;
        self.params = DetectorParams::preset(self.mode, self.env);
        self.params.smoke_detector = current_detector;
    }
}

/// Captureスレッドを起動してフレームをチャンネルに流す
pub fn spawn_capture_thread(
    mut source: Box<dyn CaptureSource>,
    tx: std::sync::mpsc::SyncSender<opencv::core::Mat>,
) {
    std::thread::spawn(move || loop {
        match source.next_frame() {
            Ok(frame) => { let _ = tx.send(frame); }
            Err(e) => eprintln!("[capture] error: {e}"),
        }
    });
}

/// Detectスレッドを起動してDetectResultをチャンネルに流す
pub fn spawn_detect_thread(
    rx_frame: std::sync::mpsc::Receiver<opencv::core::Mat>,
    tx_result: std::sync::mpsc::SyncSender<(DetectResult, Duration)>,
    state: Arc<Mutex<AppState>>,
) {
    std::thread::spawn(move || {
        // 初期paramsでDetectorを構築
        let initial_params = {
            let s = state.lock().unwrap();
            (s.params.clone(), s.mode)
        };
        let mut detector = Detector::new(&initial_params.0).expect("Detector init failed");

        loop {
            let frame = match rx_frame.recv() {
                Ok(f) => f,
                Err(_) => break,
            };

            let (params, mode) = {
                let s = state.lock().unwrap();
                (s.params.clone(), s.mode)
            };

            let t0 = Instant::now();
            match detector.process(&frame, &params, mode) {
                Ok(result) => {
                    let elapsed = t0.elapsed();
                    let _ = tx_result.send((result, elapsed));
                }
                Err(e) => eprintln!("[detect] error: {e}"),
            }
        }
    });
}

/// MatをDynamicImageに変換（BGR→RGB）
pub fn mat_to_dynamic_image(mat: &opencv::core::Mat) -> anyhow::Result<DynamicImage> {
    use opencv::{core::Mat, imgproc, prelude::*};
    let mut rgb = Mat::default();
    imgproc::cvt_color(mat, &mut rgb, imgproc::COLOR_BGR2RGB, 0)?;
    let rows = rgb.rows() as u32;
    let cols = rgb.cols() as u32;
    let data = rgb.data_bytes().context("Mat data_bytes failed")?;
    let buf = image::RgbImage::from_raw(cols, rows, data.to_vec())
        .context("RgbImage::from_raw failed")?;
    Ok(DynamicImage::ImageRgb8(buf))
}
```

- [ ] **Step 2: `main.rs` に `mod app;` を追加し、スレッド起動のスケルトンを書く**

```rust
mod app;
mod capture;
mod detect;
mod params;
mod track;

use clap::Parser;
use params::{BubbleMode, CaptureSource as CaptSrc, Environment};
use std::sync::{Arc, Mutex};

#[derive(Parser, Debug)]
#[command(name = "shabom", about = "Real-time bubble detection TUI")]
pub struct Args {
    #[arg(long, default_value = "uvc")] pub source: String,
    #[arg(long, default_value = "smoke")] pub mode: String,
    #[arg(long, default_value = "indoor")] pub env: String,
    #[arg(long, default_value = "bright")] pub detector: String,
    #[arg(long, default_value_t = 0)] pub device: u32,
    #[arg(long, default_value_t = 30)] pub fps: u32,
}

fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    let mode = match args.mode.as_str() {
        "trans" | "transparent" => BubbleMode::Transparent,
        _ => BubbleMode::Smoke,
    };
    let env = match args.env.as_str() {
        "outdoor" => Environment::Outdoor,
        _ => Environment::Indoor,
    };
    let source = match args.source.as_str() {
        "screen" => CaptSrc::Screen,
        _ => CaptSrc::Uvc,
    };

    let state = Arc::new(Mutex::new(app::AppState::new(mode, env, source)));

    let cap: Box<dyn capture::CaptureSource> = match source {
        CaptSrc::Uvc => Box::new(capture::uvc::UvcCapture::new(args.device)?),
        CaptSrc::Screen => Box::new(capture::screen::ScreenCapture::new()?),
    };

    let (tx_frame, rx_frame) = std::sync::mpsc::sync_channel(2);
    let (tx_result, rx_result) = std::sync::mpsc::sync_channel(2);

    app::spawn_capture_thread(cap, tx_frame);
    app::spawn_detect_thread(rx_frame, tx_result, Arc::clone(&state));

    // Task 11でTUIループに置き換える
    // 暫定: 結果を標準出力に表示
    for (result, elapsed) in rx_result.iter().take(30) {
        println!("tracks={} raw={} elapsed={:.1}ms", result.tracks.len(), result.raw_count, elapsed.as_secs_f64() * 1000.0);
    }

    Ok(())
}
```

- [ ] **Step 3: UVCカメラで動作確認（カメラが接続されている場合）**

```bash
cd shabom
cargo run -- --source uvc 2>&1 | head -30
```

Expected: `tracks=N raw=M elapsed=X.Xms` が30行出力される。

- [ ] **Step 4: コミット**

```bash
git add shabom/src/app.rs shabom/src/main.rs
git commit -m "feat(shabom): add AppState and capture/detect thread pipeline"
```

---

### Task 11: TUIレイアウトスケルトン (`ui/`)

**Files:**
- Create: `shabom/src/ui/mod.rs`
- Create: `shabom/src/ui/preview.rs`
- Create: `shabom/src/ui/controls.rs`
- Modify: `shabom/src/main.rs`

- [ ] **Step 1: `ui/mod.rs` でレイアウトを定義する**

```rust
pub mod controls;
pub mod preview;

use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    Frame,
};
use crate::app::AppState;

pub fn render(frame: &mut Frame, state: &AppState, image_state: &mut ratatui_image::StatefulProtocol) {
    let chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(60), Constraint::Percentage(40)])
        .split(frame.area());

    preview::render_preview(frame, chunks[0], state, image_state);
    controls::render_controls(frame, chunks[1], state);
    render_status_bar(frame, state);
}

fn render_status_bar(frame: &mut Frame, state: &AppState) {
    use ratatui::{layout::*, widgets::*, style::*};
    let area = frame.area();
    let bar = Rect::new(0, area.height.saturating_sub(1), area.width, 1);
    let text = " Tab:移動  ↑↓:項目  ←→:値変更  m:モード  e:環境  s:ソース  q:終了";
    frame.render_widget(Paragraph::new(text).style(Style::default().bg(Color::DarkGray)), bar);
}
```

- [ ] **Step 2: `ui/preview.rs` を実装する**

```rust
use ratatui::{layout::Rect, Frame};
use ratatui_image::StatefulProtocol;
use crate::app::AppState;

pub fn render_preview(
    frame: &mut Frame,
    area: Rect,
    _state: &AppState,
    image_state: &mut StatefulProtocol,
) {
    use ratatui::widgets::Block;
    use ratatui_image::StatefulImage;

    let block = Block::bordered().title(" PREVIEW ");
    let inner = block.inner(area);
    frame.render_widget(block, area);

    if _state.latest_frame.is_some() {
        let image_widget = StatefulImage::new();
        frame.render_stateful_widget(image_widget, inner, image_state);
    }
}
```

- [ ] **Step 3: `ui/controls.rs` を実装する**

```rust
use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, List, ListItem, Paragraph},
    Frame,
};
use crate::{app::AppState, params::{BubbleMode, Environment, CaptureSource, SmokeDetector}};

pub fn render_controls(frame: &mut Frame, area: Rect, state: &AppState) {
    let block = Block::bordered().title(" CONTROL ");
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let sections = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(6),  // MODE
            Constraint::Length(8),  // PARAMS
            Constraint::Min(4),     // TRACKS
            Constraint::Length(4),  // STATS
        ])
        .split(inner);

    render_mode_section(frame, sections[0], state);
    render_params_section(frame, sections[1], state);
    render_tracks_section(frame, sections[2], state);
    render_stats_section(frame, sections[3], state);
}

fn render_mode_section(frame: &mut Frame, area: Rect, state: &AppState) {
    let bubble_str = match state.mode {
        BubbleMode::Smoke => "[Smoke*] [Trans ]",
        BubbleMode::Transparent => "[Smoke ] [Trans*]",
    };
    let env_str = match state.env {
        Environment::Indoor => "[In*  ] [Out  ]",
        Environment::Outdoor => "[In   ] [Out* ]",
    };
    let src_str = match state.source {
        CaptureSource::Uvc => "[UVC* ] [Scrn ]",
        CaptureSource::Screen => "[UVC  ] [Scrn*]",
    };
    let det_str = match state.params.smoke_detector {
        SmokeDetector::Bright => "[bright*][hough][motion]",
        SmokeDetector::Hough => "[bright][hough*][motion]",
        SmokeDetector::Motion => "[bright][hough][motion*]",
    };
    let text = format!(
        "◆ MODE\n Bubble: {}\n Env:    {}\n Src:    {}\n Det:    {}",
        bubble_str, env_str, src_str, det_str
    );
    frame.render_widget(Paragraph::new(text), area);
}

fn render_params_section(frame: &mut Frame, area: Rect, state: &AppState) {
    let p = &state.params;
    let items = match state.mode {
        BubbleMode::Smoke => match p.smoke_detector {
            SmokeDetector::Bright => vec![
                format!("  min_value  {:>4}", p.min_value),
                format!("  max_sat    {:>4}", p.max_saturation),
                format!("  nms_thresh {:>4.2}", p.nms_threshold),
                format!("  min_area   {:>4.0}", p.min_area),
            ],
            SmokeDetector::Hough => vec![
                format!("  param2     {:>4}", p.hough_param2),
                format!("  min_mean   {:>4.0}", p.min_mean_value),
                format!("  contrast   {:>4.0}", p.min_local_contrast),
                format!("  highlight  {:>4}", p.min_highlight_value),
                format!("  nms_thresh {:>4.2}", p.nms_threshold),
            ],
            SmokeDetector::Motion => vec![
                format!("  mog2_hist  {:>4}", p.mog2_history),
                format!("  var_thresh {:>4.0}", p.mog2_var_threshold),
                format!("  min_area   {:>4.0}", p.min_area),
                format!("  nms_thresh {:>4.2}", p.nms_threshold),
            ],
        },
        BubbleMode::Transparent => vec![
            format!("  param2     {:>4}", p.transparent_param2),
            format!("  hue_grad   {:>4}", p.hue_grad_threshold),
            format!("  pastel_s   {:>2}-{:<2}", p.pastel_s_min, p.pastel_s_max),
            format!("  pastel_v   {:>4}", p.pastel_v_min),
            format!("  nms_thresh {:>4.2}", p.transparent_nms),
        ],
    };

    let title = format!("◆ PARAMS ({})", match (state.mode, state.params.smoke_detector) {
        (BubbleMode::Smoke, SmokeDetector::Bright) => "bright",
        (BubbleMode::Smoke, SmokeDetector::Hough) => "hough",
        (BubbleMode::Smoke, SmokeDetector::Motion) => "motion",
        (BubbleMode::Transparent, _) => "transparent",
    });

    let text = std::iter::once(title).chain(items).collect::<Vec<_>>().join("\n");
    frame.render_widget(Paragraph::new(text), area);
}

fn render_tracks_section(frame: &mut Frame, area: Rect, state: &AppState) {
    let mut lines = vec!["◆ TRACKS".to_string()];
    for t in state.tracks.iter().take(5) {
        lines.push(format!("  #{:<3} x:{:>4} y:{:>4} r:{:>3} age:{}", t.id, t.x as i32, t.y as i32, t.r as i32, t.age));
    }
    frame.render_widget(Paragraph::new(lines.join("\n")), area);
}

fn render_stats_section(frame: &mut Frame, area: Rect, state: &AppState) {
    let text = format!(
        "◆ STATS\n  Det:{:<3} Tracks:{:<3}\n  Frame:{:.1}ms  FPS:{:.1}",
        state.raw_count, state.tracks.len(), state.frame_ms, state.fps
    );
    frame.render_widget(Paragraph::new(text), area);
}
```

- [ ] **Step 4: `main.rs` に `mod ui;` を追加**

```rust
mod app;
mod capture;
mod detect;
mod params;
mod track;
mod ui;
```

- [ ] **Step 5: ビルド確認**

```bash
cd shabom
cargo build 2>&1
```

- [ ] **Step 6: コミット**

```bash
git add shabom/src/ui/
git commit -m "feat(shabom): add TUI layout skeleton with ratatui"
```

---

### Task 12: メインループ + ratatui-image プレビュー (`main.rs` 完成版)

**Files:**
- Modify: `shabom/src/main.rs`

- [ ] **Step 1: `main.rs` を完全なratatuiイベントループに置き換える**

```rust
mod app;
mod capture;
mod detect;
mod params;
mod track;
mod ui;

use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use anyhow::Context;
use clap::Parser;
use crossterm::{
    event::{self, Event, KeyCode, KeyModifiers},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{backend::CrosstermBackend, Terminal};
use ratatui_image::{picker::Picker, StatefulProtocol};

use crate::{
    app::{mat_to_dynamic_image, AppState},
    params::{BubbleMode, CaptureSource as CaptSrc, Environment, SmokeDetector},
};

#[derive(Parser, Debug)]
#[command(name = "shabom", about = "Real-time bubble detection TUI")]
pub struct Args {
    #[arg(long, default_value = "uvc")] pub source: String,
    #[arg(long, default_value = "smoke")] pub mode: String,
    #[arg(long, default_value = "indoor")] pub env: String,
    #[arg(long, default_value = "bright")] pub detector: String,
    #[arg(long, default_value_t = 0)] pub device: u32,
    #[arg(long, default_value_t = 30)] pub fps: u32,
}

fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    let mode = match args.mode.as_str() {
        "trans" | "transparent" => BubbleMode::Transparent,
        _ => BubbleMode::Smoke,
    };
    let env_val = match args.env.as_str() {
        "outdoor" => Environment::Outdoor,
        _ => Environment::Indoor,
    };
    let source_val = match args.source.as_str() {
        "screen" => CaptSrc::Screen,
        _ => CaptSrc::Uvc,
    };

    let state = Arc::new(Mutex::new(AppState::new(mode, env_val, source_val)));

    let cap: Box<dyn capture::CaptureSource> = match source_val {
        CaptSrc::Uvc => Box::new(capture::uvc::UvcCapture::new(args.device)?),
        CaptSrc::Screen => Box::new(capture::screen::ScreenCapture::new()?),
    };

    let (tx_frame, rx_frame) = std::sync::mpsc::sync_channel(2);
    let (tx_result, rx_result) = std::sync::mpsc::sync_channel(2);

    app::spawn_capture_thread(cap, tx_frame);
    app::spawn_detect_thread(rx_frame, tx_result, Arc::clone(&state));

    // ratatui 初期化
    enable_raw_mode()?;
    let mut stdout = std::io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    // ratatui-image: プロトコル自動検出（Sixel/Kitty/Halfblock）
    let mut picker = Picker::from_termios().unwrap_or_else(|_| Picker::new((8, 12)));
    picker.guess_protocol();
    let mut image_state: Option<StatefulProtocol> = None;

    let mut fps_counter = 0u32;
    let mut fps_timer = Instant::now();

    let result = 'main: loop {
        // 非ブロッキングでDetectResultを取得
        while let Ok((detect_result, elapsed)) = rx_result.try_recv() {
            let dyn_img = detect_result.annotated.try_into_image()
                .or_else(|_| mat_to_dynamic_image(&detect_result.annotated))?;

            let proto = picker.new_resize_protocol(dyn_img);
            image_state = Some(proto);

            let mut s = state.lock().unwrap();
            s.tracks = detect_result.tracks;
            s.raw_count = detect_result.raw_count;
            s.frame_ms = elapsed.as_secs_f64() * 1000.0;

            fps_counter += 1;
            if fps_timer.elapsed() >= Duration::from_secs(1) {
                s.fps = fps_counter as f64 / fps_timer.elapsed().as_secs_f64();
                fps_counter = 0;
                fps_timer = Instant::now();
            }
        }

        // 描画
        {
            let s = state.lock().unwrap();
            let s_clone = s.clone();
            drop(s);
            if let Some(ref mut img_state) = image_state {
                terminal.draw(|f| ui::render(f, &s_clone, img_state))?;
            } else {
                terminal.draw(|f| {
                    let mut dummy = picker.new_resize_protocol(
                        image::DynamicImage::new_rgb8(1, 1)
                    );
                    ui::render(f, &s_clone, &mut dummy);
                })?;
            }
        }

        // キー入力処理（16msタイムアウト ≈ 60fps UI）
        if event::poll(Duration::from_millis(16))? {
            if let Event::Key(key) = event::read()? {
                let mut s = state.lock().unwrap();
                match key.code {
                    KeyCode::Char('q') => break 'main Ok(()),
                    KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => break 'main Ok(()),
                    KeyCode::Char('m') => {
                        s.mode = match s.mode {
                            BubbleMode::Smoke => BubbleMode::Transparent,
                            BubbleMode::Transparent => BubbleMode::Smoke,
                        };
                        s.apply_preset();
                    }
                    KeyCode::Char('e') => {
                        s.env = match s.env {
                            Environment::Indoor => Environment::Outdoor,
                            Environment::Outdoor => Environment::Indoor,
                        };
                        s.apply_preset();
                    }
                    KeyCode::Char('s') => {
                        s.source = match s.source {
                            CaptSrc::Uvc => CaptSrc::Screen,
                            CaptSrc::Screen => CaptSrc::Uvc,
                        };
                        // TODO: ソース切替はスレッド再起動が必要（Task 13で対応）
                    }
                    KeyCode::Char('d') => {
                        s.params.smoke_detector = match s.params.smoke_detector {
                            SmokeDetector::Bright => SmokeDetector::Hough,
                            SmokeDetector::Hough => SmokeDetector::Motion,
                            SmokeDetector::Motion => SmokeDetector::Bright,
                        };
                    }
                    _ => {}
                }
            }
        }
    };

    // クリーンアップ
    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;

    result
}
```

> **注意**: `ratatui_image` の `StatefulProtocol` / `Picker` APIはバージョンによって変わる。`cargo doc --open -p ratatui-image` で確認してから合わせること。

- [ ] **Step 2: ビルド確認**

```bash
cd shabom
cargo build 2>&1
```

- [ ] **Step 3: UVCカメラで起動して目視確認**

```bash
cd shabom
cargo run -- --source uvc
```

確認項目:
- TUIが起動すること
- プレビューペインに映像が表示されること（または Sixel未対応端末ではブロック表示）
- `m` キーでモードが切り替わること
- `q` で正常終了すること

- [ ] **Step 4: コミット**

```bash
git add shabom/src/main.rs
git commit -m "feat(shabom): implement main ratatui event loop with image preview"
```

---

### Task 13: パラメータ操作キーバインド (`ui/controls.rs` 拡張)

**Files:**
- Modify: `shabom/src/ui/controls.rs`
- Modify: `shabom/src/main.rs`
- Modify: `shabom/src/app.rs`

パラメータ選択と増減の実装。

- [ ] **Step 1: `AppState` にフォーカス管理を追加する**

`app.rs` の `AppState` に追記:

```rust
#[derive(Clone, Debug, PartialEq)]
pub enum FocusPanel { Preview, Controls }

#[derive(Clone, Debug)]
pub struct AppState {
    // ... 既存フィールド ...
    pub focus: FocusPanel,
    pub selected_param: usize,
}

impl AppState {
    pub fn new(mode: BubbleMode, env: Environment, source: CaptSrc) -> Self {
        Self {
            // ... 既存初期化 ...
            focus: FocusPanel::Preview,
            selected_param: 0,
        }
    }

    pub fn param_count(&self) -> usize {
        match self.mode {
            BubbleMode::Smoke => match self.params.smoke_detector {
                SmokeDetector::Bright => 4,
                SmokeDetector::Hough => 5,
                SmokeDetector::Motion => 4,
            },
            BubbleMode::Transparent => 5,
        }
    }

    pub fn adjust_selected_param(&mut self, delta: i32) {
        let p = &mut self.params;
        match self.mode {
            BubbleMode::Smoke => match p.smoke_detector {
                SmokeDetector::Bright => match self.selected_param {
                    0 => p.min_value = (p.min_value + delta).clamp(0, 255),
                    1 => p.max_saturation = (p.max_saturation + delta).clamp(0, 255),
                    2 => p.nms_threshold = (p.nms_threshold + delta as f32 * 0.05).clamp(0.1, 1.0),
                    3 => p.min_area = (p.min_area + delta as f32 * 50.0).max(0.0),
                    _ => {}
                },
                SmokeDetector::Hough => match self.selected_param {
                    0 => p.hough_param2 = (p.hough_param2 + delta).clamp(1, 200),
                    1 => p.min_mean_value = (p.min_mean_value + delta as f64).clamp(0.0, 255.0),
                    2 => p.min_local_contrast = (p.min_local_contrast + delta as f64).clamp(0.0, 100.0),
                    3 => p.min_highlight_value = (p.min_highlight_value + delta).clamp(0, 255),
                    4 => p.nms_threshold = (p.nms_threshold + delta as f32 * 0.05).clamp(0.1, 1.0),
                    _ => {}
                },
                SmokeDetector::Motion => match self.selected_param {
                    0 => p.mog2_history = (p.mog2_history + delta * 10).clamp(10, 1000),
                    1 => p.mog2_var_threshold = (p.mog2_var_threshold + delta as f64).clamp(1.0, 100.0),
                    2 => p.min_area = (p.min_area + delta as f32 * 50.0).max(0.0),
                    3 => p.nms_threshold = (p.nms_threshold + delta as f32 * 0.05).clamp(0.1, 1.0),
                    _ => {}
                },
            },
            BubbleMode::Transparent => match self.selected_param {
                0 => p.transparent_param2 = (p.transparent_param2 + delta).clamp(1, 200),
                1 => p.hue_grad_threshold = (p.hue_grad_threshold + delta).clamp(1, 50),
                2 => p.pastel_s_min = (p.pastel_s_min + delta).clamp(0, p.pastel_s_max - 1),
                3 => p.pastel_v_min = (p.pastel_v_min + delta).clamp(0, 255),
                4 => p.transparent_nms = (p.transparent_nms + delta as f32 * 0.05).clamp(0.1, 1.0),
                _ => {}
            },
        }
    }
}
```

- [ ] **Step 2: `main.rs` のキー処理に `Tab`・`↑↓`・`←→` を追加**

`main.rs` のキーマッチ部分に追加:

```rust
KeyCode::Tab => {
    s.focus = match s.focus {
        FocusPanel::Preview => FocusPanel::Controls,
        FocusPanel::Controls => FocusPanel::Preview,
    };
}
KeyCode::Up if s.focus == FocusPanel::Controls => {
    if s.selected_param > 0 { s.selected_param -= 1; }
}
KeyCode::Down if s.focus == FocusPanel::Controls => {
    let max = s.param_count().saturating_sub(1);
    if s.selected_param < max { s.selected_param += 1; }
}
KeyCode::Left if s.focus == FocusPanel::Controls => {
    s.adjust_selected_param(-1);
}
KeyCode::Right if s.focus == FocusPanel::Controls => {
    s.adjust_selected_param(1);
}
KeyCode::Char('h') if s.focus == FocusPanel::Controls => {
    s.adjust_selected_param(-1);
}
KeyCode::Char('l') if s.focus == FocusPanel::Controls => {
    s.adjust_selected_param(1);
}
```

- [ ] **Step 3: `ui/controls.rs` の `render_params_section` で選択行をハイライト**

`render_params_section` を更新:

```rust
fn render_params_section(frame: &mut Frame, area: Rect, state: &AppState) {
    // ... items生成は既存のまま ...
    
    let items: Vec<ListItem> = items.iter().enumerate()
        .map(|(i, line)| {
            if i == state.selected_param && state.focus == FocusPanel::Controls {
                ListItem::new(line.as_str())
                    .style(Style::default().bg(Color::DarkGray).add_modifier(Modifier::BOLD))
            } else {
                ListItem::new(line.as_str())
            }
        })
        .collect();

    let title = /* ... 既存の title 計算 ... */;
    let list = List::new(items).block(Block::default().title(format!("◆ {}", title)));
    frame.render_widget(list, area);
}
```

`use crate::app::FocusPanel;` を `ui/controls.rs` の先頭に追加。

- [ ] **Step 4: ビルド・動作確認**

```bash
cd shabom
cargo build && cargo run -- --source uvc
```

確認: `Tab` でフォーカス切替、`↑↓` で項目移動、`←→` でパラメータ値変更、変更が次フレームの検出に反映される。

- [ ] **Step 5: コミット**

```bash
git add shabom/src/
git commit -m "feat(shabom): add parameter selection and live adjustment keybindings"
```

---

### Task 14: エンドツーエンド検証 + 設計ドキュメント保存

**Files:**
- Create: `docs/superpowers/specs/2026-05-23-shabom-design.md`
- Create: `docs/superpowers/plans/2026-05-23-shabom-implementation-plan.md`

- [ ] **Step 1: スモーク泡動画で統合テスト**

EXP-11のテスト動画を画面再生してscreencaptureでキャプチャ、またはUVCでカメラに向けて検出確認。

```bash
# テスト動画があれば再生
cd /Users/yykt/ghq/github.com/katya4oyu/shabondama-study
python3 -c "import cv2; cv2.imshow('test', cv2.imread('data/images/master.jpg')); cv2.waitKey(0)"

# shabomを起動してscreencaptureモードで確認
cd shabom
cargo run -- --source screen --mode smoke --detector bright
```

確認項目:
- 検出結果（緑の円）がオーバーレイ表示される
- IDが各泡に付与されて複数フレーム維持される
- パラメータ変更が即座に反映される

- [ ] **Step 2: 透明泡モードのテスト**

```bash
cargo run -- --source screen --mode transparent
```

`data/images/closeup.jpg` などを表示した状態でテスト。

- [ ] **Step 3: 設計ドキュメントを保存する**

```bash
mkdir -p docs/superpowers/specs docs/superpowers/plans
# このプランファイルの内容をdocs/superpowers/plans/に保存
# 設計仕様部分をdocs/superpowers/specs/に保存
```

- [ ] **Step 4: 最終コミット**

```bash
git add docs/ shabom/
git commit -m "docs: add shabom design spec and implementation plan"
```

---

## 検証チェックリスト

| 項目 | 確認方法 |
|------|---------|
| ビルド成功 | `cargo build` エラーなし |
| ユニットテスト | `cargo test` 全パス |
| UVC起動 | `shabom --source uvc` でプレビュー表示 |
| Screen起動 | `shabom --source screen` でデスクトップ表示 |
| Smoke/bright検出 | スモーク泡動画で緑円オーバーレイ |
| Smoke/hough検出 | `d` キーで切替、smokey bubbleで動作 |
| 透明泡検出 | `--mode trans` + `closeup.jpg` で虹色泡を検出 |
| ID継続 | 同一泡が複数フレーム同一IDを維持 |
| パラメータ変更 | `←→` キーで値変更が次フレームに反映 |
| モード切替 | `m` `e` `d` キーが正常動作 |
| 終了 | `q` / `Ctrl+c` で端末が正常に戻る |

---

## 既知の制約・注意事項

- `screencapturekit` クレートのAPIはバージョンによって変動するため、実装前に `cargo doc` で確認必須
- `shiguredo-video-device` のバージョンは `cargo search shiguredo-video-device` で最新版を確認
- ratatui-image の Sixel/Kitty プロトコルは iTerm2 / WezTerm / Kitty 端末が必要。未対応端末ではハーフブロック描画にフォールバック
- MOG2の背景モデルは起動直後は未学習なので最初の数秒は誤検出が多い
- ソース切替（`s` キー）はスレッド再起動が必要なため、Task 12ではTODO扱い。必要に応じて `Arc<Mutex<Box<dyn CaptureSource>>>` + シグナルチャンネルで実装する
