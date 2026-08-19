import re
from typing import Any, Literal

from pydantic import BaseModel, Field


ImageQuality = Literal["auto", "low", "medium", "high", "standard", "hd"]
ImageBackground = Literal["auto", "transparent", "opaque"]
ImageOutputFormat = Literal["png", "jpeg", "webp"]
ImageModeration = Literal["auto", "low"]
InputFidelity = Literal["low", "high"]

_SIZE_PATTERN = re.compile(r"^([1-9]\d{0,4})x([1-9]\d{0,4})$")
_GPT_IMAGE_2_MODELS = {"gpt-image-2", "gpt-image-2-2026-04-21"}
_GPT_IMAGE_SIZES = {"auto", "1024x1024", "1536x1024", "1024x1536"}
_DALLE_2_SIZES = {"256x256", "512x512", "1024x1024"}
_DALLE_3_SIZES = {"1024x1024", "1792x1024", "1024x1792"}


def is_gpt_image_model(model: str) -> bool:
    return model.startswith("gpt-image-") or model == "chatgpt-image-latest"


def is_gpt_image_2_model(model: str) -> bool:
    return model in _GPT_IMAGE_2_MODELS


def validate_size(size: str, model: str) -> str:
    if size == "auto":
        if model in {"dall-e-2", "dall-e-3"}:
            raise ValueError(f"{model} 不支持 size=auto")
        return size

    match = _SIZE_PATTERN.fullmatch(size)
    if not match:
        raise ValueError("size 应为 auto 或 WIDTHxHEIGHT，例如 1536x864")

    if is_gpt_image_2_model(model):
        width, height = map(int, match.groups())
        short_edge, long_edge = sorted((width, height))
        ratio = width / height
        if width % 16 or height % 16:
            raise ValueError("gpt-image-2 的宽和高都必须是 16 的倍数")
        if not 1 / 3 <= ratio <= 3:
            raise ValueError("gpt-image-2 的宽高比必须在 1:3 到 3:1 之间")
        if long_edge > 3840 or short_edge > 2160 or width * height > 3840 * 2160:
            raise ValueError("gpt-image-2 的尺寸不能超过 3840x2160 对应的边长和像素上限")
        return size

    allowed = None
    if model == "dall-e-2":
        allowed = _DALLE_2_SIZES
    elif model == "dall-e-3":
        allowed = _DALLE_3_SIZES
    elif is_gpt_image_model(model):
        allowed = _GPT_IMAGE_SIZES
    if allowed is not None and size not in allowed:
        raise ValueError(f"{model} 的 size 仅支持: {', '.join(sorted(allowed))}")

    # Unknown model names are commonly used by OpenAI-compatible gateways.
    width, height = map(int, match.groups())
    if not (64 <= width <= 4096 and 64 <= height <= 4096):
        raise ValueError("兼容模型的宽和高必须在 64 到 4096 之间")
    return size


def validate_image_options(
    *,
    model: str,
    prompt: str,
    n: int,
    size: str,
    quality: ImageQuality,
    background: ImageBackground | None,
    output_format: ImageOutputFormat | None,
    output_compression: int | None,
    moderation: ImageModeration | None,
    editing: bool = False,
    input_fidelity: InputFidelity | None = None,
) -> None:
    prompt_limit = 1000 if model == "dall-e-2" else 4000 if model == "dall-e-3" else 32000
    if not prompt.strip():
        raise ValueError("prompt 不能为空")
    if len(prompt) > prompt_limit:
        raise ValueError(f"{model} 的 prompt 最长为 {prompt_limit} 个字符")
    if model == "dall-e-3" and n != 1:
        raise ValueError("dall-e-3 仅支持 n=1")
    if editing and model == "dall-e-3":
        raise ValueError("dall-e-3 不支持 Images API 编辑接口")

    validate_size(size, model)

    if is_gpt_image_model(model):
        if quality not in {"auto", "low", "medium", "high"}:
            raise ValueError("GPT Image 模型的 quality 仅支持 auto/low/medium/high")
    elif model == "dall-e-3" and quality not in {"auto", "standard", "hd"}:
        raise ValueError("dall-e-3 的 quality 仅支持 standard/hd")
    elif model == "dall-e-2" and quality not in {"auto", "standard"}:
        raise ValueError("dall-e-2 的 quality 仅支持 standard")

    if is_gpt_image_2_model(model) and background == "transparent":
        raise ValueError(
            "gpt-image-2 不支持透明背景；请使用 opaque/auto，或改用支持透明背景的 GPT Image 模型"
        )
    if background == "transparent" and output_format == "jpeg":
        raise ValueError("透明背景仅能与 png 或 webp 输出格式一起使用")
    if output_compression is not None and output_format not in {"jpeg", "webp"}:
        raise ValueError("output_compression 仅适用于 jpeg 或 webp")
    if moderation is not None and not is_gpt_image_model(model):
        raise ValueError("moderation 仅适用于 GPT Image 模型")
    if input_fidelity is not None and not is_gpt_image_model(model):
        raise ValueError("input_fidelity 仅适用于 GPT Image 编辑")


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=32000, description="文本提示词")
    n: int = Field(1, ge=1, le=10, description="生成图片数量")
    size: str = Field("auto", description="auto 或 WIDTHxHEIGHT；gpt-image-2 的边长须为 16 的倍数")
    quality: ImageQuality = Field("auto", description="图片质量")
    background: ImageBackground | None = Field(None, description="背景类型")
    output_format: ImageOutputFormat | None = Field(None, description="GPT Image 输出格式")
    output_compression: int | None = Field(None, ge=0, le=100, description="JPEG/WebP 压缩级别")
    moderation: ImageModeration | None = Field(None, description="GPT Image 内容审核级别")
    user: str | None = Field(None, max_length=256, description="稳定的终端用户标识")
    style: Literal["vivid", "natural"] | None = Field(None, description="仅用于 dall-e-3")
    model: str | None = Field(None, min_length=1, description="覆盖默认图像模型")


class ImageItem(BaseModel):
    b64_json: str | None = Field(None, description="Base64 编码的图片数据")
    url: str | None = Field(None, description="图片 URL")
    mime_type: str | None = Field(None, description="图片 MIME 类型")
    revised_prompt: str | None = Field(None, description="模型改写后的提示词")


class ImageResponse(BaseModel):
    model: str = Field(..., description="实际使用的模型名称")
    created: int = Field(..., description="生成时间戳（Unix 秒）")
    images: list[ImageItem] = Field(..., description="生成的图片列表")
    background: str | None = None
    output_format: str | None = None
    quality: str | None = None
    size: str | None = None
    usage: dict[str, Any] | None = Field(None, description="上游返回的 token 使用量")
