# Writing the interface_mockup prompt

`asset_type=interface_mockup` art-directs one flat, full-frame screen — no device bezel, no
perspective, no desk scene. Your prompt supplies what the model cannot infer: the screen's
job, its regions, and the relative weight of each.

## What to include

1. **Screen role** — "analytics dashboard landing", "mobile checkout step 2", "settings page".
2. **Section order, top to bottom** — name each region and what lives in it. This is the
   single most useful part; without it the model invents a generic layout.
3. **Component inventory** — nav bar, sidebar, cards, table, chart placeholders, form,
   primary button. Say which is dominant.
4. **Hierarchy** — what the eye should hit first, second, third.
5. **The design language** — palette (named hex), type roles, spacing feel, signature element.
6. **Aspect** — pass `size` at the real viewport aspect; for gpt-image-2 both edges must be
   multiples of 16.

## What to leave out

- Long UI copy. `text_policy=minimal_text` keeps lettering as indicative blocking; raster
  models garble real strings and dense fake text makes the mockup harder to judge.
- Logos and brand marks — generate those separately if needed.
- Requests for pixel-exact measurements. The mockup settles composition and mood; exact
  values come from the written design language in the build phase.

## Example

```
prompt="Analytics dashboard landing for a logistics team. Top: slim nav with product mark
left, account cluster right. Below: a single wide KPI band with four metric tiles of equal
weight. Middle, dominant: a large area-chart panel on the left two-thirds, a ranked list
panel on the right third. Bottom: a dense data table with a quiet header row. Calm, data-first,
generous whitespace between bands. Signature element is the oversized chart panel with a soft
gradient underlay. Placeholder blocking only, no real numbers or labels.",
asset_type="interface_mockup",
platform="web",
brand_palette="ink #12181F, surface #FAFBFC, line #E3E8EE, accent teal #0FB5AE, warning amber #F5A623",
visual_style="quiet data product, restrained, generous whitespace, one soft gradient accent",
composition="three stacked bands: KPI row, chart+list split, data table; left-weighted",
content_density="airy",
text_policy="minimal_text",
size="1536x1024",
quality="high"
```

## Iterating

When a mockup misses, change the design language and note the delta, rather than nudging
adjectives blindly. Common fixes:

- Layout wrong → tighten the section-order description; it is doing the heavy lifting.
- Too busy → drop to `content_density=airy` and cut regions from the prompt.
- Off-brand color → make the palette names explicit and repeat the accent's role.
- Reads generic → strengthen the signature element and remove one competing feature.
