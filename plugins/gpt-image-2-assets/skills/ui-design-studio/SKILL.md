---
name: ui-design-studio
description: Design-first pipeline for building a real interface — establish a design language, generate a static mockup for the user to approve, then build the UI and produce every background and icon through the GPT Image 2 Assets MCP. Use this whenever the user wants a screen, page, app UI, or visual redesign built (not just an isolated image): "design and build a dashboard", "make this app look good", "I need a landing page with custom graphics", "redesign this screen". Also use when the user wants a UI mockup reviewed before any code is written.
metadata:
  short-description: Design language, approved mockup, then a built UI with generated assets
---

# UI Design Studio

Build interfaces in the order a design studio does: decide the visual language, get a
picture approved, then implement. The order matters because each phase constrains the next
— code written before the language is settled gets rewritten, and assets generated before
the language is settled do not match each other.

The pipeline is: **design language → static mockup → user approval → build → assets → verify.**

## Phase 0: Read the ground truth

Before proposing anything, look at what exists. Check the frontend stack (`package.json`,
`pubspec.yaml`, `*.xcodeproj`, `composer.json`), the current theme or token file, the
resource folders, the icon convention already in use, and the component library. A design
language that fights the existing codebase costs more than it is worth.

If `design-system/<project-slug>/MASTER.md` already exists, read it and treat it as the
source of truth. Do not regenerate it or pass `--force` without the user explicitly asking.

## Phase 1: Design language, before any pixels

Produce the language in writing first. Generating an image before this is settled produces
art you then have to reverse-engineer intent from.

Run `ui-ux-pro-max` for the systematic layer — pattern, palette, typography, spacing,
contrast, anti-patterns:

```bash
python "<ui-ux-pro-max-path>/scripts/search.py" "<product> <industry> <keywords>" \
  --design-system --persist -p "<Project Name>" --output-dir "<project-root>"
```

Then apply `frontend-design` for the point of view, because a systematic palette alone
still produces something templated. From that skill, the parts that matter most here:

- Open with the most characteristic thing in the subject's world, not a generic hero.
- Pair display and body faces deliberately; typography carries the personality.
- Structural devices (numbering, eyebrows, dividers) must encode something true about the
  content rather than decorate it.
- Pick **one** signature element the page is remembered by, and keep everything else quiet.
- Avoid the three AI-default looks: cream background with high-contrast serif and terracotta
  accent; near-black with one acid accent; broadsheet with hairline rules and zero radius.
  They are defaults rather than choices. If the user's brief explicitly asks for one, follow
  the brief — the brief always wins.

Write the result down as: 4–6 named hex values, the typefaces and their roles, a layout
concept, the signature element, and an ASCII wireframe. Review it once against the brief
before continuing: if any part reads like what you would produce for any similar product,
revise it and say what changed.

**Gate: do not call `generate_ui_asset` until this is written down.**

## Phase 2: Static mockup

Translate the language into one image. Use `asset_type=interface_mockup`, which art-directs
a flat full-frame screen rather than a product photo:

```
generate_ui_asset(
  prompt="<screen role, section order, component inventory, what each region does>",
  asset_type="interface_mockup",
  platform="<web|mobile|desktop>",
  visual_style="<from the design language>",
  brand_palette="<the 4-6 hex values, named>",
  composition="<layout concept and hierarchy>",
  content_density="<airy|balanced|dense>",
  text_policy="minimal_text",
  size="<viewport aspect, edges multiple of 16 for gpt-image-2>",
  quality="high"
)
```

Save it to `design-system/<project-slug>/mockups/v<N>/` immediately along with the prompt
used. Provider URLs expire, so an unsaved mockup is a mockup you cannot compare against
later. Consider `n=2` for genuinely different directions — but present them as alternatives,
not as a menu that offloads the design decision onto the user.

`text_policy=minimal_text` is deliberate: raster models garble long strings, and dense fake
copy makes a mockup harder to judge, not easier.

## Phase 3: Review with the user

