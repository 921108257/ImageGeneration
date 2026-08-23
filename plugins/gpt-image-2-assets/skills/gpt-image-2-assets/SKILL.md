---
name: gpt-image-2-assets
description: Generate and integrate polished frontend bitmap assets through the GPT Image 2 Assets MCP tools. Use for UI backgrounds, illustrations, icon families, product mockups, textures, and coherent visual systems; do not use for generic image brainstorming.
metadata:
  short-description: Generate professional UI assets for frontend work
---

# GPT Image 2 Assets

Use the `generate_ui_asset` MCP tool for new assets and `edit_ui_asset` for reference-driven edits. The service supports local MCP at `http://127.0.0.1:8000/mcp` and hosted Streamable HTTP endpoints.

## Workflow

1. Inspect the target frontend stack, existing design tokens, image dimensions, and where the asset will be integrated.
2. Choose `asset_type`, `platform`, `content_density`, and `text_policy`. Prefer `text_policy=no_text` for decorative assets.
3. Describe the user, product context, focal subject, composition, material, lighting, edge treatment, palette, and quiet space required by the UI. The default `prompt_profile=ui_pro` expands a short brief into a principal-designer prompt.
4. Use `gpt-image-2` by default. Use `qwen-image-2.0-pro` when accurate Chinese text or native DashScope image generation is required, and Seedream when the configured Ark endpoint is preferred.
5. Save returned URLs into the project immediately. Do not leave temporary provider URLs as runtime dependencies.
6. For icon families, generate one consistent sheet, remove any backing with `rembg`, verify RGBA alpha, then split with the bundled `ui-ux-asset-pipeline` helper when available.
7. Integrate with the target framework's native image API, reserve layout space, lazy-load non-critical imagery, and add meaningful alt/content descriptions. Decorative art beside visible copy is hidden from assistive technology.
8. Check 375px, 768px, 1024px, and 1440px layouts; preserve readable contrast, visible focus, and reduced-motion behavior in the host UI.

## Model and size rules

- `gpt-image-2` accepts custom dimensions whose edges are multiples of 16 and rejects transparent backgrounds.
- If a configured `OPENAI_API_KEY_1K` or `GPT_IMAGE_2_1K_API_KEY` exists, explicit GPT Image 2 requests with both edges at or below `IMAGE_1K_MAX_EDGE` use it; otherwise the default OpenAI key is used.
- Qwen Image uses `QWEN_API_KEY`/`DASHSCOPE_API_KEY` and its native `WIDTH*HEIGHT` request shape. Its result URLs expire, so persist them.
- Seedream uses `SEEDREAM_API_KEY`/`VOLCENGINE_API_KEY` and the configured Ark OpenAI-compatible base URL.

## Prompt checklist

Include: asset role, platform, audience, focal subject, hierarchy, framing, negative space, palette, material, lighting, perspective, edge treatment, target aspect ratio, and explicit text policy. Avoid vague adjectives, invented UI copy, logos, watermarks, random gradients, and screenshots of interfaces when the output is meant to be a standalone asset.

For detailed provider limits, read [provider-matrix.md](references/provider-matrix.md).
