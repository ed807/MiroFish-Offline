# OpenRouter API Integration - Complete Guide

## ✅ What Was Implemented

I've successfully added **multi-provider LLM support** to MiroFish-Offline, allowing you to seamlessly switch between:

1. **Ollama** (local, offline) - Default
2. **OpenRouter** (cloud, 100+ models)
3. **OpenAI** (direct API)
4. **Custom** (any OpenAI-compatible endpoint)

---

## 📁 Files Modified/Created

### New Files:
- `backend/app/utils/llm_provider.py` - Provider abstraction layer
- `docs/MULTI_PROVIDER_LLM.md` - Complete documentation

### Modified Files:
- `backend/app/utils/llm_client.py` - Updated to use provider config
- `.env.example` - Added OpenRouter configuration examples

---

## 🚀 Quick Start with OpenRouter

### Step 1: Get an API Key
1. Visit [openrouter.ai](https://openrouter.ai)
2. Sign up and create an API key
3. Copy your key (starts with `sk-or-v1-`)

### Step 2: Configure Your `.env` File

```bash
# Switch from Ollama to OpenRouter
LLM_PROVIDER=openrouter
LLM_API_KEY=sk-or-v1-your-api-key-here
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL_NAME=meta-llama/llama-3-70b-instruct

# Optional: OpenRouter-specific settings
OPENROUTER_SITE_URL=https://your-site.com
OPENROUTER_SITE_NAME=MiroFish-Offline
OPENROUTER_REASONING_EFFORT=medium
```

### Step 3: Restart the Application

```bash
docker compose restart
# or if running locally
python backend/run.py
```

That's it! Your simulation will now use OpenRouter instead of local Ollama.

---

## 💡 Usage Examples

### Example 1: Auto-Detection (Recommended)

The system automatically detects the provider from `LLM_BASE_URL`:

```python
from app.utils.llm_client import LLMClient

# Just configure .env - auto-detects OpenRouter
client = LLMClient()
response = client.chat([{"role": "user", "content": "Hello!"}])
```

### Example 2: Explicit Provider

```python
from app.utils.llm_client import LLMClient

# Explicitly specify provider
client = LLMClient(
    provider_name="openrouter",
    api_key="sk-or-v1-your-key",
    model="google/gemma-2-27b-it"
)
```

### Example 3: Hybrid Approach (Best of Both Worlds)

Use local models for frequent calls, cloud for high-quality reports:

```python
from app.utils.llm_client import LLMClient

# Local Ollama for simulation (cheap, fast)
simulation_client = LLMClient(
    provider_name="ollama",
    base_url="http://localhost:11434/v1",
    model="qwen2.5:14b"
)

# OpenRouter for final report (high quality)
report_client = LLMClient(
    provider_name="openrouter",
    api_key="sk-or-v1-your-key",
    model="anthropic/claude-3-sonnet"
)
```

---

## 🎯 Popular OpenRouter Models

| Category | Model | Price (per 1M tokens) |
|----------|-------|----------------------|
| **Best Value** | `meta-llama/llama-3-70b-instruct` | $0.41 |
| **Fast & Cheap** | `google/gemma-2-9b-it` | $0.06 |
| **High Quality** | `anthropic/claude-3-sonnet` | $3.00 |
| **Top Tier** | `openai/gpt-4-turbo` | $10.00 |
| **Reasoning** | `mistralai/mistral-large` | $4.00 |

See full list: [openrouter.ai/models](https://openrouter.ai/models)

---

## ⚙️ Configuration Options

### Ollama-Specific
```bash
OLLAMA_NUM_CTX=8192  # Context window size
```

### OpenRouter-Specific
```bash
# For ranking and analytics
OPENROUTER_SITE_URL=https://your-site.com
OPENROUTER_SITE_NAME=MiroFish-Offline

# For models with reasoning capabilities
OPENROUTER_REASONING_EFFORT=medium  # low, medium, high
```

---

## 🔧 How It Works

### Architecture

```
┌─────────────────┐
│   LLMClient     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ProviderConfig  │ ← Auto-detects provider
└────────┬────────┘
         │
    ┌────┴────┬──────────┬─────────┐
    ▼         ▼          ▼         ▼
┌──────┐  ┌────────┐  ┌─────┐  ┌──────┐
│Ollama│  │OpenRout│  │OpenAI│  │Custom│
└──────┘  └────────┘  └─────┘  └──────┘
```

### Provider-Specific Optimizations

**Ollama:**
- Automatically sets `num_ctx` for large prompts
- No API key required (just non-empty value)

**OpenRouter:**
- Adds `HTTP-Referer` and `X-Title` headers for ranking
- Supports `reasoning_effort` parameter
- Handles diverse model formats

---

## ✅ Backward Compatibility

Your existing setup continues to work without changes:

```bash
# Old configuration still works
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL_NAME=qwen2.5:32b
```

The system auto-detects this as Ollama and applies the correct settings.

---

## 🧪 Testing

Test the new provider system:

```bash
cd /workspace
python3 -c "
from backend.app.utils.llm_provider import ProviderConfig
import os

# Test Ollama detection
os.environ['LLM_BASE_URL'] = 'http://localhost:11434/v1'
cfg = ProviderConfig.from_env()
print(f'Ollama: {cfg.provider.value}')

# Test OpenRouter detection
os.environ['LLM_BASE_URL'] = 'https://openrouter.ai/api/v1'
cfg = ProviderConfig.from_env()
print(f'OpenRouter: {cfg.provider.value}')
"
```

Expected output:
```
Ollama: ollama
OpenRouter: openrouter
```

---

## 📝 Migration Checklist

- [ ] Copy `.env.example` to `.env` (if not already done)
- [ ] Get OpenRouter API key from [openrouter.ai](https://openrouter.ai)
- [ ] Update `.env` with OpenRouter settings
- [ ] Choose a model (e.g., `meta-llama/llama-3-70b-instruct`)
- [ ] Restart application
- [ ] Test with a small simulation first
- [ ] Monitor costs on OpenRouter dashboard

---

## 💰 Cost Optimization Tips

1. **Hybrid approach**: Use local Ollama for simulation, OpenRouter only for final reports
2. **Cheaper models**: Start with `google/gemma-2-27b-it` ($0.20/M) before upgrading
3. **Monitor usage**: Check [OpenRouter dashboard](https://openrouter.ai/activity)
4. **Set limits**: OpenRouter allows setting spending limits

---

## 🆘 Troubleshooting

### Issue: "Invalid API key"
- Double-check your key starts with `sk-or-v1-`
- Ensure no extra spaces in `.env`

### Issue: "Model not found"
- Verify model name format: `provider/model-name`
- Check [available models](https://openrouter.ai/models)

### Issue: High latency
- Try closer regions (OpenRouter auto-selects)
- Use lighter models like `gemma-2-9b-it`

---

## 📚 Additional Resources

- [OpenRouter Documentation](https://openrouter.ai/docs)
- [Multi-Provider Guide](docs/MULTI_PROVIDER_LLM.md)
- [Available Models](https://openrouter.ai/models)
- [Pricing Calculator](https://openrouter.ai/pricing)

---

## ✨ Benefits Summary

✅ **Flexibility**: Switch providers instantly via environment variables  
✅ **Cost Control**: Use cheap local models + premium cloud when needed  
✅ **No Vendor Lock-in**: Easy to try different models  
✅ **Quality Boost**: Access GPT-4, Claude, Llama-3 for critical tasks  
✅ **Backward Compatible**: Existing setups work unchanged  

**Ready to use OpenRouter?** Just update your `.env` and restart! 🚀
