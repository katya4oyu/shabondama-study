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
