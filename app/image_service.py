import asyncio
import base64
import binascii
import io
import json
import time
from functools import lru_cache
from typing import Any

import httpx
from openai import AsyncOpenAI

from .config import Settings
from .openai_client import provider_for_model
from .oss_client import upload_image_bytes
from .schemas import (
    GenerateRequest,
    ImageItem,
    ImageResponse,
    is_gpt_image_model,
    is_qwen_model,
    is_seedream_model,
    validate_image_options,
)
from .ui_prompt import ContentDensity, PromptProfile, TextPolicy, UIAssetType, UIPlatform, build_ui_prompt


def detect_image_mime(data: bytes) -> str | None:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def image_extension(mime_type: str | None) -> str:
    return {"image/jpeg": "jpg", "image/webp": "webp"}.get(mime_type or "", "png")


def named_image(data: bytes, index: int = 1) -> io.BytesIO:
    mime_type = detect_image_mime(data)
    if mime_type is None:
        raise ValueError("仅支持 PNG、JPEG 和 WebP 图片")
    buffer = io.BytesIO(data)
    buffer.name = f"image-{index}.{image_extension(mime_type)}"
    return buffer


def decode_image_input(value: str, index: int, max_bytes: int) -> io.BytesIO:
    encoded = value.strip()
    declared_mime = None
    if encoded.startswith("data:"):
        header, separator, encoded = encoded.partition(",")
        if not separator or ";base64" not in header:
            raise ValueError(f"第 {index} 张图片必须使用 base64 data URL")
        declared_mime = header[5:].split(";", 1)[0].lower()
        if declared_mime not in {"image/png", "image/jpeg", "image/webp"}:
            raise ValueError(f"第 {index} 张图片的 MIME 类型不受支持")
    encoded = "".join(encoded.split())
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError(f"第 {index} 张图片不是有效的 base64") from exc
    if not data:
        raise ValueError(f"第 {index} 张图片为空")
    if len(data) > max_bytes:
        raise ValueError(f"第 {index} 张图片超过 {max_bytes} 字节限制")
    actual_mime = detect_image_mime(data)
    if actual_mime is None or declared_mime is not None and actual_mime != declared_mime:
        raise ValueError(f"第 {index} 张图片内容与声明的格式不匹配")
    return named_image(data, index)


def _normalize_result(result: Any) -> dict[str, Any]:
    if isinstance(result, str):
        value = result.strip()
        if not value:
            raise ValueError("上游返回了空响应")
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            if value.startswith(("http://", "https://", "data:")):
                return {"data": [value]}
            raise ValueError("上游返回了无法解析的非 JSON 响应")
    if isinstance(result, dict):
        return result
    if hasattr(result, "model_dump"):
        return result.model_dump(exclude_none=True)
    return {"created": getattr(result, "created", None), "data": getattr(result, "data", None)}


def _extract_data_url(value: str) -> tuple[str | None, str | None]:
    if not value.startswith("data:"):
        return None, None
    header, separator, encoded = value.partition(",")
    if not separator or ";base64" not in header:
        return None, None
    return encoded, header[5:].split(";", 1)[0]


def _mime_from_base64(value: str, fallback: str | None) -> str | None:
    try:
        head = base64.b64decode(value[:48] + "===", validate=False)
    except (ValueError, binascii.Error):
        return fallback
    return detect_image_mime(head) or fallback