Show the mockup and state what you were trying to achieve — the signature element, the
hierarchy, the one risk you took. Ask directly whether the direction is right.

If the user is not satisfied, do not tweak the image prompt in isolation. Take the concrete
objection back to **Phase 1**, revise the design language, and regenerate as `v<N+1>`. Keep
every version; the diff between versions is what makes the next round converge instead of
oscillating. Vague feedback ("make it pop") needs one clarifying question before you spend
another generation.

Only continue once the user has approved a direction.

## Phase 4: Build from tokens, not from pixels

Implement in the detected stack, pulling implementation guidance with
`--stack <detected-stack>`.

**Derive every color, size, and type value from the written design language — not by
eyeballing the mockup.** The mockup is a review artifact for art direction. It has garbled
text, invented glyphs, and pixel dimensions that mean nothing. Trying to pixel-match it
wastes effort and reproduces the model's mistakes. What it settles is composition, mood,
palette relationships, and weight; those you already have in writing.

Build real components with real content, honouring the quality floor: responsive to mobile,
visible keyboard focus, respected reduced-motion, semantic color tokens rather than raw hex
scattered through components.

## Phase 5: Generate the assets the build needs

List what the UI actually needs before generating anything — path, role, target dimensions,
and format per asset. Generating reactively produces a set that does not match.

Keep one visual family across every asset: repeat the palette, material, lighting,
perspective, geometry, and edge treatment from the design language in every prompt. That
repetition is what makes separately generated assets look like one system.

**Backgrounds and textures:** `asset_type=hero_background` or `texture`,
`text_policy=no_text`. Reserve quiet space where real copy will sit, and keep the focal
subject away from headings, buttons, and navigation.

**Icons:** generate one sheet for the whole family so weight and geometry stay consistent.
Enumerate every icon in the prompt and ask for a regular arrangement, no card backing, no
watermark, no text. GPT Image 2 cannot produce transparent backgrounds, so generate an
opaque sheet and key it out afterwards.

```bash
rembg i sheet.png sheet-cut.png

# Detect first and confirm the count before writing anything.
python scripts/split_icon_sheet.py --input sheet-cut.png --output-dir icons \
  --layout auto --dry-run --expected 8

python scripts/split_icon_sheet.py --input sheet-cut.png --output-dir icons \
  --layout auto --names add edit delete search share filter sort more
```

The `--dry-run` pass is what keeps broken cuts out of the project: it reports each detected
box so you can confirm the count and rough sizes before any file is written. If detection
finds the wrong number, tune `--min-area` (raise it to ignore specks, lower it to catch
faint icons) and `--merge-gap` (raise it when one icon is being split into fragments, lower
it when two neighbours are being merged). Reach for `--layout grid --columns N --rows M`
only when the sheet really is on a regular grid. See
[ui-ux-asset-pipeline](../ui-ux-asset-pipeline/SKILL.md) for the full asset rules.

Verify each icon is RGBA with non-opaque alpha before integrating. Keep the final icons and
background; remove the intermediate sheets from project resources.

Integrate with the platform's native image component, reserve intrinsic dimensions so
nothing shifts on load, lazy-load non-critical images, and prefer WebP/AVIF where supported.
Give standalone meaningful icons accessible names; treat backgrounds and icons that sit
beside a visible label as decorative.

## Phase 6: Verify before claiming it works

Check 375px, 768px, 1024px, and 1440px. Confirm text contrast, visible focus, touch targets,
and reduced-motion behavior. Confirm no provider URL survives as a runtime dependency, and
run the smallest relevant build or test command.

Do not describe an asset as transparent, responsive, accessible, or integrated until the
corresponding output has actually been inspected or the command has actually been run.

## References

- [mockup-prompting.md](references/mockup-prompting.md) — writing the interface_mockup prompt
- [asset-recipes.md](references/asset-recipes.md) — per-asset-type parameters and sizes
- [review-loop.md](references/review-loop.md) — turning vague feedback into a revision
