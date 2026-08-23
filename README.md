# GPT Image 2 界面资源生成服务

这是一个可本地或服务器部署的多模型图像资源服务，同时提供 REST、MCP Streamable HTTP、Codex Plugin 和前端资产 Skill。默认模型为 `gpt-image-2`，面向前端工程师生成可直接落地的 UI 背景、插图、图标、纹理、产品 mockup 和其他位图资源。

## 能力

- `POST /v1/images/generate`：文本生成图片
- `POST /v1/images/edit`：1-16 张参考图编辑或组合
- `POST /mcp`：MCP Streamable HTTP，暴露 `generate_ui_asset` 和 `edit_ui_asset`
- `GET /v1/models`：查看已配置的模型提供商
- GPT Image 2 自定义尺寸、输出格式、JPEG/WebP 压缩、质量、moderation
- GPT Image 2 1K 专用 Key 路由：存在 `OPENAI_API_KEY_1K` 时，明确指定不超过 `IMAGE_1K_MAX_EDGE` 的请求优先使用它，否则回退默认 OpenAI Key
- Qwen Image 原生 DashScope 生成适配、Seedream Ark OpenAI 兼容适配
- `prompt_profile=ui_pro`：把短需求扩展为包含层级、留白、材质、灯光和集成约束的专业 UI 资产 brief
- GPT Image 编辑的 `input_fidelity`
- 可选阿里云 OSS 持久化；未启用时返回 base64
- 可选 Bearer 服务密钥、DNS rebinding 防护、单进程限流与并发限制
- Docker 与反向代理部署

## 先读：GPT Image 2 的差异

`gpt-image-2` 的提示词最长 32,000 字符。自定义 `WIDTHxHEIGHT` 的宽和高必须都是 16 的倍数，宽高比需在 1:3 到 3:1 之间，并受 3840x2160 对应的边长和像素上限约束。高于 2560x1440 的尺寸属于实验范围，是否可用仍可能受账号和模型当前限制影响。

`gpt-image-2` 和 `gpt-image-2-2026-04-21` **不支持透明背景**。需要透明 PNG/WebP 时，应显式选择支持透明背景的 GPT Image 模型；本服务会在调用上游前拒绝不兼容的参数组合。

GPT Image 模型始终返回 base64。设置 `OSS_ENABLED=true` 后，服务会把图片上传到 OSS，并用资源 URL 替换响应中的 base64。

## 本地运行

要求 Python 3.11+。最简单的方式是运行一键向导：

```powershell
.\scripts\setup.ps1
.\scripts\start.ps1
```

macOS/Linux：

```bash
./scripts/setup.sh
./scripts/start.sh
```

向导会隐藏输入的密钥、写入被 Git 忽略的 `.env`，并默认只监听 `127.0.0.1:8000`。也可以直接使用 Docker：

```bash
docker compose up --build
```

安装本地 Codex Plugin：

```powershell
.\scripts\install_codex.ps1
```

需要拆分透明图标 sheet 时再安装可选资产依赖：`pip install -r requirements-assets.txt`。普通生成服务不需要 Pillow 或 `rembg`。

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows PowerShell: Copy-Item .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

可用地址：

- 服务信息：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/health`
- OpenAPI：`http://127.0.0.1:8000/docs`
- MCP：`http://127.0.0.1:8000/mcp`

如果系统设置了 `HTTP_PROXY/HTTPS_PROXY`，请让本机 MCP 地址绕过代理，例如设置 `NO_PROXY=127.0.0.1,localhost`；否则某些 HTTP 客户端会把环回请求错误地发送到外部代理。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `OPENAI_API_KEY` | 按需 | 使用 OpenAI/GPT Image 时必填，只保存在服务端 |
| `OPENAI_BASE_URL` | 官方地址 | 可选 OpenAI 兼容网关 `/v1` 地址 |
| `OPENAI_API_KEY_1K` | 空 | GPT Image 2 不超过 `IMAGE_1K_MAX_EDGE` 时优先使用；未设置则回退 `OPENAI_API_KEY` |
| `IMAGE_1K_MAX_EDGE` | `1024` | 小图专用 Key 的最长边阈值 |
| `IMAGE_MODEL` | `gpt-image-2` | 默认图像模型 |
| `QWEN_API_KEY` / `DASHSCOPE_API_KEY` | 空 | Qwen Image Key |
| `QWEN_BASE_URL` | DashScope 原生接口 | Qwen 图像生成 URL |
| `QWEN_IMAGE_MODEL` | `qwen-image-2.0-pro` | 默认 Qwen 图像模型 |
| `SEEDREAM_API_KEY` / `VOLCENGINE_API_KEY` | 空 | Seedream/Ark Key |
| `SEEDREAM_BASE_URL` | Ark 北京 API | Seedream OpenAI 兼容根地址 |
| `SEEDREAM_IMAGE_MODEL` | `doubao-seedream-4-0-250828` | 默认 Seedream 模型 ID |
| `REQUEST_TIMEOUT` | `300` | 上游请求超时，秒 |
| `MAX_CONCURRENT_GENERATIONS` | `4` | 单进程同时调用上游的上限 |
| `MAX_UPLOAD_BYTES` | `52428800` | 单张参考图上限，默认 50MB |
| `MAX_UPLOAD_TOTAL_BYTES` | `52428800` | 一次编辑的参考图总上限 |
| `MAX_MASK_BYTES` | `4194304` | PNG mask 上限，默认 4MB |
| `SERVICE_API_KEY` / `API_KEY` | 空 | REST/MCP 的 Bearer 密钥；公网部署必须设置，前者优先 |
| `API_RATE_LIMIT_PER_MINUTE` | `30` | 单进程固定窗口请求数；`0` 关闭 |
| `MCP_ALLOWED_HOSTS` / `MCP_HOSTS` | 本机 | 逗号分隔的 Host 白名单，前者优先；支持 `localhost:*` |
| `MCP_ALLOWED_ORIGINS` | 空 | 逗号分隔的 Origin 白名单 |
| `MCP_MAX_REQUEST_BODY_BYTES` | `73400320` | MCP JSON 请求体上限 |
| `OSS_ENABLED` | `false` | 是否把生成结果转存 OSS |

