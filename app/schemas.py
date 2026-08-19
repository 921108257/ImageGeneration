import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator


ImageQuality = Literal["auto", "low", "medium", "high", "standard", "hd"]
ImageBackground = Literal["auto", "transparent", "opaque"]

_SIZE_PATTERN = re.compile(r"^\d{2,5}x\d{2,5}$")


def _validate_size(v: str) -> str:
    if v == "auto":
        return v
    if not _SIZE_PATTERN.match(v):
        raise ValueError("分辨率格式无效，应为 'auto' 或 '宽x高'，例如 '1024x1024'")
    w, h = (int(x) for x in v.split("x"))
    if not (64 <= w <= 4096 and 64 <= h <= 4096):
        raise ValueError("分辨率的宽和高必须在 64 到 4096 之间")
    return v


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000, description="文本提示词")
    n: int = Field(1, ge=1, le=10, description="生成图片数量")
    size: str = Field("auto", description="图片分辨率，'auto' 或 '宽x高'，例如 '1024x1024'、'1280x720'")
    quality: ImageQuality = Field("auto", description="图片质量")
    background: ImageBackground | None = Field(None, description="背景类型")
    model: str | None = Field(None, description="覆盖默认图像模型")

    @field_validator("size")
    @classmethod
    def _check_size(cls, v: str) -> str:
        return _validate_size(v)


class ImageItem(BaseModel):
    b64_json: str | None = Field(None, description="Base64 编码的图片数据")
    url: str | None = Field(None, description="图片 URL（仅部分模型返回）")
    revised_prompt: str | None = Field(None, description="模型改写后的提示词")


class ImageResponse(BaseModel):
    model: str = Field(..., description="实际使用的模型名称")
    created: int = Field(..., description="生成时间戳（Unix 秒）")
    images: list[ImageItem] = Field(..., description="生成的图片列表")
