# Bubble Detection Test Images

Acquired on 2026-05-21 from Wikimedia Commons for local detection experiments.
JPEG files in this directory are gitignored; this document and `manifest.json`
are the tracked record of the accepted set.

Images are accepted only after opening the downloaded file and checking that the
actual pixels match the intended detection condition. File titles and Commons
descriptions are source metadata, not sufficient evidence by themselves.

## Acceptance Criteria

- A soap bubble is visibly present in the downloaded image.
- The bubble contour or film is useful for detection, not only an abstract thin
  film texture.
- The recorded condition tags match the visible image.
- Special cases are kept only when they exercise a clear detector failure mode.

## Format And Resolution Design

Keep two tiers:

- Source originals: downloaded files, stored locally and gitignored. Keep these
  for provenance checks and for recreating future variants.
- Standardized detector inputs: generated from accepted source originals by
  `scripts/prepare_bubble_detection_assets.py`, stored under
  `standardized/long-edge-1600-png/`, and gitignored.

Use PNG for standardized detector inputs. The sources are often JPEG already, so
PNG does not recover lost information, but it avoids adding another lossy
compression step when resizing or normalizing orientation.

Use 8-bit RGB with EXIF orientation applied. This keeps OpenCV/Pillow behavior
predictable and avoids silent rotation differences between viewers and scripts.

Use a maximum long edge of 1600 px without upscaling smaller images. This keeps
smoke tests fast on low-memory machines while preserving enough rim detail for
small bubbles. If a future experiment studies tiny distant bubbles, create a
separate high-resolution tier instead of silently changing this one.

## Condition Axes

- Bubble count: single, few, many, dense cluster.
- Bubble scale: small, medium, large, giant, macro.
- Human presence: none, clothed child, adult performer/crowd.
- Scene: outdoor grass, outdoor street, garden, close-up.
- Background brightness: dark, mixed, bright, backlit.
- Background complexity: blurred, vegetation, urban clutter, simple close-up.
- Shape and appearance: round, irregular, transparent rim, iridescent highlights,
  overlapping bubbles.

## Accepted Files

| File | License | Visual review result | Useful conditions |
| --- | --- | --- | --- |
| `soap_bubbles_supermacro_pd.jpg` | Public Domain | accepted: dense connected bubble cells are visible; useful as a close-up stress case | many, macro, no person, close-up, high-contrast rims |
| `master_of_soapbubbles_cc0.jpg` | CC0 1.0 | accepted: many real bubbles over a busy street scene with people | many, mixed sizes, person/crowd, outdoor, cluttered background |
| `irregular_bubble_cc0.jpg` | CC0 1.0 | accepted: one large non-circular bubble is clearly isolated | single/few, irregular, no person, outdoor, textured background |
| `soap_bubble_closeup_cc_by_2_0.jpg` | CC BY 2.0 | accepted: one large circular bubble with a clean rim and blurred background | single, large, no person, outdoor, shallow depth of field |
| `soap_bubbles_algerian_grassland_cc_by_sa_4_0.jpg` | CC BY-SA 4.0 | accepted: clothed child blowing a small chain of bubbles in strong backlight | few, small/medium, clothed child, outdoor grass, bright/backlit |
| `giant_bubble_cc_by_sa_3_0.jpg` | CC BY-SA 3.0 | accepted: one giant irregular bubble with an adult performer | single, giant, adult, outdoor vegetation, irregular contour |
| `soap_bubble_grapevine_cc_by_sa_3_0.jpg` | CC BY-SA 3.0 | accepted: one round bubble against leafy garden clutter | single, large, no person, garden, cluttered green background |
| `girl_with_soap_bubble_machine_cc_by_2_0.jpg` | CC BY 2.0 | accepted: clothed child with many small bubbles from a bubble machine | many, small, clothed child, outdoor, dark/blurred background |

## Rejected Local Downloads

These files may still exist locally because images are ignored by git, but they
are not part of the accepted set in `manifest.json`.

| File | Reason |
| --- | --- |
| `soap_bubbles_iridescent_pd.jpg` | rejected: mostly cropped thin-film arcs on black; useful for optics texture, weak as a bubble detector input |
| `soap_bubbles_bathroom_cc_by_sa_4_0.jpg` | rejected: downloaded image is not a bathroom scene despite the title-derived filename; condition metadata would be misleading |
| `macro_photography_soap_bubble_cc_by_sa_4_0.jpg` | rejected: abstract macro film texture with incomplete bubble boundary; better for film-pattern study than object detection |
| `frozen_soap_bubble_cc_by_2_0.jpg` | rejected: bubble is partially cropped and frozen texture dominates; keep out of the first detector smoke set |
| `blowing_soap_bubbles_cc_by_2_0.jpg` | rejected: child subject is shirtless; avoid this asset class for the validation set |
| `bubble_blowing_14_cc_by_sa_4_0.jpg` | rejected: clothed child is acceptable, but only one forming bubble is visible; less useful than the accepted replacement for count/overlap coverage |

## License Notes

For CC BY and CC BY-SA images, attribution is required in publications,
datasets distributed outside the repository, or derived outputs where attribution
is expected. Keep source page URLs with any copied subset.
