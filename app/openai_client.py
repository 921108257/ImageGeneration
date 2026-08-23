from functools import lru_cache
from openai import AsyncOpenAI
from .config import get_settings
from .schemas import is_gpt_image_2_model, is_qwen_model, is_seedream_model, parse_size


def provider_for_model(model: str, settings=None) -> str:
    settings = settings or get_settings()
    if is_qwen_model(model) or model == settings.qwen_image_model:
        return "qwen"
    if is_seedream_model(model) or model == settings.seedream_image_model:
        return "seedream"
    return "openai"


def uses_small_image_key(model: str, size: str, settings=None) -> bool:
    settings = settings or get_settings()
    dimensions = parse_size(size)
    return is_gpt_image_2_model(model) and dimensions is not None and max(dimensions) <= settings.image_1k_max_edge


def resolve_api_key(model: str, size: str, settings=None) -> str:
    settings = settings or get_settings()
    if uses_small_image_key(model, size, settings) and settings.openai_api_key_1k:
        return settings.openai_api_key_1k
    provider = provider_for_model(model, settings)
    key = {
        "qwen": settings.qwen_api_key,
        "seedream": settings.seedream_api_key,
        "openai": settings.openai_api_key,
    }[provider]
    if not key:
        raise ValueError(f"未配置 {provider} 模型所需的 API Key")
    return key


def resolve_base_url(model: str, settings=None) -> str | None:
    settings = settings or get_settings()
    return {
        "qwen": settings.qwen_base_url,
        "seedream": settings.seedream_base_url,
        "openai": settings.openai_base_url,
    }[provider_for_model(model, settings)]


def configured_models(settings=None) -> list[dict]:
    settings = settings or get_settings()
    credentials = {
        "openai": bool(settings.openai_api_key),
        "qwen": bool(settings.qwen_api_key),
        "seedream": bool(settings.seedream_api_key),
    }
    candidates = [
        (settings.image_model, provider_for_model(settings.image_model, settings), True),
        (settings.qwen_image_model, "qwen", False),
        (settings.seedream_image_model, "seedream", False),
    ]
    models = []
    for model, provider, default in candidates:
        if any(item["id"] == model for item in models) or not default and not credentials[provider]:
            continue
        models.append({"id": model, "provider": provider, "default": default, "configured": credentials[provider]})
    return models


@lru_cache(maxsize=32)
def get_client(model: str | None = None, size: str = "auto") -> AsyncOpenAI:
    settings = get_settings()
    resolved_model = model or settings.image_model
    return AsyncOpenAI(
        api_key=resolve_api_key(resolved_model, size, settings),
        base_url=resolve_base_url(resolved_model, settings),
        timeout=settings.request_timeout,
    )
