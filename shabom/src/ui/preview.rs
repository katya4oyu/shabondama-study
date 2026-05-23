use ratatui::{layout::Rect, Frame};
use ratatui_image::protocol::StatefulProtocol;
use crate::app::AppState;

pub fn render_preview(
    frame: &mut Frame,
    area: Rect,
    _state: &AppState,
    image_state: &mut StatefulProtocol,
) {
    use ratatui::widgets::Block;
    use ratatui_image::StatefulImage;

    let block = Block::bordered().title(" PREVIEW ");
    let inner = block.inner(area);
    frame.render_widget(block, area);

    if _state.latest_frame.is_some() {
        let image_widget: StatefulImage<StatefulProtocol> = StatefulImage::new();
        frame.render_stateful_widget(image_widget, inner, image_state);
    }
}
