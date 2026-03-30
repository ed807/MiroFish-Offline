"""
LLM Providers Configuration
Supports Ollama, OpenRouter, and NVIDIA NIM with automatic rotation
"""

import os

# Provider configurations
PROVIDERS = {
    "ollama": {
        "base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        "api_key_env": None,  # No API key needed for Ollama
        "models": {
            "qwen2.5:32b": {
                "tags": ["local", "free", "general"],
                "priority": 1,
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 8192,
                "num_ctx": 32768
            }
        }
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "LLM_API_KEY",
        "headers": {
            "HTTP-Referer": "https://github.com/nikmcfly/MiroFish-Offline",
            "X-Title": "MiroFish-Offline"
        },
        "models": {
            # Free models
            "meta-llama/llama-3-8b-instruct:free": {
                "tags": ["free", "fast", "general"],
                "priority": 10,
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 8192
            },
            "google/gemma-2-9b-it:free": {
                "tags": ["free", "fast", "general"],
                "priority": 11,
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 8192
            },
            "microsoft/phi-3-mini-128k-instruct:free": {
                "tags": ["free", "long-context"],
                "priority": 12,
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 8192
            },
            "huggingfaceh4/zephyr-7b-beta:free": {
                "tags": ["free", "fast"],
                "priority": 13,
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 8192
            },
            "openchat/openchat-7b:free": {
                "tags": ["free", "fast"],
                "priority": 14,
                "temperature": 0.7,
                "top_p": 0.95,
                "max_tokens": 8192
            }
        }
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key_env": "NVIDIA_API_KEY",
        "models": {
            "mistralai/mistral-small-4-119b-2603": {
                "tags": ["premium", "large-context"],
                "priority": 20,
                "temperature": 0.10,
                "top_p": 1.00,
                "max_tokens": 16384,
                "reasoning_effort": "high"
            },
            "nvidia/nemotron-3-super-120b-a12b": {
                "tags": ["premium", "reasoning"],
                "priority": 21,
                "temperature": 1.0,
                "top_p": 0.95,
                "max_tokens": 16384,
                "extra_body": {
                    "chat_template_kwargs": {"enable_thinking": True},
                    "reasoning_budget": 16384
                }
            },
            "qwen/qwen3.5-122b-a10b": {
                "tags": ["premium", "thinking"],
                "priority": 22,
                "temperature": 0.60,
                "top_p": 0.95,
                "max_tokens": 16384,
                "chat_template_kwargs": {"enable_thinking": True}
            },
            "minimaxai/minimax-m2.5": {
                "tags": ["premium", "fast"],
                "priority": 23,
                "temperature": 1.0,
                "top_p": 0.95,
                "max_tokens": 8192
            },
            "qwen/qwen3.5-397b-a17b": {
                "tags": ["premium", "large", "thinking"],
                "priority": 24,
                "temperature": 0.60,
                "top_p": 0.95,
                "top_k": 20,
                "max_tokens": 16384,
                "presence_penalty": 0,
                "repetition_penalty": 1,
                "chat_template_kwargs": {"enable_thinking": True}
            },
            "z-ai/glm5": {
                "tags": ["premium", "thinking"],
                "priority": 25,
                "temperature": 1.0,
                "top_p": 1.0,
                "max_tokens": 16384,
                "extra_body": {
                    "chat_template_kwargs": {"enable_thinking": True, "clear_thinking": False}
                }
            },
            "stepfun-ai/step-3.5-flash": {
                "tags": ["premium", "fast"],
                "priority": 26,
                "temperature": 1.0,
                "top_p": 0.9,
                "max_tokens": 16384
            },
            "moonshotai/kimi-k2.5": {
                "tags": ["premium", "thinking"],
                "priority": 27,
                "temperature": 1.0,
                "top_p": 1.0,
                "max_tokens": 16384,
                "chat_template_kwargs": {"thinking": True}
            },
            "z-ai/glm4.7": {
                "tags": ["premium", "thinking"],
                "priority": 28,
                "temperature": 1.0,
                "top_p": 1.0,
                "max_tokens": 16384,
                "extra_body": {
                    "chat_template_kwargs": {"enable_thinking": True, "clear_thinking": False}
                }
            }
        }
    }
}

# Rotation configuration
ROTATION_CONFIG = {
    "enabled": os.environ.get("ENABLE_LLM_ROTATION", "true").lower() == "true",
    "selection_strategy": "priority",  # priority, random, round_robin, least_loaded
    "max_consecutive_failures": 3,
    "provider_cooldown_seconds": 60,
    "health_check": {
        "enabled": False,
        "interval_seconds": 300
    },
    "weights": {
        "ollama": 0.5,
        "openrouter": 1.0,
        "nvidia": 1.5
    }
}

# Task-specific routing
TASK_ROUTING = {
    "simulation_chat": {
        "preferred_tags": ["fast", "free"],
        "avoid_free_only": False
    },
    "report_generation": {
        "preferred_tags": ["premium", "reasoning", "thinking"],
        "avoid_free_only": True
    },
    "graph_extraction": {
        "preferred_tags": ["local", "free"],
        "avoid_free_only": False
    },
    "profile_generation": {
        "preferred_tags": ["fast", "free"],
        "avoid_free_only": False
    }
}
