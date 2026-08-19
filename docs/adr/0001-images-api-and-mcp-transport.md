# ADR 0001: Images API + Streamable HTTP MCP

- 状态：已接受
- 日期：2026-08-19

## 背景

服务需要让 Agent 在服务器上生成界面位图资源，同时保留普通 HTTP 调用。OpenAI 提供直接的 Images API，也可在 Responses API 中使用图像生成工具；MCP 则定义了 tools、图片内容块、资源链接和标准传输。

## 决策

1. 上游采用 OpenAI Images API。它直接覆盖单次生成、多参考图编辑、输出格式、压缩和 input fidelity，避免为了单次资产生成引入会话状态。
2. REST 与 MCP 共用同一个校验、上游调用和结果归一化层。
3. MCP 使用官方 Python SDK 2.x 的 Streamable HTTP，挂载在同一 ASGI 进程的 `/mcp`，启用 stateless HTTP 与 JSON 响应。
4. base64 结果用 MCP `ImageContent` 返回；持久化 URL 用 `ResourceLink` 返回；同时提供不含 base64 的 `structuredContent` 和 JSON 文本块。
5. MCP 编辑只接收 base64/data URL，不接收远程 URL或服务器路径，避免 SSRF 和本地文件越权。
6. 公网的最小鉴权为静态 Bearer 服务密钥；多租户 OAuth、配额与跨实例限流交给 API 网关或专用授权层。

## 结果

- REST 和 MCP 不会出现参数支持差异。
- 单进程部署简单，Agent 能直接消费标准图片内容块。
- 未启用 OSS 时，MCP/REST 响应可能很大；启用对象存储后改为资源链接。
- 当前不暴露 OpenAI partial image streaming，也不实现 MCP Tasks 扩展。只有在真实客户端需要长任务恢复或渐进预览时再增加。
- 静态 Bearer 适合私有 Agent，不适合直接作为多租户授权模型。

## 依据

- [OpenAI image generation](https://developers.openai.com/api/docs/guides/image-generation)
- [OpenAI GPT Image 2](https://developers.openai.com/api/docs/models/gpt-image-2)
- [MCP tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
- [MCP transports](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports)
- [MCP resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)
