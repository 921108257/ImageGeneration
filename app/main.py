import asyncio
import base64
import io
import json
import logging
import traceback
from typing import Annotated

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError, BadRequestError

logger = logging.getLogger("image_api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from .config import Settings, get_settings
from .openai_client import get_client
from .oss_client import upload_image_bytes
from .schemas import (
    GenerateRequest,
    ImageResponse,
    ImageItem,
    ImageQuality,
    _validate_size,
)

app = FastAPI(
    title="OpenAI 图像生成 API",
    description=(
        "基于 FastAPI 封装 OpenAI 图像模型的 REST 服务，支持：\n\n"
        "- **文本生成图片**：`POST /v1/images/generate`\n"
        "- **文本 + 参考图生成图片**：`POST /v1/images/edit`（multipart 上传）\n\n"
        "支持自定义 `BASE_URL`（通过 `.env` 中的 `OPENAI_BASE_URL` 配置）\n"
        "支持自定义分辨率（`size` 字段可传 `auto` 或 `宽x高`，例如 `1024x1024`、`1280x720`）"
    ),
    version="1.0.0",
)


def _norm(v: str | None) -> str | None:
    """把 Swagger UI 传来的空字符串或占位符 'string' 归一化为 None。"""
    if v is None:
        return None
    s = v.strip()
    if not s or s == "string":
        return None
    return s


def _extract_upstream_info(exc: Exception) -> dict:
    """从 OpenAI SDK 异常中抽取上游 API 返回的详细信息。"""
    info: dict = {"exception_type": type(exc).__name__}
    for attr in ("status_code", "code", "message", "request_id", "type", "param"):
        v = getattr(exc, attr, None)
        if v is not None:
            info[attr] = v
    body = getattr(exc, "body", None)
    if body is not None:
        info["body"] = body
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            info["response_text"] = response.text
            info["response_headers"] = dict(response.headers)
        except Exception:
            pass
    return info


def _map_openai_error(exc: Exception, model: str | None = None) -> HTTPException:
    info = _extract_upstream_info(exc)
    logger.error("上游 API 调用失败: %s\n%s", info, traceback.format_exc())

    detail = {
        "message": getattr(exc, "message", None) or str(exc),
        "upstream": info,
    }

    # 提取上游错误码（兼容 {"error": {...}} 与扁平两种结构）
    upstream_code = None
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            upstream_code = err.get("code")
        upstream_code = upstream_code or body.get("code")
    if upstream_code == "model_not_found":
        model_desc = f"模型 '{model}'" if model else "请求的模型"
        detail["message"] = (
            f"上游模型不可用：{model_desc} 在所属分组中没有可用的渠道。"
            "请在上游服务后台为当前分组配置该模型的渠道，或更换请求的模型名。"
        )
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    if isinstance(exc, BadRequestError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    if isinstance(exc, RateLimitError):
        return HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)
    if isinstance(exc, APIConnectionError):
        detail["message"] = f"上游连接异常: {exc}"
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
    if isinstance(exc, APIError):
        upstream_status = getattr(exc, "status_code", None)
        code = upstream_status if isinstance(upstream_status, int) and 400 <= upstream_status < 600 else status.HTTP_502_BAD_GATEWAY
        return HTTPException(status_code=code, detail=detail)
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


def _normalize_result(result) -> dict:
    """把上游返回归一化为 dict，兼容 SDK 对象 / dict / JSON 字符串。"""
    if isinstance(result, str):
        s = result.strip()
        if not s:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="上游返回了空响应")
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            # 非 JSON：可能是上游直接返回的图片 URL 纯文本
            if s.startswith(("http://", "https://", "data:")):
                return {"data": [s]}
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": "上游返回了无法解析的非 JSON 响应",
                    "upstream": {"response_text": s[:2000]},
                },
            )
    if isinstance(result, dict):
        return result
    return {
        "created": getattr(result, "created", None),
        "data": getattr(result, "data", None),
    }


def _item_field(item, key: str):
    """兼容 dict 与 SDK 对象两种数据项形态取字段。"""
    return item.get(key) if isinstance(item, dict) else getattr(item, key, None)


async def _to_response(model: str, result, settings: Settings) -> ImageResponse:
    payload = _normalize_result(result)

    data = payload.get("data")
    if data is None:
        # 兼容部分代理返回的字段名
        for key in ("images", "output", "urls", "items"):
            data = payload.get(key)
            if data is not None:
                break
    if data is None:
        # 部分代理把单张图片 URL 直接放在顶层
        for key in ("url", "image", "result"):
            v = payload.get(key)
            if isinstance(v, str):
                data = [v]
                break
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": "上游响应中未找到图片数据", "upstream": {"body": payload}},
        )
    if isinstance(data, str):
        data = [data]

    images = []
    for item in data:
        if isinstance(item, str):
            item = (
                {"url": item}
                if item.startswith(("http://", "https://", "data:"))
                else {"b64_json": item}
            )
        b64_json = _item_field(item, "b64_json")
        url = _item_field(item, "url")
        if b64_json and settings.oss_enabled:
            # 解码后转存 OSS；成功则返回 OSS 链接，失败保留 base64 兜底
            try:
                raw = base64.b64decode(b64_json)
            except Exception as exc:
                logger.error("base64 解码失败: %s", exc)
                raw = None
            oss_url = None
            if raw:
                oss_url = await asyncio.to_thread(upload_image_bytes, raw, model)
            if oss_url:
                url = oss_url
                b64_json = None
        images.append(
            ImageItem(
                b64_json=b64_json,
                url=url,
                revised_prompt=_item_field(item, "revised_prompt"),
            )
        )
    return ImageResponse(
        model=model,
        created=payload.get("created") or 0,
        images=images,
    )


