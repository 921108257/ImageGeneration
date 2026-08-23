from typing import Literal


PromptProfile = Literal["ui_pro", "raw"]
UIAssetType = Literal[
    "auto",
    "hero_background",
    "empty_state",
    "illustration",
    "icon",
    "logo",
    "texture",
    "product_mockup",
    "avatar",
    "pattern",
]
UIPlatform = Literal["web", "mobile", "desktop", "cross_platform"]
TextPolicy = Literal["no_text", "minimal_text", "exact_text"]
ContentDensity = Literal["airy", "balanced", "dense"]


def build_ui_prompt(
    prompt: str,
    *,
    profile: PromptProfile = "ui_pro",
    asset_type: UIAssetType = "auto",
    platform: UIPlatform = "web",
    visual_style: str | None = None,
    brand_palette: str | None = None,
    composition: str | None = None,
    content_density: ContentDensity = "balanced",
    text_policy: TextPolicy = "no_text",
) -> str:
    """Turn a short frontend brief into a production-oriented visual brief."""
    if profile == "raw":
        return prompt.strip()

    text_rule = {
        "no_text": "Do not render words, letters, logos, labels, UI chrome, or watermarks.",
        "minimal_text": "Use only the fewest legible words explicitly requested; never invent copy.",
        "exact_text": "Render requested text exactly and keep typography clean, legible, and intentional.",
    }[text_policy]
    style = visual_style or "quiet premium product design, restrained, contemporary, and brand-ready"
    palette = brand_palette or "a disciplined neutral palette with one controlled accent color"
    layout = composition or "clear focal hierarchy, deliberate negative space, balanced alignment, and a stable silhouette"
    asset = asset_type.replace("_", " ")
    platform_label = platform.replace("_", " ")

    return "\n".join(
        [
            "Act as a principal product designer, visual systems director, and senior UI asset art director.",
            f"Create one production-ready bitmap asset for a {platform_label} interface.",
            f"Asset role: {asset}.",
            f"Design brief: {prompt.strip()}",
            f"Visual direction: {style}.",
            f"Color direction: {palette}.",
            f"Composition: {layout}.",
            f"Content density: {content_density}; preserve breathing room around the focal subject.",
            "Use a coherent design system: consistent geometry, material language, lighting, edge treatment, and visual weight.",
            "Prioritize immediate comprehension, polished hierarchy, scalable composition, and clean integration beside real product UI.",
            text_rule,
            "Avoid generic stock-art styling, random decoration, clutter, inconsistent perspective, muddy contrast, banding, and accidental UI screenshots.",
            "Return only the visual asset; do not include an explanation or a frame around it.",
        ]
    )