async def to_image_response(
    model: str,
    result: Any,
    settings: Settings,
    requested_format: str | None = None,
    prompt_profile: str = "raw",
) -> ImageResponse:
    payload = _normalize_result(result)
    data = payload.get("data")
    if data is None:
        for key in ("images", "output", "urls", "items"):
            if payload.get(key) is not None:
                data = payload[key]
                break
    if data is None:
        for key in ("url", "image", "result"):
            if isinstance(payload.get(key), str):
                data = [payload[key]]
                break
    if data is None:
        raise ValueError("上游响应中未找到图片数据")
    if isinstance(data, str):
        data = [data]

    fallback_mime = {
        "png": "image/png",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
    }.get(payload.get("output_format") or requested_format)
    images: list[ImageItem] = []
    for item in data:
        if isinstance(item, str):
            b64_value, data_mime = _extract_data_url(item)
            item = (
                {"b64_json": b64_value, "mime_type": data_mime}
                if b64_value is not None
                else {"url": item}
                if item.startswith(("http://", "https://"))
                else {"b64_json": item}
            )
        elif hasattr(item, "model_dump"):
            item = item.model_dump(exclude_none=True)
        if not isinstance(item, dict):
            raise ValueError("上游返回了不支持的图片数据结构")

        b64_json = item.get("b64_json")
        url = item.get("url") or item.get("image") or item.get("image_url")
        mime_type = item.get("mime_type") or (
            _mime_from_base64(b64_json, fallback_mime) if b64_json else fallback_mime
        )
        if not b64_json and not url:
            raise ValueError("上游图片项既没有 b64_json 也没有 url")

        if b64_json and settings.oss_enabled:
            try:
                raw = base64.b64decode(b64_json, validate=True)
            except (ValueError, binascii.Error):
                raw = b""
            if raw:
                oss_url = await asyncio.to_thread(upload_image_bytes, raw, model)
                if oss_url:
                    url, b64_json = oss_url, None

        images.append(
            ImageItem(
                b64_json=b64_json,
                url=url,
                mime_type=mime_type,
                revised_prompt=item.get("revised_prompt"),
            )
        )

    usage = payload.get("usage")
    if hasattr(usage, "model_dump"):
        usage = usage.model_dump(exclude_none=True)
    return ImageResponse(
        model=model,
        provider=provider_for_model(model, settings),
        prompt_profile=prompt_profile,
        created=payload.get("created") or int(time.time()),
        images=images,
        background=payload.get("background"),
        output_format=payload.get("output_format") or requested_format,
        quality=payload.get("quality"),
        size=payload.get("size"),
        usage=usage if isinstance(usage, dict) else None,
    )


@lru_cache
def _generation_slots(limit: int) -> asyncio.Semaphore:
    return asyncio.Semaphore(limit)


async def generate_images(
    client: AsyncOpenAI,
    settings: Settings,
    request: GenerateRequest,
) -> ImageResponse:
    model = request.model or settings.image_model
    effective_prompt = build_ui_prompt(
        request.prompt,
        profile=request.prompt_profile,
        asset_type=request.asset_type,
        platform=request.platform,
        visual_style=request.visual_style,
        brand_palette=request.brand_palette,
        composition=request.composition,
        content_density=request.content_density,
        text_policy=request.text_policy,
    )
    validate_image_options(
        model=model,
        prompt=effective_prompt,
        n=request.n,
        size=request.size,
        quality=request.quality,
        background=request.background,
        output_format=request.output_format,
        output_compression=request.output_compression,
        moderation=request.moderation,
    )

    kwargs: dict[str, Any] = {
        "model": model,
        "prompt": effective_prompt,
        "n": request.n,
    }
    if request.size != "auto" or is_gpt_image_model(model):
        kwargs["size"] = request.size
    if request.user:
        kwargs["user"] = request.user
    if is_qwen_model(model):
        result = await _generate_qwen(settings, request, effective_prompt)
    elif is_gpt_image_model(model):
        kwargs["quality"] = request.quality
        for name in ("background", "output_format", "output_compression", "moderation"):
            value = getattr(request, name)
            if value is not None:
                kwargs[name] = value
    elif is_seedream_model(model):
        kwargs["response_format"] = "url"
        extra_body = {
            key: value
            for key, value in (("seed", request.seed), ("watermark", request.watermark))
            if value is not None
        }
        if extra_body:
            kwargs["extra_body"] = extra_body
        async with _generation_slots(settings.max_concurrent_generations):
            result = await client.images.generate(**kwargs)
    else:
        if request.quality != "auto":
            kwargs["quality"] = request.quality
        kwargs["response_format"] = "b64_json"
        if model == "dall-e-3" and request.style:
            kwargs["style"] = request.style

        if request.seed is not None or request.negative_prompt is not None:
            kwargs["extra_body"] = {
                key: value
                for key, value in (("seed", request.seed), ("negative_prompt", request.negative_prompt))
                if value is not None
            }
        async with _generation_slots(settings.max_concurrent_generations):
            result = await client.images.generate(**kwargs)
    if is_gpt_image_model(model):
        async with _generation_slots(settings.max_concurrent_generations):
            result = await client.images.generate(**kwargs)
    return await to_image_response(model, result, settings, request.output_format, request.prompt_profile)


