# Multi-Provider LLM Support

This project now supports multiple LLM providers with seamless switching via environment variables.

## Supported Providers

- **Ollama** (default) - Local models, completely offline
- **OpenRouter** - Access to 100+ cloud models (Claude, GPT-4, Llama, etc.)
- **OpenAI** - Direct OpenAI API access
- **Custom** - Any OpenAI-compatible endpoint

## Quick Start

### Using Ollama (Default)

```bash
# .env file
LLM_PROVIDER=ollama
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL_NAME=qwen2.5:32b
```

### Using OpenRouter

1. Get an API key from [openrouter.ai](https://openrouter.ai)
2. Update your `.env`:

```bash
# .env file
LLM_PROVIDER=openrouter
LLM_API_KEY=sk-or-v1-your-api-key-here
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL_NAME=meta-llama/llama-3-70b-instruct
```

**Popular OpenRouter models:**
- `meta-llama/llama-3-70b-instruct` - Llama 3 70B
- `google/gemma-2-27b-it` - Gemma 2 27B
- `mistralai/mistral-large` - Mistral Large
- `anthropic/claude-3-sonnet` - Claude 3 Sonnet
- `openai/gpt-4-turbo` - GPT-4 Turbo

### Using OpenAI

```bash
# .env file
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-openai-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4-turbo-preview
```

## Configuration Options

### Ollama-Specific

```bash
# Context window size (prevents prompt truncation)
OLLAMA_NUM_CTX=8192
```

### OpenRouter-Specific

```bash
# Optional: For OpenRouter ranking
OPENROUTER_SITE_URL=https://your-site.com
OPENROUTER_SITE_NAME=MiroFish-Offline

# Reasoning effort for supported models (low, medium, high)
OPENROUTER_REASONING_EFFORT=medium
```

## Hybrid Approach

You can use different providers for different tasks:

- **Local (Ollama)**: Agent simulation, frequent calls
- **Cloud (OpenRouter)**: Final report generation, complex reasoning

To implement this, create separate `LLMClient` instances with different configurations in your code.

## Architecture

The new `ProviderConfig` class (`backend/app/utils/llm_provider.py`) handles:
- Auto-detection of provider from base URL
- Provider-specific request parameters
- Custom headers and options per provider

The `LLMClient` automatically applies the correct configuration based on your settings.

## Migration

Existing configurations continue to work without changes. The system auto-detects the provider from `LLM_BASE_URL`.

To explicitly specify a provider:

```python
from app.utils.llm_client import LLMClient
from app.utils.llm_provider import LLMProvider

# Explicitly set provider
client = LLMClient(provider_name="openrouter")

# Or let it auto-detect from base_url
client = LLMClient(base_url="https://openrouter.ai/api/v1")
```

## Benefits

- **Flexibility**: Switch between local and cloud models instantly
- **Cost optimization**: Use cheap local models for simulation, premium models for reports
- **No vendor lock-in**: Easy to try different models
- **Backward compatible**: Existing setups work unchanged
