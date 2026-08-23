import json
from typing import Annotated, Literal

from mcp import types
from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.transport_security import TransportSecuritySettings
from openai import APIError
from pydantic import Field, ValidationError

from .config import get_settings
from .image_service import decode_image_input, edit_images, generate_images
from .openai_client import configured_models, get_client
from .schemas import GenerateRequest, ImageResponse


settings = get_settings()
mcp = MCPServer(
    name="gpt-image-2-assets",
    title="Professional UI Image Assets",
    description="Generate production-ready interface assets with GPT Image 2, Qwen Image, or Seedream.",
    instructions=(
        "Use list_ui_models before choosing a non-default provider. Use prompt_profile=ui_pro for "
        "production UI assets and raw only when the caller already supplies a complete art-direction brief. "
        "GPT Image 2 does not support transparent backgrounds. Save provider URLs into the target project."
    ),
    version="3.0.0",
)

_TOOL_ANNOTATIONS = types.ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
)


@mcp.tool(
    name="list_ui_models",
    title="List UI image models",
    description="List configured image providers and models without making an upstream request.",
    annotations=types.ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
    structured_output=False,
)
async def list_ui_models() -> types.CallToolResult:
    payload = {
        "models": configured_models(settings),
        "small_image_key_enabled": bool(settings.openai_api_key_1k),
    }
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
        structuredContent=payload,
        isError=False,
    )


def _result_metadata(response: ImageResponse) -> dict:
    return {
        "model": response.model,
        "provider": response.provider,
        "prompt_profile": response.prompt_profile,
        "created": response.created,
        "background": response.background,
        "output_format": response.output_format,
        "quality": response.quality,
        "size": response.size,
        "usage": response.usage,
        "images": [
            {
                "index": index,
                "url": image.url,
                "mime_type": image.mime_type,
                "revised_prompt": image.revised_prompt,
                "embedded": image.b64_json is not None,
            }
            for index, image in enumerate(response.images, start=1)
        ],
    }


def _tool_result(response: ImageResponse) -> types.CallToolResult:
    metadata = _result_metadata(response)
    content: list[types.ContentBlock] = [
        types.TextContent(type="text", text=json.dumps(metadata, ensure_ascii=False))
    ]
    for index, image in enumerate(response.images, start=1):
        if image.b64_json:
            content.append(
                types.ImageContent(
                    type="image",
                    data=image.b64_json,
                    mimeType=image.mime_type or "image/png",
                )
            )
        elif image.url:
            extension = "jpg" if image.mime_type == "image/jpeg" else (image.mime_type or "image/png").split("/")[-1]
            content.append(
                types.ResourceLink(
                    type="resource_link",
                    uri=image.url,
                    name=f"generated-{index}.{extension}",
                    mimeType=image.mime_type,
                    description="Generated image asset",
                )
            )
    return types.CallToolResult(content=content, structuredContent=metadata, isError=False)


def _tool_error(exc: Exception) -> types.CallToolResult:
    if isinstance(exc, APIError):
        status_code = getattr(exc, "status_code", None)
        code = getattr(exc, "code", None)
        prefix = f"OpenAI API 错误{f' ({status_code})' if status_code else ''}"
        message = getattr(exc, "message", None) or str(exc)
        text = f"{prefix}: {message}{f' [code={code}]' if code else ''}"
    else:
        text = str(exc)
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)],
        structuredContent={"error": text},
        isError=True,
    )


@mcp.tool(
    name="generate_ui_asset",
    title="Generate UI asset",
    description=(
        "Generate one or more production-ready interface assets with professional UI prompt expansion. "
        "Supports configured GPT Image 2, Qwen Image, and Seedream providers."
    ),
    annotations=_TOOL_ANNOTATIONS,
    structured_output=False,
)
async def generate_ui_asset(
    ctx: Context,
    prompt: Annotated[str, Field(min_length=1, max_length=32000)],
    n: Annotated[int, Field(ge=1, le=10)] = 1,
    size: str = "auto",
    quality: Literal["auto", "low", "medium", "high"] = "auto",
    background: Literal["auto", "transparent", "opaque"] | None = None,
    output_format: Literal["png", "jpeg", "webp"] = "png",
    output_compression: Annotated[int | None, Field(ge=0, le=100)] = None,
    moderation: Literal["auto", "low"] | None = None,
    user: Annotated[str | None, Field(max_length=256)] = None,
    model: str | None = None,
    prompt_profile: Literal["ui_pro", "raw"] = "ui_pro",
    asset_type: Literal["auto", "hero_background", "empty_state", "illustration", "icon", "logo", "texture", "product_mockup", "avatar", "pattern"] = "auto",
    platform: Literal["web", "mobile", "desktop", "cross_platform"] = "web",
    visual_style: str | None = None,
    brand_palette: str | None = None,
    composition: str | None = None,
    content_density: Literal["airy", "balanced", "dense"] = "balanced",
    text_policy: Literal["no_text", "minimal_text", "exact_text"] = "no_text",
    negative_prompt: str | None = None,
    prompt_extend: bool | None = None,
    watermark: bool | None = None,
    seed: Annotated[int | None, Field(ge=0, le=2147483647)] = None,
) -> types.CallToolResult:
    await ctx.report_progress(0.05, 1, "正在提交图像生成请求")
    try:
        request = GenerateRequest(
            prompt=prompt,
            n=n,
            size=size,
            quality=quality,
            background=background,
            output_format=output_format,
            output_compression=output_compression,
            moderation=moderation,
            user=user,
            model=model,
            prompt_profile=prompt_profile,
            asset_type=asset_type,
            platform=platform,
            visual_style=visual_style,
            brand_palette=brand_palette,
            composition=composition,
            content_density=content_density,
            text_policy=text_policy,
            negative_prompt=negative_prompt,
            prompt_extend=prompt_extend,
            watermark=watermark,
            seed=seed,
        )
        resolved_model = request.model or settings.image_model
        response = await generate_images(get_client(resolved_model, request.size), settings, request)
    except Exception as exc:
        return _tool_error(exc)
    await ctx.report_progress(1, 1, "图像生成完成")
    return _tool_result(response)


