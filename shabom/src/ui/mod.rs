pub mod controls;
pub mod preview;

use ratatui::{
    layout::{Constraint, Direction, Layout},
    Frame,
};
use crate::app::AppState;

pub fn render(frame: &mut Frame, state: &AppState, image_state: &mut ratatui_image::protocol::StatefulProtocol) {
    let chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(60), Constraint::Percentage(40)])
        .split(frame.area());

    preview::render_preview(frame, chunks[0], state, image_state);
    controls::render_controls(frame, chunks[1], state);
    render_status_bar(frame, state);
}

fn render_status_bar(frame: &mut Frame, _state: &AppState) {
    use ratatui::{layout::*, widgets::*, style::*};
    let area = frame.area();
    let bar = Rect::new(0, area.height.saturating_sub(1), area.width, 1);
    let text = " Tab:移動  ↑↓:項目  ←→:値変更  m:モード  e:環境  s:ソース  q:終了";
    frame.render_widget(Paragraph::new(text).style(Style::default().bg(Color::DarkGray)), bar);
}
