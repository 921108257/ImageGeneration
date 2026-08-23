from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str | None = Field(None, validation_alias=AliasChoices("OPENAI_API_KEY"))
    openai_base_url: str | None = None
    openai_api_key_1k: str | None = Field(
        None,
        validation_alias=AliasChoices("OPENAI_API_KEY_1K", "GPT_IMAGE_2_1K_API_KEY"),
    )
    image_1k_max_edge: int = Field(1024, ge=64, le=4096)
    image_model: str = "gpt-image-2"
    qwen_api_key: str | None = Field(
        None,
        validation_alias=AliasChoices("QWEN_API_KEY", "DASHSCOPE_API_KEY"),
    )
    qwen_base_url: str = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    qwen_image_model: str = "qwen-image-2.0-pro"
    seedream_api_key: str | None = Field(
        None,
        validation_alias=AliasChoices("SEEDREAM_API_KEY", "VOLCENGINE_API_KEY", "ARK_API_KEY"),
    )
    seedream_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    seedream_image_model: str = "doubao-seedream-4-0-250828"
    request_timeout: float = Field(300.0, gt=0)
    max_concurrent_generations: int = Field(4, ge=1, le=64)

    max_upload_bytes: int = Field(50 * 1024 * 1024, ge=1)
    max_upload_total_bytes: int = Field(50 * 1024 * 1024, ge=1)
    max_mask_bytes: int = Field(4 * 1024 * 1024, ge=1)

    service_api_key: str | None = None
    api_rate_limit_per_minute: int = Field(30, ge=0)

    mcp_dns_rebinding_protection: bool = True
    mcp_allowed_hosts: str = "localhost:*,127.0.0.1:*"
    mcp_allowed_origins: str = ""
    mcp_max_request_body_bytes: int = Field(70 * 1024 * 1024, ge=1024)

    oss_enabled: bool = False
    oss_endpoint: str | None = None
    oss_bucket: str | None = None
    oss_access_key_id: str | None = None
    oss_access_key_secret: str | None = None
    oss_public_base_url: str | None = None
    oss_key_prefix: str = "images"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def allowed_mcp_hosts(self) -> list[str]:
        return [value.strip() for value in self.mcp_allowed_hosts.split(",") if value.strip()]

    def allowed_mcp_origins(self) -> list[str]:
        return [value.strip() for value in self.mcp_allowed_origins.split(",") if value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
