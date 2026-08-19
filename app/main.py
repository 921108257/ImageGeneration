import io
import logging
import traceback
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from openai import APIConnectionError, APIError, AsyncOpenAI, BadRequestError, RateLimitError

from .config import Settings, get_settings
from .image_service import detect_image_mime, edit_images, generate_images, named_image
from .mcp_server import mcp_http_app
from .openai_client import get_client
from .schemas import (
    GenerateRequest,
    ImageBackground,
    ImageOutputFormat,
    ImageQuality,
    ImageResponse,
    InputFidelity,
)
from .security import RequestGuardMiddleware

logger = logging.getLogger("image_api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with mcp_http_app.router.lifespan_context(mcp_http_app):
        yield


app = FastAPI(
    title="GPT Image 2 图像生成服务",
    description=(
        "面向界面资源生成的 OpenAI Images API 与 MCP 服务。\n\n"
        "- REST 生成：`POST /v1/images/generate`\n"
        "- REST 多图编辑：`POST /v1/images/edit`\n"
        "- MCP Streamable HTTP：`POST /mcp`"
    ),
    version="2.0.0",
    lifespan=lifespan,
)
app.add_middleware(RequestGuardMiddleware)


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value if value and value != "string" else None


def _extract_upstream_info(exc: Exception) -> dict:
    info: dict = {"exception_type": type(exc).__name__}
    for attribute in ("status_code", "code", "message", "request_id", "type", "param"):
        value = getattr(exc, attribute, None)
        if value is not None:
            info[attribute] = value
    body = getattr(exc, "body", None)
    if body is not None:
        info["body"] = body
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            info["response_text"] = response.text[:2000]
            info["response_headers"] = {
                key: response.headers[key]
                for key in ("x-request-id", "openai-processing-ms", "retry-after")
                if key in response.headers
            }
        except Exception:
            pass
    return info


def _map_openai_error(exc: Exception, model: str | None = None) -> HTTPException:
    info = _extract_upstream_info(exc)
    logger.error("上游 API 调用失败: %s\n%s", info, traceback.format_exc())
    detail = {"message": getattr(exc, "message", None) or str(exc), "upstream": info}

    upstream_code = None
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            upstream_code = error.get("code")
        upstream_code = upstream_code or body.get("code")
    if upstream_code == "model_not_found":
        model_description = f"模型 '{model}'" if model else "请求的模型"
        detail["message"] = f"上游不可用：{model_description} 未授权、未开通或没有可用渠道。"
        return HTTPException(status_code=404, detail=detail)
    if isinstance(exc, BadRequestError):
        return HTTPException(status_code=400, detail=detail)
    if isinstance(exc, RateLimitError):
        return HTTPException(status_code=429, detail=detail)
    if isinstance(exc, APIConnectionError):
        return HTTPException(status_code=502, detail=detail)
    if isinstance(exc, APIError):
        upstream_status = getattr(exc, "status_code", None)
        code = upstream_status if isinstance(upstream_status, int) and 400 <= upstream_status < 600 else 502
        return HTTPException(status_code=code, detail=detail)
    return HTTPException(status_code=500, detail=detail)


async def _read_upload(upload: UploadFile, limit: int, index: int) -> io.BytesIO:
    data = await upload.read(limit + 1)
    if not data:
        raise HTTPException(status_code=400, detail=f"第 {index} 个上传文件为空")
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"第 {index} 个上传文件超过 {limit} 字节限制")
    if detect_image_mime(data) is None:
        raise HTTPException(status_code=415, detail=f"第 {index} 个上传文件不是 PNG、JPEG 或 WebP")
    return named_image(data, index)


@app.get("/", summary="服务信息")
async def index() -> dict:
    return {"docs": "/docs", "health": "/health", "mcp": "/mcp"}


@app.get("/health", summary="健康检查")
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    return {
        "status": "ok",
        "model": settings.image_model,
        "mcp_endpoint": "/mcp",
        "authentication_enabled": bool(settings.service_api_key),
    }


@app.post(
    "/v1/images/generate",
    response_model=ImageResponse,
    summary="文本生成图片",
    description=(
        "调用 OpenAI Images API 生成图片。gpt-image-2 支持边长为 16 倍数的 WIDTHxHEIGHT；"
        "该模型不支持 transparent 背景。"
    ),
)
async def generate_image(
    body: GenerateRequest,
    client: Annotated[AsyncOpenAI, Depends(get_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImageResponse:
    model = body.model or settings.image_model
    try:
        return await generate_images(client, settings, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise _map_openai_error(exc, model) from exc


@app.post(
    "/v1/images/edit",
    response_model=ImageResponse,
    summary="多参考图编辑",
    description="上传最多 16 张 PNG/JPEG/WebP 参考图；mask 必须是小于 4MB 的 PNG。",
)
async def edit_image(
    prompt: Annotated[str, Form(min_length=1, max_length=32000, description="文本提示词")],
    image: Annotated[list[UploadFile], File(description="1-16 张参考图，重复使用 image 字段")],
    client: Annotated[AsyncOpenAI, Depends(get_client)],
    settings: Annotated[Settings, Depends(get_settings)],
    mask: Annotated[UploadFile | None, File(description="可选 PNG 蒙版")] = None,
    n: Annotated[int, Form(ge=1, le=10)] = 1,
    size: Annotated[str, Form(description="auto 或 WIDTHxHEIGHT")] = "auto",
    quality: Annotated[ImageQuality, Form()] = "auto",
    background: Annotated[ImageBackground | None, Form()] = None,
    output_format: Annotated[ImageOutputFormat | None, Form()] = None,
    output_compression: Annotated[int | None, Form(ge=0, le=100)] = None,
    input_fidelity: Annotated[InputFidelity | None, Form()] = None,
    user: Annotated[str | None, Form(max_length=256)] = None,
    model: Annotated[str | None, Form()] = None,
) -> ImageResponse:
    if not 1 <= len(image) <= 16:
        raise HTTPException(status_code=400, detail="image 必须包含 1 到 16 张参考图")

    image_buffers: list[io.BytesIO] = []
    total = 0
    for index, upload in enumerate(image, start=1):
        buffer = await _read_upload(upload, settings.max_upload_bytes, index)
        total += buffer.getbuffer().nbytes
        if total > settings.max_upload_total_bytes:
            raise HTTPException(status_code=413, detail="参考图总大小超过服务限制")
        image_buffers.append(buffer)

    mask_buffer = None
    if mask is not None:
        mask_buffer = await _read_upload(mask, settings.max_mask_bytes, 1)
        if not mask_buffer.name.endswith(".png"):
            raise HTTPException(status_code=415, detail="mask 必须是 PNG 图片")

    resolved_model = _normalize_optional(model) or settings.image_model
    try:
        return await edit_images(
            client,
            settings,
            prompt=prompt,
            images=image_buffers,
            mask=mask_buffer,
            n=n,
            size=size,
            quality=quality,
            background=background,
            output_format=output_format,
            output_compression=output_compression,
            input_fidelity=input_fidelity,
            user=_normalize_optional(user),
            model=resolved_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise _map_openai_error(exc, resolved_model) from exc


# Mount last so FastAPI's REST, docs, and health routes win before the MCP ASGI app.
app.mount("/", mcp_http_app)
