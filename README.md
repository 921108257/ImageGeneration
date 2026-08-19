# OpenAI 图像生成 API

基于 FastAPI 封装 OpenAI 图像模型（默认 `gpt-image-1`）的 REST 服务，支持：

- **文本生成图片**：`POST /v1/images/generate`
- **文本 + 参考图生成图片**：`POST /v1/images/edit`（multipart 上传）
- **自定义 BASE_URL**：通过环境变量指向代理、Azure OpenAI 兼容端点或第三方镜像
- **自定义分辨率**：`size` 字段支持 `auto` 或任意 `宽x高`（例如 `1024x1024`、`1280x720`、`1536x1024`）

> 注：OpenAI 目前的图像模型名为 `gpt-image-1`；若需使用 DALL·E 2 请在 `.env` 中设置 `IMAGE_MODEL=dall-e-2`。

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env       # 编辑 OPENAI_API_KEY，可选 OPENAI_BASE_URL
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

打开交互式文档：http://localhost:8000/docs

## 环境变量

| 变量名 | 说明 | 默认值 |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API 密钥（必填） | - |
| `OPENAI_BASE_URL` | 自定义 API 地址（可选） | OpenAI 官方地址 |
| `IMAGE_MODEL` | 默认图像模型 | `gpt-image-1` |
| `MAX_UPLOAD_BYTES` | 上传文件大小上限（字节） | `8388608`（8MB） |
| `REQUEST_TIMEOUT` | 请求超时（秒） | `120` |

## 接口说明

### 1. 文本生成图片 `POST /v1/images/generate`

请求体（JSON）：

```json
{
  "prompt": "一只穿着宇航服在太空中漂浮的小熊猫，吉卜力工作室风格",
  "n": 1,
  "size": "1280x720",
  "quality": "high",
  "background": "transparent"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `prompt` | string | 是 | 文本提示词，1-4000 字 |
| `n` | int | 否 | 生成图片数量，1-10，默认 1 |
| `size` | string | 否 | `auto` 或 `宽x高`，宽高范围 64-4096 |
| `quality` | string | 否 | `auto` / `low` / `medium` / `high` / `standard` / `hd` |
| `background` | string | 否 | `auto` / `transparent` / `opaque` |
| `model` | string | 否 | 覆盖默认模型 |

### 2. 文本 + 参考图生成 `POST /v1/images/edit`

`multipart/form-data` 表单字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `prompt` | string | 是 | 文本提示词 |
| `image` | file(s) | 是 | 一张或多张参考图（PNG/JPEG/WebP） |
| `mask` | file | 否 | PNG 蒙版，透明像素区域将被重新生成 |
| `n`、`size`、`quality`、`background`、`model` | | 否 | 与文本生成接口一致 |

调用示例：

```bash
curl -X POST http://localhost:8000/v1/images/edit \
  -F "prompt=把天空换成繁星密布的夜空" \
  -F "image=@./photo.png" \
  -F "mask=@./mask.png" \
  -F "size=1280x720"
```

### 响应格式

```json
{
  "model": "gpt-image-1",
  "created": 1730000000,
  "images": [
    { "b64_json": "iVBORw0KGgo...", "url": null, "revised_prompt": null }
  ]
}
```

`gpt-image-1` 始终返回 base64；`dall-e-*` 系列可能返回 URL。
