use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use anyhow::Context;
use image::DynamicImage;
use opencv::prelude::*;

use crate::{
    capture::CaptureSource,
    detect::{DetectResult, Detector},
    params::{BubbleMode, SourceKind, DetectorParams, Environment, SmokeDetector},
    track::BubbleTrack,
};

#[derive(Clone, Debug)]
pub struct AppState {
    pub mode: BubbleMode,
    pub env: Environment,
    pub source: SourceKind,
    pub params: DetectorParams,
    pub tracks: Vec<BubbleTrack>,
    pub latest_frame: Option<Arc<DynamicImage>>,
    pub fps: f64,
    pub frame_ms: f64,
    pub raw_count: usize,
}

impl AppState {
    pub fn new(mode: BubbleMode, env: Environment, source: SourceKind) -> Self {
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
        let initial_params = {
            let s = state.lock().unwrap();
            s.params.clone()
        };
        let mut detector = Detector::new(&initial_params).expect("Detector init failed");

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
    use opencv::core::AlgorithmHint;
    let mut rgb = Mat::default();
    imgproc::cvt_color(mat, &mut rgb, imgproc::COLOR_BGR2RGB, 0, AlgorithmHint::ALGO_HINT_DEFAULT)?;
    let rows = rgb.rows() as u32;
    let cols = rgb.cols() as u32;
    let data = rgb.data_bytes().context("Mat data_bytes failed")?;
    let buf = image::RgbImage::from_raw(cols, rows, data.to_vec())
        .context("RgbImage::from_raw failed")?;
    Ok(DynamicImage::ImageRgb8(buf))
}