async def _generate_qwen(settings: Settings, request: GenerateRequest, prompt: str) -> dict[str, Any]:
    if not settings.qwen_api_key:
        raise ValueError("未配置 QWEN_API_KEY 或 DASHSCOPE_API_KEY")
    parameters: dict[str, Any] = {
        "n": request.n,
        "prompt_extend": request.prompt_extend if request.prompt_extend is not None else False,
        "watermark": request.watermark if request.watermark is not None else False,
    }
    if request.size != "auto":
        parameters["size"] = request.size.replace("x", "*")
    for key in ("negative_prompt", "seed"):
        value = getattr(request, key)
        if value is not None:
            parameters[key] = value
    payload = {
        "model": request.model or settings.image_model,
        "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
        "parameters": parameters,
    }
    async with _generation_slots(settings.max_concurrent_generations):
        async with httpx.AsyncClient(timeout=settings.request_timeout) as http:
            response = await http.post(
                settings.qwen_base_url,
                headers={"Authorization": f"Bearer {settings.qwen_api_key}"},
                json=payload,
            )
            response.raise_for_status()
    body = response.json()
    images = []
    for choice in body.get("output", {}).get("choices", []):
        for content in choice.get("message", {}).get("content", []):
            if content.get("image"):
                images.append({"url": content["image"], "revised_prompt": content.get("actual_prompt")})
    if not images:
        raise ValueError("Qwen 上游响应中未找到图片数据")
    return {"data": images, "usage": body.get("usage"), "size": request.size}


async def edit_images(
    client: AsyncOpenAI,
    settings: Settings,
    *,
    prompt: str,
    images: list[io.BytesIO],
    mask: io.BytesIO | None,
    n: int,
    size: str,
    quality: str,
    background: str | None,
    output_format: str | None,
    output_compression: int | None,
    input_fidelity: str | None,
    user: str | None,
    model: str | None,
    prompt_profile: PromptProfile = "ui_pro",
    asset_type: UIAssetType = "auto",
    platform: UIPlatform = "web",
    visual_style: str | None = None,
    brand_palette: str | None = None,
    composition: str | None = None,
    content_density: ContentDensity = "balanced",
    text_policy: TextPolicy = "no_text",
) -> ImageResponse:
    resolved_model = model or settings.image_model
    if is_qwen_model(resolved_model) or is_seedream_model(resolved_model):
        raise ValueError(f"{resolved_model} 当前仅支持生成，不支持此编辑接口")
    effective_prompt = build_ui_prompt(
        prompt,
        profile=prompt_profile,
        asset_type=asset_type,
        platform=platform,
        visual_style=visual_style,
        brand_palette=brand_palette,
        composition=composition,
        content_density=content_density,
        text_policy=text_policy,
    )
    validate_image_options(
        model=resolved_model,
        prompt=effective_prompt,
        n=n,
        size=size,
        quality=quality,  # type: ignore[arg-type]
        background=background,  # type: ignore[arg-type]
        output_format=output_format,  # type: ignore[arg-type]
        output_compression=output_compression,
        moderation=None,
        editing=True,
        input_fidelity=input_fidelity,  # type: ignore[arg-type]
    )
    if not images:
        raise ValueError("至少需要一张参考图")
    if len(images) > 16:
        raise ValueError("GPT Image 编辑最多支持 16 张参考图")

    kwargs: dict[str, Any] = {
        "model": resolved_model,
        "prompt": effective_prompt,
        "image": images if len(images) > 1 else images[0],
        "n": n,
        "size": size,
    }
    if mask is not None:
        kwargs["mask"] = mask
    if user:
        kwargs["user"] = user
    if is_gpt_image_model(resolved_model):
        kwargs["quality"] = quality
        for name, value in (
            ("background", background),
            ("output_format", output_format),
            ("output_compression", output_compression),
            ("input_fidelity", input_fidelity),
        ):
            if value is not None:
                kwargs[name] = value
    else:
        if quality != "auto":
            kwargs["quality"] = quality
        kwargs["response_format"] = "b64_json"

    async with _generation_slots(settings.max_concurrent_generations):
        result = await client.images.edit(**kwargs)
    return await to_image_response(resolved_model, result, settings, output_format, prompt_profile)
