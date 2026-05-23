mod detect;
mod params;

use clap::Parser;

#[derive(Parser, Debug)]
#[command(name = "shabom", about = "Real-time bubble detection TUI")]
pub struct Args {
    /// 初期映像ソース
    #[arg(long, default_value = "uvc")]
    pub source: String,

    /// 初期検出モード
    #[arg(long, default_value = "smoke")]
    pub mode: String,

    /// 初期環境
    #[arg(long, default_value = "indoor")]
    pub env: String,

    /// 初期Detectorサブモード
    #[arg(long, default_value = "bright")]
    pub detector: String,

    /// UVCデバイス番号
    #[arg(long, default_value_t = 0)]
    pub device: u32,

    /// キャプチャFPS上限
    #[arg(long, default_value_t = 30)]
    pub fps: u32,
}

fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    println!("shabom starting: source={} mode={} env={}", args.source, args.mode, args.env);
    Ok(())
}
