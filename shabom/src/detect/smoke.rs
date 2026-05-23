use crate::{detect::{Detection, nms}, params::DetectorParams};
use opencv::{
    core::{self, AlgorithmHint, Mat, Point, Rect, Scalar, Size, Vector},
    imgproc,
    prelude::*,
    video,
};

pub struct SmokePipeline {
    mog2: core::Ptr<video::BackgroundSubtractorMOG2>,
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

    /// bright モード: HSV低彩度/高輝度マスク → 輪郭 → NMS
    pub fn detect_bright(&self, frame: &Mat, params: &DetectorParams) -> anyhow::Result<Vec<Detection>> {
        let mut hsv = Mat::default();
        imgproc::cvt_color(frame, &mut hsv, imgproc::COLOR_BGR2HSV, 0, AlgorithmHint::ALGO_HINT_DEFAULT)?;

        let lower = Scalar::new(0.0, 0.0, params.min_value as f64, 0.0);
        let upper = Scalar::new(180.0, params.max_saturation as f64, 255.0, 0.0);
        let mut mask = Mat::default();
        core::in_range(&hsv, &lower, &upper, &mut mask)?;

        self.contour_to_detections(&mask, params)
    }

    /// hough モード: HoughCircles + 輝度フィルタ → NMS
    pub fn detect_hough(&self, frame: &Mat, params: &DetectorParams) -> anyhow::Result<Vec<Detection>> {
        let mut gray = Mat::default();
        imgproc::cvt_color(frame, &mut gray, imgproc::COLOR_BGR2GRAY, 0, AlgorithmHint::ALGO_HINT_DEFAULT)?;

        let mut blurred = Mat::default();
        imgproc::gaussian_blur(&gray, &mut blurred, Size::new(9, 9), 2.0, 2.0, core::BORDER_DEFAULT, AlgorithmHint::ALGO_HINT_DEFAULT)?;

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

            let x0 = ((cx - r) as i32).max(0);
            let y0 = ((cy - r) as i32).max(0);
            let x1 = ((cx + r) as i32).min(cols);
            let y1 = ((cy + r) as i32).min(rows);
            if x1 <= x0 || y1 <= y0 { continue; }

            let roi = Mat::roi(frame, Rect::new(x0, y0, x1 - x0, y1 - y0))?;
            let mean_val = core::mean(&roi, &core::no_array())?;
            let mean_v = (mean_val[0] + mean_val[1] + mean_val[2]) / 3.0;

            if mean_v < params.min_mean_value { continue; }

            // ローカルコントラスト: 内円より外リングとの輝度差
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

        Ok(nms(detections, params.nms_threshold))
    }

    /// motion モード: MOG2背景差分 → モルフォロジー → 輪郭 → NMS
    pub fn detect_motion(&mut self, frame: &Mat, params: &DetectorParams) -> anyhow::Result<Vec<Detection>> {
        let mut fg_mask = Mat::default();
        BackgroundSubtractorTrait::apply(&mut self.mog2, frame, &mut fg_mask, -1.0)?;

        let kernel = imgproc::get_structuring_element(
            imgproc::MORPH_ELLIPSE,
            Size::new(5, 5),
            Point::new(-1, -1),
        )?;
        let fg_src = fg_mask.clone();
        imgproc::morphology_ex(
            &fg_src,
            &mut fg_mask,
            imgproc::MORPH_OPEN,
            &kernel,
            Point::new(-1, -1),
            2,
            core::BORDER_DEFAULT,
            Scalar::default(),
        )?;

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
