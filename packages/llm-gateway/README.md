# llm-gateway

Unified LLM provider abstraction — multi-model gateway with auto-detection.

## Usage

### Python API

```python
from llm_gateway import detect_backends, LLMRequest

# Auto-detect available providers
providers = detect_backends()

# Or create a specific provider
from llm_gateway.detection import create_provider
provider = create_provider("ollama", base_url="http://localhost:11434/v1")

# Make a request
response = provider.complete(LLMRequest(prompt="Hello!"))
print(response.content)  # "Hello! How can I help you?"
print(f"Tokens: {response.input_tokens} in, {response.output_tokens} out")
```

### CLI

```bash
# List available models
llm-gateway list

# Generate from prompt
llm-gateway generate "What is the capital of France?"

# Generate with specific model (model depends on available providers)
llm-gateway generate --model llama3.2 "Explain quantum computing"
```

### MCP (Model Context Protocol)

```bash
# Start MCP server (stdio)
llm-gateway mcp

# Client connects via:
#   - Claude Desktop: add to claude_desktop_config.json
#   - CodeBuddy: add to MCP config
```

### HTTP API

```bash
# Start HTTP server
llm-gateway serve --port 9090

# Generate
curl -X POST http://localhost:9090/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello!", "model": "llama3.2"}'
```

## Supported Providers

| Provider | API Key Env | Default Model |
|----------|------------|---------------|
| Ollama | (none) | local:11434 |
| OpenAI | `OPENAI_API_KEY` | gpt-3.5-turbo |
| Anthropic | `ANTHROPIC_API_KEY` | claude-3-sonnet |
| DeepSeek | `DEEPSEEK_API_KEY` | deepseek-chat |
| Gemini | `GEMINI_API_KEY` | gemini-pro |

## Public API (Stable Symbols)

```python
from llm_gateway import (
    LLMProvider,     # ABC for providers
    LLMRequest,      # Request dataclass
    LLMResponse,     # Response dataclass (includes input/output tokens)
    create_provider, # Create by name
    detect_backends, # Auto-detect available
)
```

## Installation

```bash
pip install llm-gateway
# Or with specific provider:
pip install llm-gateway[openai]
```

## Architecture

```
User → API (CLI / MCP / HTTP / Python)
         ↓
     detect_backends() → create_provider()
         ↓
     LLMProvider.complete(LLMRequest) → LLMResponse
         ↓
     Provider implementations (Ollama, OpenAI, Anthropic, ...)
         ↓
     LLM API
```

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

## License

MIT
