"""
LLM Provider Abstraction Layer
Supports multiple providers: Ollama, OpenRouter, OpenAI, etc.
Allows switching between providers based on configuration
"""

from enum import Enum
from typing import Optional, Dict, Any


class LLMProvider(Enum):
    """Supported LLM Providers"""
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    OPENAI = "openai"
    NVIDIA = "nvidia"
    CUSTOM = "custom"


class ProviderConfig:
    """Provider-specific configuration"""
    
    def __init__(
        self,
        provider: LLMProvider,
        api_key: str,
        base_url: str,
        model: str,
        extra_config: Optional[Dict[str, Any]] = None
    ):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.extra_config = extra_config or {}
    
    @classmethod
    def from_env(cls, provider_name: Optional[str] = None) -> 'ProviderConfig':
        """
        Create ProviderConfig from environment variables
        
        Args:
            provider_name: Override provider name (default: auto-detect from base_url)
        
        Returns:
            ProviderConfig instance
        """
        import os
        
        # Get base configuration
        api_key = os.environ.get('LLM_API_KEY', '')
        base_url = os.environ.get('LLM_BASE_URL', 'http://localhost:11434/v1')
        model = os.environ.get('LLM_MODEL_NAME', 'qwen2.5:32b')
        
        # Auto-detect provider if not specified
        if provider_name is None:
            if '11434' in base_url:
                provider = LLMProvider.OLLAMA
            elif 'openrouter.ai' in base_url:
                provider = LLMProvider.OPENROUTER
            elif 'api.openai.com' in base_url:
                provider = LLMProvider.OPENAI
            elif 'integrate.api.nvidia.com' in base_url or 'nvidia.com' in base_url:
                provider = LLMProvider.NVIDIA
            else:
                provider = LLMProvider.CUSTOM
        else:
            provider = LLMProvider(provider_name.lower())
        
        # Provider-specific defaults
        extra_config = {}
        
        if provider == LLMProvider.OLLAMA:
            # Ollama-specific: context window size
            num_ctx = int(os.environ.get('OLLAMA_NUM_CTX', '8192'))
            extra_config['num_ctx'] = num_ctx
            
        elif provider == LLMProvider.OPENROUTER:
            # OpenRouter-specific: site URL and name for ranking
            extra_config['site_url'] = os.environ.get('OPENROUTER_SITE_URL', '')
            extra_config['site_name'] = os.environ.get('OPENROUTER_SITE_NAME', 'MiroFish-Offline')
            # OpenRouter supports extra parameters like reasoning_effort
            extra_config['reasoning_effort'] = os.environ.get('OPENROUTER_REASONING_EFFORT', 'medium')
        
        elif provider == LLMProvider.NVIDIA:
            # NVIDIA NIM-specific: model presets with optimized parameters
            nvidia_model = model.lower()
            
            # Reasoning/Thinking models configuration
            reasoning_models = {
                'nvidia/nemotron-3-super-120b-a12b': {'reasoning_budget': 16384, 'enable_thinking': True},
                'qwen/qwen3.5-122b-a10b': {'enable_thinking': True},
                'qwen/qwen3.5-397b-a17b': {'enable_thinking': True},
                'z-ai/glm5': {'enable_thinking': True, 'clear_thinking': False},
                'z-ai/glm4.7': {'enable_thinking': True, 'clear_thinking': False},
                'moonshotai/kimi-k2.5': {'thinking': True},
            }
            
            # Check if current model supports reasoning/thinking
            for model_pattern, thinking_config in reasoning_models.items():
                if model_pattern in nvidia_model or any(x in nvidia_model for x in model_pattern.split('/')):
                    extra_config['chat_template_kwargs'] = thinking_config
                    if 'reasoning_budget' in thinking_config:
                        extra_config['reasoning_budget'] = thinking_config['reasoning_budget']
                    break
            
            # Model-specific temperature and token defaults
            if 'mistral-small' in nvidia_model:
                extra_config.setdefault('temperature', 0.10)
                extra_config.setdefault('top_p', 1.00)
                extra_config.setdefault('max_tokens', 16384)
                extra_config['reasoning_effort'] = 'high'
            elif 'nemotron' in nvidia_model:
                extra_config.setdefault('temperature', 1.0)
                extra_config.setdefault('top_p', 0.95)
                extra_config.setdefault('max_tokens', 16384)
            elif 'qwen' in nvidia_model:
                extra_config.setdefault('temperature', 0.60)
                extra_config.setdefault('top_p', 0.95)
                extra_config.setdefault('max_tokens', 16384)
                extra_config.setdefault('top_k', 20)
                extra_config.setdefault('presence_penalty', 0)
                extra_config.setdefault('repetition_penalty', 1)
            elif 'minimax' in nvidia_model:
                extra_config.setdefault('temperature', 1.0)
                extra_config.setdefault('top_p', 0.95)
                extra_config.setdefault('max_tokens', 8192)
            elif 'glm' in nvidia_model:
                extra_config.setdefault('temperature', 1.0)
                extra_config.setdefault('top_p', 1.0)
                extra_config.setdefault('max_tokens', 16384)
            elif 'step' in nvidia_model:
                extra_config.setdefault('temperature', 1.0)
                extra_config.setdefault('top_p', 0.9)
                extra_config.setdefault('max_tokens', 16384)
            elif 'kimi' in nvidia_model:
                extra_config.setdefault('temperature', 1.0)
                extra_config.setdefault('top_p', 1.0)
                extra_config.setdefault('max_tokens', 16384)
        
        return cls(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model=model,
            extra_config=extra_config
        )
    
    def is_ollama(self) -> bool:
        """Check if this is an Ollama provider"""
        return self.provider == LLMProvider.OLLAMA
    
    def is_openrouter(self) -> bool:
        """Check if this is an OpenRouter provider"""
        return self.provider == LLMProvider.OPENROUTER
    
    def is_nvidia(self) -> bool:
        """Check if this is a NVIDIA provider"""
        return self.provider == LLMProvider.NVIDIA
    
    def get_request_kwargs(self, **overrides) -> Dict[str, Any]:
        """
        Get request kwargs specific to this provider
        
        Args:
            **overrides: Override any default parameters
        
        Returns:
            Dictionary of kwargs for OpenAI client chat.completions.create()
        """
        kwargs = {**overrides}
        
        if self.provider == LLMProvider.OLLAMA:
            # Ollama: pass num_ctx via extra_body
            if 'num_ctx' in self.extra_config:
                if 'extra_body' not in kwargs:
                    kwargs['extra_body'] = {}
                kwargs['extra_body']['options'] = {
                    'num_ctx': self.extra_config['num_ctx']
                }
        
        elif self.provider == LLMProvider.OPENROUTER:
            # OpenRouter: add headers for ranking and optional parameters
            if 'extra_headers' not in kwargs:
                kwargs['extra_headers'] = {}
            
            if self.extra_config.get('site_url'):
                kwargs['extra_headers']['HTTP-Referer'] = self.extra_config['site_url']
            
            if self.extra_config.get('site_name'):
                kwargs['extra_headers']['X-Title'] = self.extra_config['site_name']
            
            # Add reasoning effort if specified
            if self.extra_config.get('reasoning_effort'):
                kwargs['reasoning_effort'] = self.extra_config['reasoning_effort']
        
        elif self.provider == LLMProvider.NVIDIA:
            # NVIDIA NIM: pass chat_template_kwargs, reasoning_budget, and model-specific params
            if 'chat_template_kwargs' in self.extra_config:
                if 'extra_body' not in kwargs:
                    kwargs['extra_body'] = {}
                kwargs['extra_body']['chat_template_kwargs'] = self.extra_config['chat_template_kwargs']
            
            if 'reasoning_budget' in self.extra_config:
                if 'extra_body' not in kwargs:
                    kwargs['extra_body'] = {}
                kwargs['extra_body']['reasoning_budget'] = self.extra_config['reasoning_budget']
            
            # Pass through model-specific defaults if not overridden
            for key in ['temperature', 'top_p', 'max_tokens', 'top_k', 'presence_penalty', 'repetition_penalty', 'reasoning_effort']:
                if key in self.extra_config and key not in kwargs:
                    kwargs[key] = self.extra_config[key]
        
        return kwargs
    
    def __repr__(self) -> str:
        return f"ProviderConfig(provider={self.provider.value}, model={self.model})"
