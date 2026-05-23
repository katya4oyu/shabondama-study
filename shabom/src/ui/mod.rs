pub mod controls;
pub mod preview;

use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    Frame,
};
use crate::app::AppState;

pub fn render(frame: &mut Frame, state: &AppState, image_state: &mut ratatui_image::protocol::StatefulProtocol) {
    let root = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Min(0), Constraint::Length(1)])
        .split(frame.area());

    let chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(60), Constraint::Percentage(40)])
        .split(root[0]);

    preview::render_preview(frame, chunks[0], state, image_state);
    controls::render_controls(frame, chunks[1], state);
    render_status_bar(frame, root[1]);
}

fn render_status_bar(frame: &mut Frame, area: Rect) {
    use ratatui::{widgets::Paragraph, style::{Style, Color}};
    let text = " Tab:移動  ↑↓:項目  ←→:値変更  m:モード  e:環境  s:ソース  q:終了";
    frame.render_widget(Paragraph::new(text).style(Style::default().bg(Color::DarkGray)), area);
}
