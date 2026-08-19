from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str
    openai_base_url: str | None = None
    image_model: str = "gpt-image-1"
    max_upload_bytes: int = 8 * 1024 * 1024
    request_timeout: float = 120.0

    # 阿里云 OSS 配置（可选，启用后生成的 b64 图片自动转存 OSS 并返回链接）
    oss_enabled: bool = False
    oss_endpoint: str | None = None
    oss_bucket: str | None = None
    oss_access_key_id: str | None = None
    oss_access_key_secret: str | None = None
    oss_public_base_url: str | None = None
    oss_key_prefix: str = "images"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
