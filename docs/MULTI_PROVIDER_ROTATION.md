# Multi-Provider LLM Configuration with Smart Rotation

## Overview

MiroFish-Offline now supports **multiple LLM providers** (Ollama, OpenRouter, NVIDIA NIM) with **smart automatic rotation** based on:
- Task requirements
- Model health and success rates  
- Cost optimization (prefers free models)
- Automatic fallback on failures

## Quick Start

### 1. Configure API Keys

Edit your `.env` file:

```bash
# Enable smart rotation (recommended)
ENABLE_LLM_ROTATION=true

# OpenRouter API key (for free models)
LLM_API_KEY=sk-or-v1-your-openrouter-key

# NVIDIA NIM API key (for premium models)
NVIDIA_API_KEY=nvapi-your-nvidia-key

# Ollama runs locally (no API key needed)
```

### 2. That's It!

The system automatically:
- Selects the best model for each task type
- Rotates between providers if one fails
- Tracks success rates and response times
- Prefers free models when possible

## Configuration File

All providers and models are configured in `backend/config/llm_providers_config.py`:

### Providers

#### 1. **NVIDIA NIM** (`nvidia`)
- **Base URL**: `https://integrate.api.nvidia.com/v1`
- **API Key Env**: `NVIDIA_API_KEY`
- **Features**: Reasoning support, thinking models, high performance
- **Models**:
  - `mistralai/mistral-small-4-119b-2603` - High-performance general model
  - `nvidia/nemotron-3-super-120b-a12b` - Reasoning + thinking support
  - `qwen/qwen3.5-122b-a10b` - Thinking support
  - `qwen/qwen3.5-397b-a17b` - Ultra-large reasoning model
  - `minimaxai/minimax-m2.5` - Fast general purpose
  - `z-ai/glm5` - Thinking support
  - `z-ai/glm4.7` - Thinking support
  - `stepfun-ai/step-3.5-flash` - Fast inference
  - `moonshotai/kimi-k2.5` - Thinking support

#### 2. **OpenRouter** (`openrouter`)
- **Base URL**: `https://openrouter.ai/api/v1`
- **API Key Env**: `LLM_API_KEY`
- **Features**: Access to 100+ models, free tier available
- **Free Models**:
  - `meta-llama/llama-3-8b-instruct:free`
  - `google/gemma-2-9b-it:free`
  - `microsoft/phi-3-mini-128k-instruct:free`
  - `huggingfaceh4/zephyr-7b-beta:free`
  - `openchat/openchat-7b:free`
- **Paid Models**:
  - `meta-llama/llama-3-70b-instruct`
  - `anthropic/claude-3-haiku`
  - `mistralai/mistral-large`

#### 3. **Ollama** (`ollama`)
- **Base URL**: `http://ollama:11434/v1` (Docker) or `http://localhost:11434/v1`
- **API Key**: None required
- **Features**: Fully local, no internet needed
- **Models**:
  - `qwen2.5:32b` - Default general model
  - `llama3.1:8b` - Fast lightweight model
  - `mixtral:8x7b` - High-performance MoE model

## Task-Based Routing

Different tasks automatically use different models:

| Task Type | Preferred Tags | Priority | Example Use Case |
|-----------|---------------|----------|------------------|
| `persona_generation` | general, high-performance | 2+ | Creating agent personas |
| `simulation_chat` | free, fast, local | ≤2 | Agent interactions in simulation |
| `report_generation` | reasoning, thinking, high-performance | 1+ | Final analysis reports |
| `embedding` | local | Force Ollama | Text embeddings |

## Rotation Strategies

Configure in `ROTATION_CONFIG`:

```python
{
    "enabled": True,
    "max_consecutive_failures": 3,      # Switch after 3 failures
    "provider_cooldown_seconds": 60,     # Wait 60s before retry
    "selection_strategy": "priority",    # priority, random, round_robin, least_loaded
    "fallback_chain": ["ollama", "openrouter", "nvidia"]
}
```

### Selection Strategies

1. **priority** (default): Select by model priority + tag match + success rate
2. **random**: Random selection from available models
3. **round_robin**: Cycle through models evenly
4. **least_loaded**: Balance load across providers

## Health Monitoring

