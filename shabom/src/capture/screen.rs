use super::CaptureSource;
use opencv::core::Mat;

pub struct ScreenCapture {
    name: String,
}

impl ScreenCapture {
    pub fn new() -> anyhow::Result<Self> {
        // Task 6で実装
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
