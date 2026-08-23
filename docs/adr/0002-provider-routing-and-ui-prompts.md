# ADR 0002: 多模型路由与专业 UI 提示层

- 状态：已接受
- 日期：2026-08-23

## 背景

同一套 REST/MCP/Plugin 需要支持 GPT Image 2、Qwen Image 与 Seedream，同时让前端工程师只提供产品 brief，也能得到具有清晰层级、留白和设计系统一致性的界面资源。

## 决策

1. 模型名称决定 provider；每个 provider 使用独立 Key 与 Base URL，响应统一归一化为 `ImageResponse`。
2. GPT Image 2 只有在显式尺寸的两条边均不超过 `IMAGE_1K_MAX_EDGE` 时才选择小图专用 Key；专用 Key 缺失时回退默认 OpenAI Key。`size=auto` 无法预判，因此使用默认 Key。
3. Qwen 使用 DashScope 原生同步多模态生成接口；Seedream 使用 Ark OpenAI 兼容 Images 接口。非 OpenAI provider 当前只承诺生成，不伪装支持编辑。
4. `ui_pro` 在共享服务层扩展提示词，REST 与 MCP 行为一致；`raw` 保留调用方原始提示词。
5. 本地插件默认连接回环地址且不启用服务鉴权；远程模板使用环境变量 Bearer Token。

## 结果

- 新 provider 只需要补路由、参数映射和归一化，不改变 REST/MCP 契约。
- 自动尺寸不会错误消耗 1K 专用 Key。
- UI 提示增强是可关闭的，不阻塞已有精确提示词工作流。
- Qwen 返回的临时 URL 必须由调用 Skill 及时保存；需要服务端持久化时启用对象存储或扩展 URL 转存。

## 依据

- [OpenAI Image generation](https://developers.openai.com/api/docs/guides/image-generation)
- [OpenAI GPT Image 2](https://developers.openai.com/api/docs/models/gpt-image-2)
- [Alibaba Cloud Qwen Image API](https://help.aliyun.com/zh/model-studio/qwen-image-api)
- [Volcengine Ark API documentation](https://www.volcengine.com/docs/82379)
