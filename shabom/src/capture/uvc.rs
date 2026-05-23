use super::CaptureSource;
use anyhow::Context;
use opencv::{
    core::Mat,
    prelude::{MatTraitConst, VideoCaptureTraitConst, VideoCaptureTrait},
    videoio::{self, VideoCapture, CAP_ANY},
};

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