@app.get("/health", summary="健康检查", description="服务存活检查接口")
async def health() -> dict:
    return {"status": "ok"}


@app.post(
    "/v1/images/generate",
    response_model=ImageResponse,
    summary="文本生成图片",
    description=(
        "根据文本提示词生成图片。\n\n"
        "**参数说明**：\n"
        "- `prompt`：文本提示词（必填）\n"
        "- `n`：生成图片数量，1-10\n"
        "- `size`：分辨率，`auto` 或 `宽x高`（例如 `1024x1024`、`1280x720`、`1536x1024`）\n"
        "- `quality`：质量档位\n"
        "- `background`：背景（`transparent` 生成透明底 PNG）\n"
        "- `model`：可选，覆盖默认模型"
    ),
)
async def generate_image(
    body: GenerateRequest,
    client: Annotated[AsyncOpenAI, Depends(get_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImageResponse:
    model = body.model or settings.image_model
    kwargs: dict = {
        "model": model,
        "prompt": body.prompt,
        "n": body.n,
        "size": body.size,
    }
    if body.quality != "auto":
        kwargs["quality"] = body.quality
    if body.background:
        kwargs["background"] = body.background

    try:
        result = await client.images.generate(**kwargs)
    except Exception as exc:
        raise _map_openai_error(exc, model) from exc
    return await _to_response(model, result, settings)


@app.post(
    "/v1/images/edit",
    response_model=ImageResponse,
    summary="文本 + 参考图生成图片",
    description=(
        "以一张或多张参考图 + 文本提示词进行图像编辑或组合生成。\n\n"
        "**表单字段**：\n"
        "- `prompt`：文本提示词（必填）\n"
        "- `image`：一张或多张参考图（必填，PNG/JPEG/WebP）\n"
        "- `mask`：可选 PNG 蒙版，透明像素区域将被重新生成\n"
        "- `n` / `size` / `quality` / `background` / `model`：与文本生成接口一致\n\n"
        "`size` 支持自定义分辨率，格式 `宽x高`，例如 `1024x1024`、`1280x720`。"
    ),
)
async def edit_image(
    client: Annotated[AsyncOpenAI, Depends(get_client)],
    settings: Annotated[Settings, Depends(get_settings)],
    prompt: str = Form(..., min_length=1, max_length=4000, description="文本提示词"),
    image: UploadFile = File(..., description="参考图（PNG/JPEG/WebP）"),
    image2: UploadFile | None = File(None, description="可选第二张参考图"),
    image3: UploadFile | None = File(None, description="可选第三张参考图"),
    image4: UploadFile | None = File(None, description="可选第四张参考图"),
    mask: UploadFile | None = File(None, description="可选 PNG 蒙版，透明像素区域将被编辑"),
    n: int = Form(1, ge=1, le=10, description="生成图片数量"),
    size: str = Form("auto", description="分辨率：'auto' 或 '宽x高'，例如 '1024x1024'"),
    quality: ImageQuality = Form("auto", description="图片质量"),
    background: str | None = Form(None, description="背景类型：auto / transparent / opaque"),
    model: str | None = Form(None, description="覆盖默认图像模型（留空使用服务端默认）"),
) -> ImageResponse:
    size = _norm(size) or "auto"
    model = _norm(model)
    background = _norm(background)
    if background is not None and background not in ("auto", "transparent", "opaque"):
        raise HTTPException(status_code=400, detail="background 仅支持 auto/transparent/opaque")

    try:
        size = _validate_size(size)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    resolved_model = model or settings.image_model
    image_files = [f for f in (image, image2, image3, image4) if f is not None]
    image_payload = []
    total = 0
    for f in image_files:
        data = await f.read()
        total += len(data)
        if total > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="上传的参考图总大小超过限制")
        buf = io.BytesIO(data)
        buf.name = f.filename or "image.png"
        image_payload.append(buf)

    kwargs: dict = {
        "model": resolved_model,
        "prompt": prompt,
        "n": n,
        "size": size,
        "image": image_payload if len(image_payload) > 1 else image_payload[0],
    }
    if quality != "auto":
        kwargs["quality"] = quality
    if background:
        kwargs["background"] = background

    if mask is not None:
        mask_data = await mask.read()
        if len(mask_data) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="蒙版文件大小超过限制")
        mask_buf = io.BytesIO(mask_data)
        mask_buf.name = mask.filename or "mask.png"
        kwargs["mask"] = mask_buf

    try:
        result = await client.images.edit(**kwargs)
    except Exception as exc:
        raise _map_openai_error(exc, resolved_model) from exc
    return await _to_response(resolved_model, result, settings)
