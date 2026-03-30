# MiroFish Multi-Provider LLM Configuration
# This file defines all available providers and their models with rotation support

PROVIDERS = {
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key_env": "NVIDIA_API_KEY",
        "type": "openai_compatible",
        "supports_reasoning": True,
        "supports_thinking": True,
        "timeout": 60,
        "max_retries": 3,
        "models": {
            # High-performance general models
            "mistralai/mistral-small-4-119b-2603": {
                "temperature": 0.10,
                "top_p": 1.00,
                "max_tokens": 16384,
                "reasoning_effort": "high",
                "priority": 1,
                "tags": ["general", "high-performance"]
            },
            # Reasoning models with thinking support
            "nvidia/nemotron-3-super-120b-a12b": {
                "temperature": 1.0,
                "top_p": 0.95,
                "max_tokens": 16384,
                "extra_body": {
                    "chat_template_kwargs": {"enable_thinking": True},
                    "reasoning_budget": 16384
                },
                "priority": 2,
                "tags": ["reasoning", "thinking", "premium"]
            },
            "qwen/qwen3.5-122b-a10b": {
                "temperature": 0.60,
                "top_p": 0.95,
                "max_tokens": 16384,
                "chat_template_kwargs": {"enable_thinking": True},
                "priority": 2,
                "tags": ["reasoning", "thinking"]
            },
            "qwen/qwen3.5-397b-a17b": {
                "temperature": 0.60,
                "top_p": 0.95,
                "top_k": 20,
                "presence_penalty": 0,
                "repetition_penalty": 1,
                "max_tokens": 16384,
                "chat_template_kwargs": {"enable_thinking": True},
                "priority": 1,
                "tags": ["reasoning", "thinking", "ultra-large"]
            },
            # General purpose models
            "minimaxai/minimax-m2.5": {
                "temperature": 1.0,
                "top_p": 0.95,
                "max_tokens": 8192,
                "priority": 3,
                "tags": ["general", "fast"]
            },
            "z-ai/glm5": {
                "temperature": 1.0,
                "top_p": 1.0,
                "max_tokens": 16384,
                "extra_body": {
                    "chat_template_kwargs": {
                        "enable_thinking": True,
                        "clear_thinking": False
                    }
                },
                "priority": 2,
                "tags": ["reasoning", "thinking"]
            },
            "z-ai/glm4.7": {
                "temperature": 1.0,
                "top_p": 1.0,
                "max_tokens": 16384,
                "extra_body": {
                    "chat_template_kwargs": {
                        "enable_thinking": True,
                        "clear_thinking": False
                    }
                },
                "priority": 3,
                "tags": ["reasoning", "thinking"]
            },
            "stepfun-ai/step-3.5-flash": {
                "temperature": 1.0,
                "top_p": 0.9,
                "max_tokens": 16384,
                "priority": 3,
                "tags": ["general", "fast"]
            },
            "moonshotai/kimi-k2.5": {
                "temperature": 1.0,
                "top_p": 1.0,
                "max_tokens": 16384,
                "chat_template_kwargs": {"thinking": True},
                "priority": 2,
                "tags": ["reasoning", "thinking"]
            }
        }
    },
    
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "LLM_API_KEY",
        "type": "openai_compatible",
        "supports_reasoning": True,
        "supports_thinking": False,
        "timeout": 45,
        "max_retries": 3,
        "headers": {
            "HTTP-Referer": "https://github.com/nikmcfly/MiroFish-Offline",
            "X-Title": "MiroFish Offline"
        },
        "models": {
            # Free models (priority for cost optimization)
            "meta-llama/llama-3-8b-instruct:free": {
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 8192,
                "priority": 1,
                "tags": ["free", "general", "fast"]
            },
            "google/gemma-2-9b-it:free": {
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 8192,
                "priority": 1,
                "tags": ["free", "general"]
            },
            "microsoft/phi-3-mini-128k-instruct:free": {
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 8192,
                "priority": 1,
                "tags": ["free", "general", "long-context"]
            },
            "huggingfaceh4/zephyr-7b-beta:free": {
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 8192,
                "priority": 1,
                "tags": ["free", "general"]
            },
            "openchat/openchat-7b:free": {
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 8192,
                "priority": 1,
                "tags": ["free", "general"]
            },
            # Paid but low-cost models
            "meta-llama/llama-3-70b-instruct": {
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 8192,
                "priority": 2,
                "tags": ["paid", "high-performance"]
            },
            "anthropic/claude-3-haiku": {
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 4096,
                "priority": 2,
                "tags": ["paid", "reasoning"]
            },
            "mistralai/mistral-large": {
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 8192,
                "priority": 2,
                "tags": ["paid", "high-performance"]
            }
        }
    },
    
    "ollama": {
        "base_url": "http://ollama:11434/v1",
        "api_key_env": None,  # No API key needed for Ollama
        "type": "openai_compatible",
        "supports_reasoning": False,
        "supports_thinking": False,
        "timeout": 120,
        "max_retries": 2,
        "models": {
            "qwen2.5:32b": {
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 8192,
                "num_ctx": 32768,
                "priority": 1,
                "tags": ["local", "general"]
            },
            "llama3.1:8b": {
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 8192,
                "num_ctx": 8192,
                "priority": 2,
                "tags": ["local", "fast"]
            },
            "mixtral:8x7b": {
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 8192,
                "num_ctx": 16384,
                "priority": 2,
                "tags": ["local", "high-performance"]
            }
        }
    }
}

# Rotation Strategy Configuration
ROTATION_CONFIG = {
    # Enable smart rotation across providers
    "enabled": True,
    
    # Maximum consecutive failures before switching provider
    "max_consecutive_failures": 3,
    
    # Cooldown period (seconds) after a provider fails
    "provider_cooldown_seconds": 60,
    
    # Model selection strategy: "priority", "random", "round_robin", "least_loaded"
    "selection_strategy": "priority",
    
    # Fallback chain: if primary fails, try these in order
    "fallback_chain": ["ollama", "openrouter", "nvidia"],
    
    # Health check settings
    "health_check": {
        "enabled": True,
        "interval_seconds": 300,  # Check every 5 minutes
        "test_prompt": "Hello, are you working?",
        "timeout_seconds": 10
    },
    
    # Load balancing weights (if using least_loaded strategy)
    "weights": {
        "nvidia": 0.5,
        "openrouter": 0.3,
        "ollama": 0.2
    }
}

# Task-specific model routing
TASK_ROUTING = {
    # For agent persona generation (needs creativity)
    "persona_generation": {
        "preferred_tags": ["general", "high-performance"],
        "avoid_free_only": True,
        "min_priority": 2
    },
    
    # For simulation interactions (needs speed + low cost)
    "simulation_chat": {
        "preferred_tags": ["free", "fast", "local"],
        "prefer_local": True,
        "max_priority": 2
    },
    
    # For report generation (needs high quality + reasoning)
    "report_generation": {
        "preferred_tags": ["reasoning", "thinking", "high-performance"],
        "avoid_free_only": True,
        "min_priority": 1
    },
    
    # For embedding generation
    "embedding": {
        "preferred_tags": ["local"],
        "force_provider": "ollama"
    }
}

# Logging and monitoring
MONITORING = {
    "log_all_requests": True,
    "log_response_times": True,
    "track_failure_rates": True,
    "alert_threshold_failure_rate": 0.3,  # Alert if >30% failures
    "metrics_endpoint": "/api/v1/llm/metrics"
}
