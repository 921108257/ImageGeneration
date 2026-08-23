# Provider Matrix

| Provider | Model examples | Endpoint mode | Key variables | Important limits |
|---|---|---|---|---|
| OpenAI | `gpt-image-2` | OpenAI Images API | `OPENAI_API_KEY`, optional `OPENAI_API_KEY_1K` | GPT Image 2 dimensions use 16-pixel edges; transparent background is rejected |
| Qwen | `qwen-image-2.0-pro`, `qwen-image-3.0` | DashScope native multimodal generation | `QWEN_API_KEY` or `DASHSCOPE_API_KEY` | `WIDTH*HEIGHT`; Qwen Image 2 total pixels 512²-2048²; image URLs expire |
| Seedream | `doubao-seedream-4-0-250828` | Ark OpenAI-compatible Images API | `SEEDREAM_API_KEY`, `VOLCENGINE_API_KEY`, or `ARK_API_KEY` | Configure the regional Ark base URL and model id issued to the account |

The service normalizes provider output to one response shape: `model`, `provider`, `images`, `mime_type`, `url` or `b64_json`, and `usage` when available.