`MCP_ALLOWED_HOSTS`（或兼容别名 `MCP_HOSTS`）按 Host 请求头匹配，`*` 本身不是“允许全部”。公网部署应同时配置裸域名和带端口形式，例如 `image.example.com,image.example.com:*,localhost:*,127.0.0.1:*`。服务访问密钥使用 `SERVICE_API_KEY`（或兼容别名 `API_KEY`）；若两个变量同时存在，规范变量优先。

完整 OSS 配置见 [.env.example](./.env.example)。

## REST API

若设置了 `SERVICE_API_KEY` 或 `API_KEY`，所有生成/编辑与 MCP 请求都需要：

```http
Authorization: Bearer YOUR_SERVICE_API_KEY
```

### 生成

```bash
curl http://127.0.0.1:8000/v1/images/generate \
  -H "Authorization: Bearer $IMAGE_SERVICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "为数据分析产品生成一张安静、清晰的空状态插图，无文字",
    "size": "1536x864",
    "quality": "high",
    "background": "opaque",
    "output_format": "webp",
    "output_compression": 85,
    "moderation": "auto"
  }'
```

生成字段：

| 字段 | 约束 |
|---|---|
| `prompt` | 必填；GPT Image 最长 32,000 字符 |
| `n` | 1-10；默认 1 |
| `size` | `auto` 或 `WIDTHxHEIGHT`；GPT Image 2 见上方约束 |
| `quality` | GPT Image：`auto/low/medium/high` |
| `background` | `auto/opaque/transparent`；GPT Image 2 禁止 transparent |
| `output_format` | GPT Image：`png/jpeg/webp` |
| `output_compression` | 0-100，仅 `jpeg/webp` |
| `moderation` | GPT Image：`auto/low` |
| `user` | 稳定、非敏感的终端用户 ID，用于安全监控 |
| `model` | 可覆盖服务端默认模型 |
| `prompt_profile` | `ui_pro` 或 `raw`；默认把短需求扩展为专业 UI 资产 brief |
| `asset_type` | `hero_background/empty_state/illustration/icon/logo/texture/product_mockup/avatar/pattern` |
| `platform` | `web/mobile/desktop/cross_platform` |
| `visual_style` / `brand_palette` / `composition` | 可选视觉系统、材质和构图约束 |
| `content_density` | `airy/balanced/dense` |
| `text_policy` | `no_text/minimal_text/exact_text` |
| `negative_prompt` / `prompt_extend` / `watermark` / `seed` | Qwen/兼容模型的扩展参数 |

### 多图编辑

重复使用 `image` 字段即可上传多张参考图：

```bash
curl http://127.0.0.1:8000/v1/images/edit \
  -H "Authorization: Bearer $IMAGE_SERVICE_API_KEY" \
  -F "prompt=保留产品外形，把它放入简洁的电商详情页场景，不要添加文字" \
  -F "image=@product.png" \
  -F "image=@style-reference.webp" \
  -F "input_fidelity=high" \
  -F "size=1536x1024" \
  -F "quality=high" \
  -F "output_format=png"
```

参考图支持 PNG、JPEG、WebP，最多 16 张。`mask` 只能是小于 4MB 的 PNG，透明区域表示需要编辑的位置；mask 会应用到第一张参考图，尺寸一致性由 OpenAI 上游再次校验。

### 响应

```json
{
  "model": "gpt-image-2",
  "created": 1787100000,
  "images": [
    {
      "b64_json": "iVBORw0KGgo...",
      "url": null,
      "mime_type": "image/png",
      "revised_prompt": null
    }
  ],
  "background": "opaque",
  "output_format": "png",
  "quality": "high",
  "size": "1536x1024",
  "usage": {
    "input_tokens": 42,
    "output_tokens": 4096,
    "total_tokens": 4138
  }
}
```

