---
name: ui-ux-asset-pipeline
description: Redesign frontend visuals, generate professional bitmap assets through the GPT Image 2 Assets MCP, remove icon backgrounds, and integrate verified project-ready resources. Use for concrete app or site visual implementation, not generic image ideation.
---

# UI/UX Asset Pipeline

## Required order

1. Use `ui-ux-pro-max` to establish the product, audience, platform, visual direction, palette, typography, spacing, contrast, and responsive constraints. Inspect the existing UI entry point, theme, resource folders, and icon conventions before changing assets.
2. Call `list_ui_models` when exposed by the server. Use the configured default unless the task benefits from Qwen text rendering or a configured Seedream endpoint; an older server without this tool supports only the tools it actually lists.
3. Generate with `generate_ui_asset` and `prompt_profile=ui_pro`. Set `asset_type`, `platform`, `visual_style`, `brand_palette`, `composition`, `content_density`, and `text_policy` explicitly from the design system.
4. Keep one visual family across backgrounds and icons: repeat palette, material, lighting, perspective, geometry, and edge treatment. Backgrounds reserve quiet space behind real UI copy and contain no generated labels.
5. Save every selected URL inside the target project immediately. Provider URLs can expire and must never become production dependencies.
6. Remove generated icon backgrounds with `rembg`; then verify the result is RGBA and has non-opaque alpha. Generate an opaque icon sheet when the model cannot reliably return transparency.
7. Split icon sheets with `scripts/split_icon_sheet.py`. Run `--dry-run` first to confirm the detected icon count, then write. Keep final icons and the final background; remove intermediate sheets from project resources.
8. Integrate with the platform's native image component. Reserve intrinsic dimensions to prevent layout shift, lazy-load non-critical images, and use WebP/AVIF where the target supports them.
9. Give standalone meaningful icons accessible names. Treat backgrounds and icons beside visible labels as decorative.
10. Verify 375px, 768px, 1024px, and 1440px layouts, text contrast, focus visibility, touch targets, reduced motion, alpha, file dimensions, and the smallest relevant build/test command.

## Asset rules

- Hero/background: literal intended aspect ratio, focal placement, quiet copy area, no text, no logo, no UI screenshot.
- Empty state: compact focal illustration, restrained detail, clear silhouette, no decorative card backing unless the actual component needs one.
- Icon family: enumerate every icon, use consistent framing and optical weight, and request no card, watermark, emoji, or text.
- Product mockup: show the real product state clearly; avoid atmospheric crops that prevent inspection.
- Generated text: default to `no_text`. Use `exact_text` only when the text itself is the asset and verify every glyph.

## Commands

```powershell
rembg i input.png output.png

# Detect and confirm the icon count before writing anything.
python scripts/split_icon_sheet.py --input output.png --output-dir icons --layout auto --dry-run --expected 4

python scripts/split_icon_sheet.py --input output.png --output-dir icons --layout auto --names add edit delete search
```

`--layout auto` (the default) finds each icon from the alpha channel, so it tolerates the
uneven gutters and drift that generated sheets normally have. A fixed grid slices through
icons whenever the artwork does not line up with the cell edges, which is why detection is
the default and `--layout grid --columns N --rows M` is reserved for sheets that genuinely
are regular.

Always run `--dry-run` first: it prints each detected box so a wrong count is caught before
any file lands in the project. Tune from there:

| Symptom | Flag | Direction |
|---|---|---|
| Specks detected as icons | `--min-area` | raise |
| Faint icon missed | `--min-area` | lower |
| One icon split into fragments | `--merge-gap` | raise |
| Two icons merged together | `--merge-gap` | lower |
| rembg halo widening boxes | `--alpha-threshold` | raise |
| Icons cropped too tight or loose | `--padding-ratio` | adjust |
| Sheet is opaque, rembg unavailable | `--auto-matte` | add |

Icons are trimmed to their true alpha bounds and rescaled to a common canvas budget, so a
family generated at mixed sizes still reads at one optical weight.

If `rembg` is unavailable, use its isolated CLI: `uvx --python 3.12 --from "rembg[cpu,cli]" rembg i input.png output.png`.

For the full design-language-to-built-UI pipeline this fits into, see
[ui-design-studio](../ui-design-studio/SKILL.md).

Do not claim that an asset is transparent, responsive, accessible, or integrated until the corresponding output has been inspected or tested.