The system tracks:
- ✅ Success/failure rates per model
- ⏱️ Average response times
- 🔄 Consecutive failures
- ❄️ Cooldown status

### View Metrics

```python
from app.utils.llm_rotator import get_rotation_metrics

metrics = get_rotation_metrics()
print(metrics['summary'])
# {
#   'total_models': 19,
#   'healthy': 17,
#   'degraded': 1,
#   'unhealthy': 1,
#   'avg_success_rate': 0.947
# }
```

## Manual Override

### Disable Rotation

Use a specific provider/model:

```python
from app.utils.llm_client import LLMClient

client = LLMClient(
    use_rotation=False,
    provider_name='nvidia',
    model='mistralai/mistral-small-4-119b-2603'
)
```

### Force Provider

```python
# Always use OpenRouter free models
client = LLMClient(
    task_type='simulation_chat',
    force_provider='openrouter'
)
```

## Environment Variables

```bash
# Rotation
ENABLE_LLM_ROTATION=true

# OpenRouter
LLM_API_KEY=sk-or-v1-xxx
OPENROUTER_SITE_URL=https://your-site.com
OPENROUTER_SITE_NAME=MiroFish-Offline
OPENROUTER_REASONING_EFFORT=medium

# NVIDIA NIM
NVIDIA_API_KEY=nvapi-xxx
NVIDIA_REASONING_EFFORT=high

# Ollama
OLLAMA_NUM_CTX=8192
```

## Code Examples

### Basic Usage (Auto-Rotation)

```python
from app.utils.llm_client import LLMClient

# Automatically selects best model for report generation
client = LLMClient(task_type='report_generation')
response = client.chat([
    {"role": "user", "content": "Analyze this document..."}
])
```

### Check Current Model

```python
client = LLMClient(task_type='simulation_chat')
info = client.get_current_model_info()
print(f"Using: {info['provider']}/{info['model']}")
```

### Get All Metrics

```python
from app.utils.llm_client import LLMClient

metrics = LLMClient.get_rotation_metrics()
for model_key, stats in metrics['models'].items():
    print(f"{model_key}: {stats['success_rate']:.1%} success rate")
```

## Fallback Behavior

When a model fails:

1. **First failure**: Retry same model
2. **Second failure**: Retry same model
3. **Third failure**: Mark as unhealthy, enter cooldown (60s)
4. **Fallback**: Try next model in priority order
5. **Ultimate fallback**: Use environment-configured model

## Cost Optimization

To minimize costs:

1. **Enable rotation**: Uses free models when possible
2. **Set task types**: Simulation chats use free/local models
3. **Prioritize tags**: Add `free` to `preferred_tags` in TASK_ROUTING
4. **Monitor usage**: Check metrics regularly

## Troubleshooting

### All Models Failing

Check API keys:
```bash
echo $LLM_API_KEY      # Should show OpenRouter key
echo $NVIDIA_API_KEY   # Should show NVIDIA key
```

### Rotation Not Working

Verify config:
```bash
ENABLE_LLM_ROTATION=true  # Must be set
```

### Check Logs

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Tips

1. **Local-first**: Keep Ollama running for fastest responses
2. **Hybrid approach**: Use local for simulation, cloud for reports
3. **Batch requests**: Group similar tasks together
4. **Monitor metrics**: Watch for degraded models

## Advanced Configuration

Edit `backend/config/llm_providers_config.py` to:

- Add new providers
- Customize model parameters
- Adjust rotation weights
- Define custom task routing
- Set alert thresholds

## API Reference

### llm_rotator module

```python
# Get best model for task
provider, model, config = get_best_model(task_type='report_generation')

# Record request result
record_llm_request('nvidia', 'model-name', success=True, response_time_ms=1234.5)

# Get metrics
metrics = get_rotation_metrics()
```

### llm_client module

```python
# Create client with rotation
client = LLMClient(task_type='simulation_chat')

# Send chat
response = client.chat(messages, temperature=0.7)

# Get JSON response
data = client.chat_json(messages)

# Check current model
info = client.get_current_model_info()

# Get global metrics
metrics = LLMClient.get_rotation_metrics()
```

## License

Same as MiroFish-Offline (AGPL-3.0)
