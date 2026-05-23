use crate::{detect::{Detection, nms}, params::DetectorParams};
use opencv::{
    core::{self, AlgorithmHint, Mat, Point, Scalar, Size, Vector},
    imgproc,
    prelude::*,
};

pub struct TransparentPipeline;

impl TransparentPipeline {
    pub fn new() -> Self { Self }

    pub fn detect(&self, frame: &Mat, params: &DetectorParams) -> anyhow::Result<Vec<Detection>> {
        // BGR → HSV
        let mut hsv = Mat::default();
        imgproc::cvt_color(frame, &mut hsv, imgproc::COLOR_BGR2HSV, 0, AlgorithmHint::ALGO_HINT_DEFAULT)?;

        // Extract hue channel
        let mut channels: Vector<Mat> = Vector::new();
        core::split(&hsv, &mut channels)?;
        let hue = channels.get(0)?;

        let mut hue_f32 = Mat::default();
        hue.convert_to(&mut hue_f32, core::CV_32F, 1.0, 0.0)?;

        // Sobel gradient of hue
        let mut sobel_x = Mat::default();
        let mut sobel_y = Mat::default();
        imgproc::sobel(&hue_f32, &mut sobel_x, core::CV_32F, 1, 0, 3, 1.0, 0.0, core::BORDER_DEFAULT)?;
        imgproc::sobel(&hue_f32, &mut sobel_y, core::CV_32F, 0, 1, 3, 1.0, 0.0, core::BORDER_DEFAULT)?;

        // Gradient magnitude = sqrt(dx^2 + dy^2)
        let mut grad_mag = Mat::default();
        core::magnitude(&sobel_x, &sobel_y, &mut grad_mag)?;

        // Threshold: gradient > hue_grad_threshold
        let mut hue_grad_mask = Mat::default();
        core::compare(&grad_mag, &Scalar::from(params.hue_grad_threshold as f64), &mut hue_grad_mask, core::CMP_GT)?;

        // Dilate + morphological close
        let kernel = imgproc::get_structuring_element(
            imgproc::MORPH_ELLIPSE,
            Size::new(5, 5),
            Point::new(-1, -1),
        )?;
        let mut dilated = Mat::default();
        imgproc::dilate(&hue_grad_mask, &mut dilated, &kernel, Point::new(-1, -1), 2, core::BORDER_DEFAULT, Scalar::default())?;
        let mut combined_mask = Mat::default();
        imgproc::morphology_ex(&dilated, &mut combined_mask, imgproc::MORPH_CLOSE, &kernel, Point::new(-1, -1), 2, core::BORDER_DEFAULT, Scalar::default())?;

        // Pastel mask: S in [pastel_s_min, pastel_s_max], V in [pastel_v_min, 255]
        let lower = Scalar::new(0.0, params.pastel_s_min as f64, params.pastel_v_min as f64, 0.0);
        let upper = Scalar::new(180.0, params.pastel_s_max as f64, 255.0, 0.0);
        let mut pastel_mask = Mat::default();
        core::in_range(&hsv, &lower, &upper, &mut pastel_mask)?;

        // AND: iridescence = hue_grad AND pastel
        let mut iridescence_mask = Mat::default();
        core::bitwise_and(&combined_mask, &pastel_mask, &mut iridescence_mask, &core::no_array())?;

        // Apply mask to grayscale
        let mut gray = Mat::default();
        imgproc::cvt_color(frame, &mut gray, imgproc::COLOR_BGR2GRAY, 0, AlgorithmHint::ALGO_HINT_DEFAULT)?;

        let mut masked_gray = Mat::default();
        core::bitwise_and(&gray, &iridescence_mask, &mut masked_gray, &core::no_array())?;

        // Gaussian blur
        let mut blurred = Mat::default();
        imgproc::gaussian_blur(&masked_gray, &mut blurred, Size::new(9, 9), 2.0, 2.0, core::BORDER_DEFAULT, AlgorithmHint::ALGO_HINT_DEFAULT)?;

        // HoughCircles
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
