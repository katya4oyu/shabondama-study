mod app;
mod capture;
mod detect;
mod params;
mod track;
mod ui;

use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use clap::Parser;
use crossterm::{
    event::{self, Event, KeyCode, KeyModifiers},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{backend::CrosstermBackend, Terminal};
use ratatui_image::picker::Picker;

use crate::{
    app::{mat_to_dynamic_image, AppState},
    params::{BubbleMode, SourceKind, Environment, SmokeDetector},
};

#[derive(Parser, Debug)]
#[command(name = "shabom", about = "Real-time bubble detection TUI")]
pub struct Args {
    #[arg(long, default_value = "uvc")]    pub source: String,
    #[arg(long, default_value = "smoke")]  pub mode: String,
    #[arg(long, default_value = "indoor")] pub env: String,
    #[arg(long, default_value = "bright")] pub detector: String,
    #[arg(long, default_value_t = 0)]      pub device: u32,
    #[arg(long, default_value_t = 30)]     pub fps: u32,
}

fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    let mode = match args.mode.as_str() {
        "trans" | "transparent" => BubbleMode::Transparent,
        _ => BubbleMode::Smoke,
    };
    let env_val = match args.env.as_str() {
        "outdoor" => Environment::Outdoor,
        _ => Environment::Indoor,
    };
    let source_val = match args.source.as_str() {
        "screen" => SourceKind::Screen,
        _ => SourceKind::Uvc,
    };

    let state = Arc::new(Mutex::new(AppState::new(mode, env_val, source_val)));

    let cap: Box<dyn capture::CaptureSource> = match source_val {
        SourceKind::Uvc    => Box::new(capture::uvc::UvcCapture::new(args.device)?),
        SourceKind::Screen => Box::new(capture::screen::ScreenCapture::new()?),
    };

    let (tx_frame, rx_frame) = std::sync::mpsc::sync_channel(2);
    let (tx_result, rx_result) = std::sync::mpsc::sync_channel(2);

    app::spawn_capture_thread(cap, tx_frame);
    app::spawn_detect_thread(rx_frame, tx_result, Arc::clone(&state));

    // Terminal setup
    enable_raw_mode()?;
    let mut stdout = std::io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    // ratatui-image v11: query terminal after entering alternate screen,
    // before reading events. Falls back to halfblocks if query fails.
    let mut picker = Picker::from_query_stdio().unwrap_or_else(|_| Picker::halfblocks());

    // Start with a 1x1 transparent placeholder so image_state is always valid
    let placeholder = image::DynamicImage::new_rgb8(1, 1);
    let mut image_state = picker.new_resize_protocol(placeholder);

    let mut fps_counter = 0u32;
    let mut fps_timer = Instant::now();

    let result = 'main: loop {
        // Drain detection results (non-blocking)
        while let Ok((detect_result, elapsed)) = rx_result.try_recv() {
            let dyn_img = mat_to_dynamic_image(&detect_result.annotated)?;
            let arc_img = Arc::new(dyn_img);
            let proto = picker.new_resize_protocol((*arc_img).clone());
            image_state = proto;

            let mut s = state.lock().unwrap();
            s.latest_frame = Some(arc_img);
            s.tracks = detect_result.tracks;
            s.raw_count = detect_result.raw_count;
            s.frame_ms = elapsed.as_secs_f64() * 1000.0;

            fps_counter += 1;
            if fps_timer.elapsed() >= Duration::from_secs(1) {
                s.fps = fps_counter as f64 / fps_timer.elapsed().as_secs_f64();
                fps_counter = 0;
                fps_timer = Instant::now();
            }
        }

        // Draw
        {
            let s = state.lock().unwrap().clone();
            terminal.draw(|f| ui::render(f, &s, &mut image_state))?;
        }

        // Handle key input (16ms timeout ≈ 60 FPS UI)
        if event::poll(Duration::from_millis(16))? {
            if let Event::Key(key) = event::read()? {
                let mut s = state.lock().unwrap();
                match key.code {
                    KeyCode::Char('q') => break 'main Ok(()),
                    KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                        break 'main Ok(())
                    }
                    KeyCode::Char('m') => {
                        s.mode = match s.mode {
                            BubbleMode::Smoke => BubbleMode::Transparent,
                            BubbleMode::Transparent => BubbleMode::Smoke,
                        };
                        s.apply_preset();
                    }
                    KeyCode::Char('e') => {
                        s.env = match s.env {
                            Environment::Indoor => Environment::Outdoor,
                            Environment::Outdoor => Environment::Indoor,
                        };
                        s.apply_preset();
                    }
                    KeyCode::Char('d') => {
                        s.params.smoke_detector = match s.params.smoke_detector {
                            SmokeDetector::Bright => SmokeDetector::Hough,
                            SmokeDetector::Hough => SmokeDetector::Motion,
                            SmokeDetector::Motion => SmokeDetector::Bright,
                        };
                    }
                    KeyCode::Char('s') => {
                        s.source = match s.source {
                            SourceKind::Uvc => SourceKind::Screen,
                            SourceKind::Screen => SourceKind::Uvc,
                        };
                        // TODO(Task 13): source switch requires thread restart
                    }
                    _ => {}
                }
            }
        }
    };

    // Cleanup
    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;

    result
}
