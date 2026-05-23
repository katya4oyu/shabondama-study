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
            Detection::new(105.0, 105.0, 25.0),
        ];
        let result = nms(circles, 0.5);
        assert_eq!(result.len(), 1);
    }

    #[test]
    fn nms_keeps_larger_circle_when_overlapping() {
        let circles = vec![
            Detection::new(100.0, 100.0, 15.0),
            Detection::new(102.0, 102.0, 30.0),
        ];
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

use crate::{
    params::{BubbleMode, DetectorParams, SmokeDetector},
    track::{BubbleTrack, Tracker},
};
use opencv::{
    core::{Mat, Point, Scalar},
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
    pub tracker: Tracker,
}

impl Detector {
    pub fn new(params: &DetectorParams) -> anyhow::Result<Self> {
        Ok(Self {
            smoke: SmokePipeline::new(params)?,
            transparent: TransparentPipeline::new(),
            tracker: Tracker::new(),
        })
    }

    pub fn process(&mut self, frame: &Mat, params: &DetectorParams, mode: BubbleMode) -> anyhow::Result<DetectResult> {
        let detections = match mode {
            BubbleMode::Smoke => match params.smoke_detector {
                SmokeDetector::Bright => self.smoke.detect_bright(frame, params)?,
                SmokeDetector::Hough  => self.smoke.detect_hough(frame, params)?,
                SmokeDetector::Motion => self.smoke.detect_motion(frame, params)?,
            },
            BubbleMode::Transparent => self.transparent.detect(frame, params)?,
        };

        let raw_count = detections.len();
        let tracks = self.tracker.update(&detections);

        // Draw green circle + ID label on annotated frame
        let mut annotated = Mat::try_clone(frame)?;
        for track in &tracks {
            let center = Point::new(track.x as i32, track.y as i32);
            let radius = track.r as i32;
            imgproc::circle(
                &mut annotated,
                center,
                radius,
                Scalar::new(0.0, 255.0, 0.0, 0.0),
                2,
                imgproc::LINE_AA,
                0,
            )?;
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
