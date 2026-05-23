use super::CaptureSource;
use anyhow::Context;
use opencv::{
    core::{Mat, CV_8UC3, CV_8UC4},
    imgproc,
};
use screencapturekit::{
    cm::{CMSampleBuffer, CMSampleBufferExt},
    cv::CVPixelBufferLockFlags,
    prelude::*,
};
use std::sync::{Arc, Condvar, Mutex};

/// Raw frame data: BGRA bytes + dimensions
type FrameBuffer = Option<(Vec<u8>, usize, usize)>;

/// Background-thread frame handler that stores the latest captured frame.
struct FrameHandler {
    state: Arc<(Mutex<FrameBuffer>, Condvar)>,
}

impl SCStreamOutputTrait for FrameHandler {
    fn did_output_sample_buffer(
        &self,
        sample_buffer: CMSampleBuffer,
        of_type: SCStreamOutputType,
    ) {
        if of_type != SCStreamOutputType::Screen {
            return;
        }

        // Extract CVPixelBuffer from the sample
        let Some(pixel_buffer) = sample_buffer.image_buffer() else {
            return;
        };

        let width = pixel_buffer.width();
        let height = pixel_buffer.height();
        if width == 0 || height == 0 {
            return;
        }

        // Lock and copy pixel data
        let Ok(guard) = pixel_buffer.lock(CVPixelBufferLockFlags::READ_ONLY) else {
            return;
        };

        let bytes_per_row = guard.bytes_per_row();
        let slice = guard.as_slice();
        if slice.is_empty() {
            return;
        }

        // Compact rows (strip any row padding) into a plain BGRA vec
        let row_bytes = width * 4;
        let mut data = Vec::with_capacity(width * height * 4);
        for row in 0..height {
            let start = row * bytes_per_row;
            let end = start + row_bytes;
            if end <= slice.len() {
                data.extend_from_slice(&slice[start..end]);
            }
        }

        // Notify next_frame()
        let (lock, cvar) = &*self.state;
        let mut frame = lock.lock().unwrap();
        *frame = Some((data, width, height));
        cvar.notify_one();
    }
}

/// Screen capture source backed by ScreenCaptureKit.
pub struct ScreenCapture {
    name: String,
    /// Shared buffer between background capture thread and next_frame().
    state: Arc<(Mutex<FrameBuffer>, Condvar)>,
    /// Keep the stream alive.
    _stream: SCStream,
}

impl ScreenCapture {
    /// Create a new screen capture for the primary display.
    pub fn new() -> anyhow::Result<Self> {
        // Get shareable content (blocks synchronously)
        let content = SCShareableContent::get()
            .map_err(|e| anyhow::anyhow!("SCShareableContent::get failed: {e}"))?;

        let display = content
            .displays()
            .into_iter()
            .next()
            .ok_or_else(|| anyhow::anyhow!("No display found"))?;

        let width = display.width() as usize;
        let height = display.height() as usize;
        let name = format!("Screen:{}x{}", width, height);

        let filter = SCContentFilter::create()
            .with_display(&display)
            .with_excluding_windows(&[])
            .build();

        let config = SCStreamConfiguration::new()
            .with_width(width as u32)
            .with_height(height as u32)
            .with_pixel_format(PixelFormat::BGRA)
            .with_shows_cursor(false);

        let state: Arc<(Mutex<FrameBuffer>, Condvar)> =
            Arc::new((Mutex::new(None), Condvar::new()));

        let handler = FrameHandler {
            state: Arc::clone(&state),
        };

        let mut stream = SCStream::new(&filter, &config);
        stream.add_output_handler(handler, SCStreamOutputType::Screen);
        stream
            .start_capture()
            .map_err(|e| anyhow::anyhow!("SCStream::start_capture failed: {e}"))?;

        Ok(Self {
            name,
            state,
            _stream: stream,
        })
    }
}

impl CaptureSource for ScreenCapture {
    fn next_frame(&mut self) -> anyhow::Result<Mat> {
        // Block until a frame arrives
        let (lock, cvar) = &*self.state;
        let mut frame_opt = lock.lock().unwrap();
        loop {
            if frame_opt.is_some() {
                break;
            }
            frame_opt = cvar.wait(frame_opt).unwrap();
        }
        let (data, width, height) = frame_opt.take().unwrap();

        bgra_to_bgr_mat(&data, width as u32, height as u32)
            .context("Failed to convert BGRA frame to BGR Mat")
    }

    fn name(&self) -> &str {
        &self.name
    }
}

/// Convert a flat BGRA byte slice into a BGR `Mat`.
fn bgra_to_bgr_mat(data: &[u8], width: u32, height: u32) -> anyhow::Result<Mat> {
    let w = width as i32;
    let h = height as i32;

    // Wrap BGRA bytes into a Mat (no copy)
    let bgra_mat = unsafe {
        Mat::new_rows_cols_with_data_unsafe(h, w, CV_8UC4, data.as_ptr() as *mut _, 0)
    }
    .context("Failed to create BGRA Mat")?;

    // Convert BGRA -> BGR
    let mut bgr_mat = Mat::new_rows_cols_with_default(h, w, CV_8UC3, opencv::core::Scalar::all(0.0))
        .context("Failed to allocate BGR Mat")?;
    imgproc::cvt_color(
        &bgra_mat,
        &mut bgr_mat,
        imgproc::COLOR_BGRA2BGR,
        0,
        opencv::core::AlgorithmHint::ALGO_HINT_DEFAULT,
    )
    .context("cvt_color BGRA->BGR failed")?;

    Ok(bgr_mat)
}
