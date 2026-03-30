"""
LLM Client Wrapper
Unified OpenAI format API calls
Supports multiple providers: Ollama, OpenRouter, NVIDIA NIM, etc.
Provider-specific optimizations (e.g., Ollama num_ctx, OpenRouter headers)
Smart rotation across providers and models based on health and task type
"""

import json
import os
import re
import time
from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..config import Config
from .llm_provider import ProviderConfig, LLMProvider
from .llm_rotator import (
    get_best_model,
    get_provider_config_for_model,
    record_llm_request,
    get_rotation_metrics
)
from .logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """LLM Client with multi-provider support and smart rotation"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        provider_name: Optional[str] = None,
        timeout: float = 300.0,
        use_rotation: bool = True,
        task_type: Optional[str] = None
    ):
        self.use_rotation = use_rotation and Config.get('ENABLE_LLM_ROTATION', True)
        self.task_type = task_type
        
        if self.use_rotation:
            # Use smart rotator to select best model
            provider_name, model, model_config = get_best_model(
                task_type=task_type,
                force_provider=provider_name
            )
            provider_config = get_provider_config_for_model(provider_name, model)
            
            self.api_key = provider_config.api_key or Config.LLM_API_KEY
            self.base_url = provider_config.base_url
            self.model = provider_config.model
            self.provider_config = provider_config
            self._selected_provider = provider_name
            self._selected_model = model
            self._model_config = model_config
        else:
            # Legacy mode: use provided or environment config
            self.api_key = api_key or Config.LLM_API_KEY
            self.base_url = base_url or Config.LLM_BASE_URL
            self.model = model or Config.LLM_MODEL_NAME
            
            # Initialize provider configuration
            self.provider_config = ProviderConfig.from_env(provider_name)
            self._selected_provider = self.provider_config.provider.value
            self._selected_model = self.model
            self._model_config = {}
        
        if not self.api_key and 'ollama' not in self.base_url.lower():
            raise ValueError("LLM_API_KEY not configured")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
        )
    
    def _record_result(self, success: bool, start_time: float):
        """Record request result for rotation metrics"""
        if self.use_rotation:
            response_time_ms = (time.time() - start_time) * 1000
            record_llm_request(
                provider=self._selected_provider,
                model=self._selected_model,
                success=success,
                response_time_ms=response_time_ms
            )

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
        stream: bool = False
    ) -> str:
        """
        Send chat request

        Args:
            messages: Message list
            temperature: Temperature parameter
            max_tokens: Max token count
            response_format: Response format (e.g., JSON mode)
            stream: Enable streaming (not yet fully supported with rotation)

        Returns:
            Model response text
        """
        # Use model-specific defaults if available
        if self._model_config:
            temperature = self._model_config.get('temperature', temperature)
            max_tokens = self._model_config.get('max_tokens', max_tokens)
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            kwargs["response_format"] = response_format

        # Apply provider-specific configurations
        provider_kwargs = self.provider_config.get_request_kwargs(**kwargs)
        
        start_time = time.time()
        try:
            response = self.client.chat.completions.create(**provider_kwargs)
            content = response.choices[0].message.content
            # Some models (like MiniMax M2.5) include thinking content in response, need to remove
            content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
            self._record_result(success=True, start_time=start_time)
            return content
        except Exception as e:
            self._record_result(success=False, start_time=start_time)
            logger.error(f"LLM request failed: {e}")
            raise

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Send chat request and return JSON

        Args:
            messages: Message list
            temperature: Temperature parameter
            max_tokens: Max token count

        Returns:
            Parsed JSON object
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        # Clean markdown code block markers
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format from LLM: {cleaned_response}")
            raise ValueError(f"Invalid JSON format from LLM: {cleaned_response}")
    
    def get_current_model_info(self) -> Dict[str, str]:
        """Get information about the currently selected model"""
        return {
            'provider': self._selected_provider,
            'model': self._selected_model,
            'base_url': self.base_url,
            'use_rotation': self.use_rotation
        }
    
    @staticmethod
    def get_rotation_metrics() -> Dict[str, Any]:
        """Get rotation metrics (static method for easy access)"""
        return get_rotation_metrics()
