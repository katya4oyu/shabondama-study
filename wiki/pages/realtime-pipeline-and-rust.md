---
title: リアルタイム検出パイプラインと Rust 化
created_at: 2026-05-22
updated_at: 2026-05-22
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
