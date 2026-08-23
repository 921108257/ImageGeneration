# 术语表

| 术语 | 本项目中的含义 |
|---|---|
| GPT Image 2 | 默认 OpenAI 图像模型 `gpt-image-2`；支持自定义分辨率，但不支持透明背景 |
| Images API | OpenAI 的 `/v1/images/generations` 与 `/v1/images/edits` 能力，由官方 SDK 调用 |
| MCP | Model Context Protocol，Agent 发现并调用本服务工具的标准协议 |
| Streamable HTTP | MCP 的标准 HTTP 传输；本服务入口为 `/mcp` |
| stateless HTTP | 每次 MCP 请求独立处理，服务不依赖连接级隐式会话 |
| ImageContent | MCP 内嵌图片块，数据是 base64，带 MIME 类型 |
| ResourceLink | MCP 指向外部资源的链接；本项目用于 OSS/上游图片 URL |
| structuredContent | MCP 工具的结构化结果；本项目只放元数据，不重复放大体积 base64 |
| input fidelity | 图像编辑时匹配参考图风格和特征的力度，支持 `low/high` |
| output compression | JPEG/WebP 的 0-100 压缩质量；PNG 不接受该参数 |
| DNS rebinding protection | MCP HTTP 层对 Host/Origin 的白名单校验 |
| 服务密钥 | `SERVICE_API_KEY`（兼容别名 `API_KEY`）；调用方使用 Bearer 令牌访问 REST/MCP，不是 OpenAI API key |
| 上游 | OpenAI 官方 API 或 `OPENAI_BASE_URL` 指定的兼容服务 |
| provider | 实际提供图像能力的 OpenAI、Qwen/DashScope 或 Seedream/Ark 服务 |
| 小图专用 Key | GPT Image 2 显式尺寸两边均不超过阈值时使用的 `OPENAI_API_KEY_1K` |
| UI Pro | 默认提示词配置；把产品 brief 补全为包含层级、构图、留白、材质、光照和文字策略的专业资产 brief |
