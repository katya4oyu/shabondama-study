from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "data" / "images" / "bubble-detection"
MANIFEST_PATH = ASSET_DIR / "manifest.json"
OUTPUT_DIR = ASSET_DIR / "standardized" / "long-edge-1600-png"
OUTPUT_MANIFEST_PATH = OUTPUT_DIR / "manifest.json"
MAX_LONG_EDGE = 1600


def standardized_size(width: int, height: int) -> tuple[int, int]:
    long_edge = max(width, height)
    if long_edge <= MAX_LONG_EDGE:
        return width, height

    scale = MAX_LONG_EDGE / long_edge
    return round(width * scale), round(height * scale)


def main() -> None:
    records = json.loads(MANIFEST_PATH.read_text())
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    outputs = []
    for record in records:
        if record.get("review_status") != "accepted":
            continue

        source_path = ASSET_DIR / record["file"]
        with Image.open(source_path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            source_width, source_height = image.size
            target_width, target_height = standardized_size(source_width, source_height)
            if (target_width, target_height) != image.size:
                image = image.resize(
                    (target_width, target_height),
                    resample=Image.Resampling.LANCZOS,
                )

            output_name = f"{source_path.stem}.png"
            output_path = OUTPUT_DIR / output_name
            image.save(output_path, format="PNG", optimize=True)

        outputs.append(
            {
                "file": output_name,
                "source_file": record["file"],
                "source_dimensions": f"{source_width}x{source_height}",
                "dimensions": f"{target_width}x{target_height}",
                "format": "PNG",
                "color_mode": "RGB",
                "max_long_edge": MAX_LONG_EDGE,
                "conditions": record["conditions"],
            }
        )

    OUTPUT_MANIFEST_PATH.write_text(json.dumps(outputs, indent=2) + "\n")
    print(f"wrote {len(outputs)} standardized assets to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
