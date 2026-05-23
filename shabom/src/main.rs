mod app;
mod capture;
mod detect;
mod params;
mod track;
mod ui;

use clap::Parser;
use params::{BubbleMode, SourceKind, Environment};
use std::sync::{Arc, Mutex};

#[derive(Parser, Debug)]
#[command(name = "shabom", about = "Real-time bubble detection TUI")]
pub struct Args {
    #[arg(long, default_value = "uvc")]   pub source: String,
    #[arg(long, default_value = "smoke")] pub mode: String,
    #[arg(long, default_value = "indoor")] pub env: String,
    #[arg(long, default_value = "bright")] pub detector: String,
    #[arg(long, default_value_t = 0)]     pub device: u32,
    #[arg(long, default_value_t = 30)]    pub fps: u32,
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

    let state = Arc::new(Mutex::new(app::AppState::new(mode, env_val, source_val)));

    let cap: Box<dyn capture::CaptureSource> = match source_val {
        SourceKind::Uvc    => Box::new(capture::uvc::UvcCapture::new(args.device)?),
        SourceKind::Screen => Box::new(capture::screen::ScreenCapture::new()?),
    };

    let (tx_frame, rx_frame) = std::sync::mpsc::sync_channel(2);
    let (tx_result, rx_result) = std::sync::mpsc::sync_channel(2);

    app::spawn_capture_thread(cap, tx_frame);
    app::spawn_detect_thread(rx_frame, tx_result, Arc::clone(&state));

    // Temporary: print results to stdout (Task 12 replaces this with TUI)
    for (result, elapsed) in rx_result.iter().take(30) {
        println!(
            "tracks={} raw={} elapsed={:.1}ms",
            result.tracks.len(),
            result.raw_count,
            elapsed.as_secs_f64() * 1000.0
        );
    }

    Ok(())
}
