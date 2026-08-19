import logging
import time
import uuid
from functools import lru_cache

import oss2

from .config import get_settings

logger = logging.getLogger("image_api.oss")


@lru_cache
def get_bucket() -> oss2.Bucket | None:
    """构造 OSS Bucket 客户端；未启用或配置不完整时返回 None。"""
    settings = get_settings()
    if not settings.oss_enabled:
        return None
    if not (
        settings.oss_endpoint
        and settings.oss_bucket
        and settings.oss_access_key_id
        and settings.oss_access_key_secret
    ):
        logger.warning("OSS 配置不完整，跳过上传")
        return None
    auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
    return oss2.Bucket(auth, settings.oss_endpoint, settings.oss_bucket)


def _guess_image_type(data: bytes) -> tuple[str, str]:
    """根据文件头判断图片类型，返回 (扩展名, Content-Type)。"""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png", "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg", "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    return "png", "image/png"


def _public_url(key: str) -> str:
    """构造公开访问 URL，优先使用自定义域名。"""
    settings = get_settings()
    if settings.oss_public_base_url:
        return f"{settings.oss_public_base_url.rstrip('/')}/{key}"
    endpoint = (settings.oss_endpoint or "").replace("https://", "").replace("http://", "").rstrip("/")
    return f"https://{settings.oss_bucket}.{endpoint}/{key}"


def upload_image_bytes(data: bytes, model: str) -> str | None:
    """上传图片字节到 OSS，返回公开访问 URL；未启用或失败时返回 None。"""
    bucket = get_bucket()
    if bucket is None:
        return None
    ext, content_type = _guess_image_type(data)
    prefix = get_settings().oss_key_prefix
    key = f"{prefix}/{model}/{int(time.time())}_{uuid.uuid4().hex[:12]}.{ext}"
    try:
        bucket.put_object(key, data, headers={"Content-Type": content_type})
    except oss2.exceptions.OssError as exc:
        logger.error("OSS 上传失败（key=%s）: %s", key, exc)
        return None
    logger.info("图片已上传 OSS: %s", key)
    return _public_url(key)
