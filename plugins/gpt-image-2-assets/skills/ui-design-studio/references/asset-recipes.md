# Asset recipes

Per-asset parameters for `generate_ui_asset`. Keep the palette, material, lighting,
perspective, and edge treatment identical across every asset so the set reads as one family.
All sizes for gpt-image-2 must have both edges as multiples of 16, aspect within 1:3–3:1.

## Interface mockup (review artifact)

| Field | Value |
|---|---|
| `asset_type` | `interface_mockup` |
| `text_policy` | `minimal_text` |
| `size` | viewport aspect, e.g. `1536x1024` web, `1024x1536` mobile portrait |
| `quality` | `high` |

Not a production asset — see [mockup-prompting.md](mockup-prompting.md).

## Hero / section background

| Field | Value |
|---|---|
| `asset_type` | `hero_background` |
| `text_policy` | `no_text` |
| `background` | `opaque` (gpt-image-2 cannot do transparent) |
| `size` | the literal region aspect it fills |
| `composition` | reserve a quiet copy-safe area; focal subject away from headings/buttons/nav |

## Texture / pattern

| Field | Value |
|---|---|
| `asset_type` | `texture` or `pattern` |
| `text_policy` | `no_text` |
| `content_density` | `airy` — must stay subordinate to foreground UI |
| `composition` | tileable or crop-safe, low contrast |

## Icon family

| Field | Value |
|---|---|
| `asset_type` | `icon` |
| `text_policy` | `no_text` |
| `size` | square, e.g. `1024x1024`, laid out as one regular sheet |
| `composition` | consistent optical box, stroke weight, corner language; no card, watermark, emoji, or text |

Generate the **whole family as one sheet** so weight and geometry stay consistent, then
key out the background and split. Because gpt-image-2 returns opaque output:

```bash
rembg i sheet.png sheet-cut.png
python scripts/split_icon_sheet.py --input sheet-cut.png --output-dir icons \
  --layout auto --dry-run --expected <count>       # confirm detection first
python scripts/split_icon_sheet.py --input sheet-cut.png --output-dir icons \
  --layout auto --names <name1> <name2> ...
```

Splitter tuning (auto layout):

| Symptom | Flag | Direction |
|---|---|---|
| Specks detected as icons | `--min-area` | raise |
| Faint icon missed | `--min-area` | lower |
| One icon split into pieces | `--merge-gap` | raise |
| Two icons merged into one | `--merge-gap` | lower |
| rembg halo widening boxes | `--alpha-threshold` | raise |
| Icons cropped too tight/loose | `--padding-ratio` | adjust |
| Sheet has no alpha, rembg skipped | `--auto-matte` | add (keys out a solid background) |

Use `--layout grid --columns N --rows M` only when the sheet genuinely is a regular grid.

## Logo / mark

| Field | Value |
|---|---|
| `asset_type` | `logo` |
| `text_policy` | `no_text` unless the wordmark itself is the asset |
| `composition` | simple distinctive mark, scalable edges, no mockup context |

## Product mockup vs interface mockup

`product_mockup` art-directs a **product** in realistic context (a physical object, a device
in a scene). `interface_mockup` art-directs a **screen design** flat and full-frame. Do not
use `product_mockup` for a UI concept — it adds perspective and bezels you then have to
fight.
