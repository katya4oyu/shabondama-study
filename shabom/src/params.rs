#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BubbleMode { Smoke, Transparent }

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Environment { Indoor, Outdoor }

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SourceKind { Uvc, Screen }   // NOTE: SourceKind, not CaptureSource

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