代理返回 SDK 对象、JSON、URL、base64 或常见兼容字段时，服务会尽量归一化成以上结构。不能解析的响应会返回 `502`，而不是伪造成功结果。

## MCP

服务使用官方 Python MCP SDK 2.x，按协商版本提供 Streamable HTTP。当前实现采用 stateless HTTP 和 JSON 响应，工具返回：

- `TextContent`：不含大体积 base64 的 JSON 元数据，兼容旧客户端
- `ImageContent`：未启用 OSS 时的 base64 图片
- `ResourceLink`：启用 OSS 或上游返回 URL 时的图片链接
- `structuredContent`：模型、尺寸、格式、usage 和图片索引

工具：

| 工具 | 用途 |
|---|---|
| `list_ui_models` | 查看已配置提供商、模型及 generate/edit 能力，不调用上游 |
| `generate_ui_asset` | 文本生成 1-10 张界面位图资源 |
| `edit_ui_asset` | 用 base64/data URL 参考图编辑或组合资源 |

### 前端产出工作流

插件内的 [gpt-image-2-assets Skill](./plugins/gpt-image-2-assets/skills/gpt-image-2-assets/SKILL.md) 负责把产品上下文、平台、资产类型、留白、材质和文字策略组织成可执行的提示词。它要求生成结果落盘到前端项目，不把短期 Provider URL 留作运行时依赖；图标还要经过 `rembg` 去底并校验 RGBA alpha。`ui-ux-asset-pipeline` 可进一步用 `split_icon_sheet.py` 拆分一致的图标族。

远程 URL 和服务器文件路径不会被 `edit_ui_asset` 接受，这避免了 SSRF 和越权读取服务器文件。远程 MCP 配置示例：

```json
{
  "mcpServers": {
    "gpt-image-2-assets": {
      "type": "http",
      "url": "https://image.example.com/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_SERVICE_API_KEY"
      }
    }
  }
}
```

仓库中的 `plugins/gpt-image-2-assets` 是可安装的本地 Plugin，默认连接本机 MCP。部署到服务器后，把它的 `.mcp.json` 替换为 `plugins/gpt-image-2-assets/.mcp.remote.example.json` 的远程 URL，并配置 `GPT_IMAGE_2_SERVICE_API_KEY` 环境变量。

## Docker 部署

```bash
docker build -t gpt-image-2-mcp .
docker run -d --name gpt-image-2-mcp \
  --env-file .env \
  -p 127.0.0.1:8000:8000 \
  --restart unless-stopped \
  gpt-image-2-mcp
```

公网部署时至少完成三件事：

1. 设置高熵 `SERVICE_API_KEY`（`API_KEY` 也兼容），不要把 OpenAI 密钥放进 Agent 或插件。
2. 把实际域名的裸域名和带端口形式都加入 `MCP_ALLOWED_HOSTS`（`MCP_HOSTS` 也兼容），例如 `image.example.com,image.example.com:*,localhost:*,127.0.0.1:*`。
3. 在 TLS 反向代理/API 网关设置统一的主体鉴权、请求体限制、速率限制和审计日志。

Nginx 片段：

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_buffering off;
    proxy_read_timeout 360s;
    client_max_body_size 70m;
}
```

应用内限流是每个 Python 进程各自计数，不能替代多实例网关。Docker 默认只启动一个 worker；横向扩容时应在共享网关限流。面向多租户或第三方公开发布时，静态 Bearer 密钥也不等同于完整 OAuth 授权服务器，应在网关或 MCP OAuth 层完成主体、scope、撤销和轮换。

## API 选择

本服务使用 Images API，而没有把 Responses API 的 `image_generation` 工具包进来。Images API 更适合一次性生成/编辑并直接拿到图片；Responses API 更适合对话上下文中的多轮图像工作流。这个取舍和 MCP 传输决策记录在 [ADR 0001](./docs/adr/0001-images-api-and-mcp-transport.md)，术语见 [glossary](./docs/glossary.md)。

## 官方资料

- [OpenAI Image generation guide](https://developers.openai.com/api/docs/guides/image-generation)
- [OpenAI GPT Image 2 model](https://developers.openai.com/api/docs/models/gpt-image-2)
- [Alibaba Cloud Qwen Image API](https://help.aliyun.com/zh/model-studio/qwen-image-api)
- [Volcengine Ark documentation](https://www.volcengine.com/docs/82379)
- [MCP 2026-07-28 Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
- [MCP 2026-07-28 Transports](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports)
- [MCP 2026-07-28 Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)

OpenAI 的模型可用性、配额、计费和高分辨率支持取决于账号与实时发布状态；服务只在本地校验公开参数约束，最终仍以上游响应为准。

## 开源发布清单

- 不提交 `.env`、API Key、OSS 密钥或生成结果；`.gitignore` 已覆盖本地密钥文件。
- 运行 `python -m unittest discover -s tests -v`、插件校验和 Skill 校验。
- 用 `git grep` 检查仓库中没有真实凭据，再提交并推送到你的 GitHub 仓库。