@mcp.tool(
    name="edit_ui_asset",
    title="Edit UI asset",
    description=(
        "Edit or combine up to 16 PNG, JPEG, or WebP references. Supply each image as raw base64 "
        "or a data:image/...;base64 URL; remote URLs and server file paths are intentionally rejected."
    ),
    annotations=_TOOL_ANNOTATIONS,
    structured_output=False,
)
async def edit_ui_asset(
    ctx: Context,
    prompt: Annotated[str, Field(min_length=1, max_length=32000)],
    images: Annotated[list[str], Field(min_length=1, max_length=16)],
    mask: str | None = None,
    n: Annotated[int, Field(ge=1, le=10)] = 1,
    size: str = "auto",
    quality: Literal["auto", "low", "medium", "high"] = "auto",
    background: Literal["auto", "transparent", "opaque"] | None = None,
    output_format: Literal["png", "jpeg", "webp"] = "png",
    output_compression: Annotated[int | None, Field(ge=0, le=100)] = None,
    input_fidelity: Literal["low", "high"] | None = None,
    user: Annotated[str | None, Field(max_length=256)] = None,
    model: str | None = None,
    prompt_profile: Literal["ui_pro", "raw"] = "ui_pro",
    asset_type: Literal["auto", "hero_background", "empty_state", "illustration", "icon", "logo", "texture", "product_mockup", "avatar", "pattern"] = "auto",
    platform: Literal["web", "mobile", "desktop", "cross_platform"] = "web",
    visual_style: str | None = None,
    brand_palette: str | None = None,
    composition: str | None = None,
    content_density: Literal["airy", "balanced", "dense"] = "balanced",
    text_policy: Literal["no_text", "minimal_text", "exact_text"] = "no_text",
) -> types.CallToolResult:
    await ctx.report_progress(0.05, 1, "正在校验参考图")
    try:
        decoded = [decode_image_input(value, index, settings.max_upload_bytes) for index, value in enumerate(images, 1)]
        if sum(buffer.getbuffer().nbytes for buffer in decoded) > settings.max_upload_total_bytes:
            raise ValueError("参考图总大小超过服务限制")
        decoded_mask = decode_image_input(mask, 1, settings.max_mask_bytes) if mask else None
        if decoded_mask is not None and not decoded_mask.name.endswith(".png"):
            raise ValueError("mask 必须是 PNG 图片")
        response = await edit_images(
            get_client(model or settings.image_model, size),
            settings,
            prompt=prompt,
            images=decoded,
            mask=decoded_mask,
            n=n,
            size=size,
            quality=quality,
            background=background,
            output_format=output_format,
            output_compression=output_compression,
            input_fidelity=input_fidelity,
            user=user,
            model=model,
            prompt_profile=prompt_profile,
            asset_type=asset_type,
            platform=platform,
            visual_style=visual_style,
            brand_palette=brand_palette,
            composition=composition,
            content_density=content_density,
            text_policy=text_policy,
        )
    except Exception as exc:
        return _tool_error(exc)
    await ctx.report_progress(1, 1, "图像编辑完成")
    return _tool_result(response)


transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=settings.mcp_dns_rebinding_protection,
    allowed_hosts=settings.allowed_mcp_hosts(),
    allowed_origins=settings.allowed_mcp_origins(),
)
mcp_http_app = mcp.streamable_http_app(
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
    max_request_body_size=settings.mcp_max_request_body_bytes,
    transport_security=transport_security,
)
