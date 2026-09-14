# Role model map

The live local OpenCode Go catalog is authoritative.

- Standard supervisor: `opencode-go/minimax-m3`
- Deep supervisor: `opencode-go/deepseek-v4.1-flash`
- Explorer: `opencode-go/deepseek-v4.1-flash`
- Fast worker: `opencode-go/qwen3.8-flash`
- Strong-role worker: `opencode-go/qwen3.8-flash`
- Test/debug worker: `opencode-go/qwen3.8-flash`
- Logic reviewer: `opencode-go/minimax-m3`
- Adversarial reviewer: `opencode-go/deepseek-v4.1-flash`
- Direct read: `opencode-go/deepseek-v4.1-flash`
- Direct write: `opencode-go/qwen3.8-flash`
- Vision reviewer: `opencode-go/deepseek-v4-flash-vision-exp`

Intent:
- Qwen handles most code and tests.
- DeepSeek handles exploration, deep supervision and adversarial review.
- MiniMax supplies independent standard supervision/review.
- Vision is reserved for actual images/screenshots.

Expensive models are not automatic fallbacks.
