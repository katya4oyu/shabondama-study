use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    widgets::{Block, List, ListItem, Paragraph},
    Frame,
};
use crate::{app::AppState, params::{BubbleMode, Environment, SourceKind, SmokeDetector}};

pub fn render_controls(frame: &mut Frame, area: Rect, state: &AppState) {
    let block = Block::bordered().title(" CONTROL ");
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let sections = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(6),  // MODE
            Constraint::Length(8),  // PARAMS
            Constraint::Min(4),     // TRACKS
            Constraint::Length(4),  // STATS
        ])
        .split(inner);

    render_mode_section(frame, sections[0], state);
    render_params_section(frame, sections[1], state);
    render_tracks_section(frame, sections[2], state);
    render_stats_section(frame, sections[3], state);
}

fn render_mode_section(frame: &mut Frame, area: Rect, state: &AppState) {
    let bubble_str = match state.mode {
        BubbleMode::Smoke => "[Smoke*] [Trans ]",
        BubbleMode::Transparent => "[Smoke ] [Trans*]",
    };
    let env_str = match state.env {
        Environment::Indoor => "[In*  ] [Out  ]",
        Environment::Outdoor => "[In   ] [Out* ]",
    };
    let src_str = match state.source {
        SourceKind::Uvc => "[UVC* ] [Scrn ]",
        SourceKind::Screen => "[UVC  ] [Scrn*]",
    };
    let det_str = match state.params.smoke_detector {
        SmokeDetector::Bright => "[bright*][hough][motion]",
        SmokeDetector::Hough => "[bright][hough*][motion]",
        SmokeDetector::Motion => "[bright][hough][motion*]",
    };
    let text = format!(
        "◆ MODE\n Bubble: {}\n Env:    {}\n Src:    {}\n Det:    {}",
        bubble_str, env_str, src_str, det_str
    );
    frame.render_widget(Paragraph::new(text), area);
}

fn render_params_section(frame: &mut Frame, area: Rect, state: &AppState) {
    let p = &state.params;
    let items: Vec<String> = match state.mode {
        BubbleMode::Smoke => match p.smoke_detector {
            SmokeDetector::Bright => vec![
                format!("  min_value  {:>4}", p.min_value),
                format!("  max_sat    {:>4}", p.max_saturation),
                format!("  nms_thresh {:>4.2}", p.nms_threshold),
                format!("  min_area   {:>4.0}", p.min_area),
            ],
            SmokeDetector::Hough => vec![
                format!("  param2     {:>4}", p.hough_param2),
                format!("  min_mean   {:>4.0}", p.min_mean_value),
                format!("  contrast   {:>4.0}", p.min_local_contrast),
                format!("  highlight  {:>4}", p.min_highlight_value),
                format!("  nms_thresh {:>4.2}", p.nms_threshold),
            ],
            SmokeDetector::Motion => vec![
                format!("  mog2_hist  {:>4}", p.mog2_history),
                format!("  var_thresh {:>4.0}", p.mog2_var_threshold),
                format!("  min_area   {:>4.0}", p.min_area),
                format!("  nms_thresh {:>4.2}", p.nms_threshold),
            ],
        },
        BubbleMode::Transparent => vec![
            format!("  param2     {:>4}", p.transparent_param2),
            format!("  hue_grad   {:>4}", p.hue_grad_threshold),
            format!("  pastel_s   {:>2}-{:<2}", p.pastel_s_min, p.pastel_s_max),
            format!("  pastel_v   {:>4}", p.pastel_v_min),
            format!("  nms_thresh {:>4.2}", p.transparent_nms),
        ],
    };

    let title = match (state.mode, state.params.smoke_detector) {
        (BubbleMode::Smoke, SmokeDetector::Bright) => "PARAMS (bright)",
        (BubbleMode::Smoke, SmokeDetector::Hough) => "PARAMS (hough)",
        (BubbleMode::Smoke, SmokeDetector::Motion) => "PARAMS (motion)",
        (BubbleMode::Transparent, _) => "PARAMS (transparent)",
    };

    let list_items: Vec<ListItem> = items.iter()
        .map(|line| ListItem::new(line.as_str()))
        .collect();

    let list = List::new(list_items).block(Block::bordered().title(format!("◆ {}", title)));
    frame.render_widget(list, area);
}

fn render_tracks_section(frame: &mut Frame, area: Rect, state: &AppState) {
    let mut lines = vec!["◆ TRACKS".to_string()];
    for t in state.tracks.iter().take(5) {
        lines.push(format!("  #{:<3} x:{:>4} y:{:>4} r:{:>3} age:{}", t.id, t.x as i32, t.y as i32, t.r as i32, t.age));
    }
    frame.render_widget(Paragraph::new(lines.join("\n")), area);
}

fn render_stats_section(frame: &mut Frame, area: Rect, state: &AppState) {
    let text = format!(
        "◆ STATS\n  Det:{:<3} Tracks:{:<3}\n  Frame:{:.1}ms  FPS:{:.1}",
        state.raw_count, state.tracks.len(), state.frame_ms, state.fps
    );
    frame.render_widget(Paragraph::new(text), area);
}
