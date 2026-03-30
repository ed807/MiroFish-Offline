"""
Smart LLM Provider Rotation System
Automatically rotates between providers and models based on:
- Success/failure rates
- Response times
- Task requirements
- Cost optimization (prefer free models when possible)
"""

import os
import time
import random
import threading
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from app.llm_providers_config import PROVIDERS, ROTATION_CONFIG, TASK_ROUTING
from .llm_provider import LLMProvider, ProviderConfig
from .logger import get_logger

logger = get_logger(__name__)


class ModelStatus(Enum):
    """Model health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    COOLDOWN = "cooldown"


@dataclass
class ModelStats:
    """Statistics for a specific model"""
    provider: str
    model_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    avg_response_time_ms: float = 0.0
    total_response_time_ms: float = 0.0
    status: ModelStatus = ModelStatus.HEALTHY
    cooldown_until: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests
    
    @property
    def failure_rate(self) -> float:
        return 1.0 - self.success_rate
    
    def record_success(self, response_time_ms: float):
        """Record a successful request"""
        self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_failures = 0
        self.last_success_time = datetime.now()
        
        # Update average response time
        self.total_response_time_ms += response_time_ms
        self.avg_response_time_ms = self.total_response_time_ms / self.total_requests
        
        # Restore health if was degraded
        if self.status == ModelStatus.DEGRADED and self.consecutive_failures == 0:
            self.status = ModelStatus.HEALTHY
    
    def record_failure(self):
        """Record a failed request"""
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self.last_failure_time = datetime.now()
        
        # Update status based on consecutive failures
        max_failures = ROTATION_CONFIG.get('max_consecutive_failures', 3)
        if self.consecutive_failures >= max_failures:
            self.status = ModelStatus.UNHEALTHY
            cooldown_seconds = ROTATION_CONFIG.get('provider_cooldown_seconds', 60)
            self.cooldown_until = datetime.now() + timedelta(seconds=cooldown_seconds)
            logger.warning(
                f"Model {self.provider}/{self.model_name} entered cooldown until {self.cooldown_until}"
            )
    
    def is_available(self) -> bool:
        """Check if model is available for use"""
        if self.status == ModelStatus.UNHEALTHY:
            if self.cooldown_until and datetime.now() > self.cooldown_until:
                # Cooldown expired, try again
                self.status = ModelStatus.DEGRADED
                self.consecutive_failures = 0
                self.cooldown_until = None
                return True
            return False
        return True


class SmartLLMRotator:
    """
    Smart LLM provider and model rotator
    Automatically selects the best model based on health, task type, and cost
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.model_stats: Dict[str, ModelStats] = {}
        self._stats_lock = threading.Lock()
        
        # Initialize stats for all configured models
        self._initialize_model_stats()
        
        # Start health check thread if enabled
        if ROTATION_CONFIG.get('health_check', {}).get('enabled', False):
            self._start_health_checker()
        
        logger.info("SmartLLMRotator initialized with smart rotation enabled")
    
    def _initialize_model_stats(self):
        """Initialize statistics for all configured models"""
        for provider_name, provider_config in PROVIDERS.items():
            for model_name, model_config in provider_config.get('models', {}).items():
                key = f"{provider_name}/{model_name}"
                self.model_stats[key] = ModelStats(
                    provider=provider_name,
                    model_name=model_name
                )
                logger.debug(f"Initialized stats for {key}")
    
    def _get_or_create_stats(self, provider: str, model: str) -> ModelStats:
        """Get or create stats for a model"""
        key = f"{provider}/{model}"
        with self._stats_lock:
            if key not in self.model_stats:
                self.model_stats[key] = ModelStats(provider=provider, model_name=model)
            return self.model_stats[key]
    
    def select_model(
        self,
        task_type: Optional[str] = None,
        preferred_tags: Optional[List[str]] = None,
        avoid_free_only: bool = False,
        force_provider: Optional[str] = None
    ) -> Tuple[str, str, Dict[str, Any]]:
        """
        Select the best model based on task requirements and health status
        
        Args:
            task_type: Type of task (e.g., 'simulation_chat', 'report_generation')
            preferred_tags: Preferred model tags
            avoid_free_only: Avoid free-only models
            force_provider: Force a specific provider
            
        Returns:
            Tuple of (provider_name, model_name, model_config)
        """
        # Apply task-specific routing if provided
        if task_type and task_type in TASK_ROUTING:
            task_config = TASK_ROUTING[task_type]
            if preferred_tags is None:
                preferred_tags = task_config.get('preferred_tags', [])
            if 'avoid_free_only' not in locals():
                avoid_free_only = task_config.get('avoid_free_only', False)
            if force_provider is None:
                force_provider = task_config.get('force_provider')
        
        strategy = ROTATION_CONFIG.get('selection_strategy', 'priority')
        
        # Filter available models
        candidates = []
        for provider_name, provider_config in PROVIDERS.items():
            # Skip if force_provider is set
            if force_provider and provider_name != force_provider:
                continue
            
            # Check if provider API key is available
            api_key_env = provider_config.get('api_key_env')
            if api_key_env and not os.environ.get(api_key_env):
                logger.debug(f"Skipping {provider_name}: API key not configured")
                continue
            
            for model_name, model_config in provider_config.get('models', {}).items():
                stats = self._get_or_create_stats(provider_name, model_name)
                
                # Skip unavailable models
                if not stats.is_available():
                    continue
                
                # Apply filters
                model_tags = model_config.get('tags', [])
                
                if avoid_free_only and 'free' in model_tags and len(model_tags) == 1:
                    continue
                
                if preferred_tags:
                    # Score based on tag matches
                    tag_score = len(set(preferred_tags) & set(model_tags))
                    if tag_score == 0 and any(t in preferred_tags for t in ['free', 'local']):
                        # Skip if no tag match and we prefer specific types
                        continue
                else:
                    tag_score = 0
                
                candidates.append((provider_name, model_name, model_config, tag_score, stats))
        
        if not candidates:
            # Fallback: try any available model
            logger.warning("No candidates found with filters, falling back to any available model")
            for provider_name, provider_config in PROVIDERS.items():
                api_key_env = provider_config.get('api_key_env')
                if api_key_env and not os.environ.get(api_key_env):
                    continue
                
                for model_name, model_config in provider_config.get('models', {}).items():
                    stats = self._get_or_create_stats(provider_name, model_name)
                    if stats.is_available():
                        return provider_name, model_name, model_config
            
            # Ultimate fallback: use environment-configured model
            logger.error("No models available, using environment default")
            return self._get_fallback_from_env()
        
        # Select based on strategy
        if strategy == 'priority':
            # Sort by priority (lower is better), then by tag score, then by success rate
            candidates.sort(key=lambda x: (
                x[2].get('priority', 999),
                -x[3],  # Negative tag score (higher is better)
                -x[4].success_rate  # Negative success rate (higher is better)
            ))
        elif strategy == 'random':
            random.shuffle(candidates)
        elif strategy == 'round_robin':
            # Simple round-robin (could be enhanced with state tracking)
            pass
        elif strategy == 'least_loaded':
            # Sort by current load (approximated by recent request count)
            weights = ROTATION_CONFIG.get('weights', {})
            candidates.sort(key=lambda x: (
                x[4].total_requests * weights.get(x[0], 1.0),
            ))
        
        selected = candidates[0]
        provider_name, model_name, model_config = selected[0], selected[1], selected[2]
        
        logger.info(f"Selected model: {provider_name}/{model_name} (strategy={strategy})")
        return provider_name, model_name, model_config
    
    def _get_fallback_from_env(self) -> Tuple[str, str, Dict[str, Any]]:
        """Get fallback model from environment variables"""
        base_url = os.environ.get('LLM_BASE_URL', 'http://localhost:11434/v1')
        model = os.environ.get('LLM_MODEL_NAME', 'qwen2.5:32b')
        
        if '11434' in base_url:
            return 'ollama', model, {'temperature': 0.7, 'top_p': 0.95, 'max_tokens': 8192}
        elif 'openrouter.ai' in base_url:
            return 'openrouter', model, {'temperature': 0.7, 'top_p': 0.95, 'max_tokens': 8192}
        elif 'nvidia.com' in base_url:
            return 'nvidia', model, {'temperature': 0.7, 'top_p': 0.95, 'max_tokens': 8192}
        else:
            return 'custom', model, {'temperature': 0.7, 'top_p': 0.95, 'max_tokens': 8192}
    
    def record_request(
        self,
        provider: str,
        model: str,
        success: bool,
        response_time_ms: float = 0.0
    ):
        """Record a request result"""
        stats = self._get_or_create_stats(provider, model)
        
        if success:
            stats.record_success(response_time_ms)
            logger.debug(f"Recorded success for {provider}/{model} ({response_time_ms:.2f}ms)")
        else:
            stats.record_failure()
            logger.warning(f"Recorded failure for {provider}/{model}")
    
    def get_provider_config(self, provider_name: str, model_name: str) -> ProviderConfig:
        """
        Create a ProviderConfig for the selected model
        
        Args:
            provider_name: Provider name
            model_name: Model name
            
        Returns:
            ProviderConfig instance
        """
        provider_config = PROVIDERS.get(provider_name)
        if not provider_config:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        model_config = provider_config.get('models', {}).get(model_name, {})
        api_key_env = provider_config.get('api_key_env')
        api_key = os.environ.get(api_key_env, '') if api_key_env else ''
        
        # Build extra config from model config
        extra_config = {}
        for key in ['temperature', 'top_p', 'max_tokens', 'top_k', 'presence_penalty', 
                    'repetition_penalty', 'reasoning_effort', 'chat_template_kwargs',
                    'reasoning_budget', 'num_ctx']:
            if key in model_config:
                extra_config[key] = model_config[key]
        
        # Add provider-specific headers
        if 'headers' in provider_config:
            extra_config['headers'] = provider_config['headers']
        
        return ProviderConfig(
            provider=LLMProvider(provider_name.lower()),
            api_key=api_key,
            base_url=provider_config['base_url'],
            model=model_name,
            extra_config=extra_config
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics for all models"""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'models': {},
            'summary': {
                'total_models': len(self.model_stats),
                'healthy': 0,
                'degraded': 0,
                'unhealthy': 0,
                'avg_success_rate': 0.0
            }
        }
        
        total_success_rate = 0.0
        for key, stats in self.model_stats.items():
            if stats.total_requests > 0:
                total_success_rate += stats.success_rate
            
            metrics['models'][key] = {
                'status': stats.status.value,
                'success_rate': round(stats.success_rate, 3),
                'total_requests': stats.total_requests,
                'consecutive_failures': stats.consecutive_failures,
                'avg_response_time_ms': round(stats.avg_response_time_ms, 2),
                'last_failure': stats.last_failure_time.isoformat() if stats.last_failure_time else None,
                'last_success': stats.last_success_time.isoformat() if stats.last_success_time else None
            }
            
            if stats.status == ModelStatus.HEALTHY:
                metrics['summary']['healthy'] += 1
            elif stats.status == ModelStatus.DEGRADED:
                metrics['summary']['degraded'] += 1
            else:
                metrics['summary']['unhealthy'] += 1
        
        if self.model_stats:
            metrics['summary']['avg_success_rate'] = round(
                total_success_rate / len(self.model_stats), 3
            )
        
        return metrics
    
    def _start_health_checker(self):
        """Start background health check thread"""
        def health_check_loop():
            interval = ROTATION_CONFIG.get('health_check', {}).get('interval_seconds', 300)
            while True:
                time.sleep(interval)
                self._run_health_check()
        
        thread = threading.Thread(target=health_check_loop, daemon=True)
        thread.start()
        logger.info("Health checker started")
    
    def _run_health_check(self):
        """Run health checks on all providers"""
        logger.debug("Running health checks...")
        # TODO: Implement actual health check logic
        # This would send test prompts to each provider and measure response
    
    def reset_stats(self, provider: Optional[str] = None, model: Optional[str] = None):
        """Reset statistics for specific model(s)"""
        with self._stats_lock:
            if provider and model:
                key = f"{provider}/{model}"
                if key in self.model_stats:
                    self.model_stats[key] = ModelStats(provider=provider, model_name=model)
            elif provider:
                for key in list(self.model_stats.keys()):
                    if key.startswith(f"{provider}/"):
                        stats = self.model_stats[key]
                        self.model_stats[key] = ModelStats(provider=provider, model_name=stats.model_name)
            else:
                self.model_stats.clear()
                self._initialize_model_stats()
        
        logger.info(f"Reset stats for provider={provider}, model={model}")


# Global singleton instance
rotator = SmartLLMRotator()


def get_best_model(task_type: Optional[str] = None, **kwargs) -> Tuple[str, str, Dict[str, Any]]:
    """Convenience function to get the best model for a task"""
    return rotator.select_model(task_type=task_type, **kwargs)


def get_provider_config_for_model(provider: str, model: str) -> ProviderConfig:
    """Get ProviderConfig for a specific model"""
    return rotator.get_provider_config(provider, model)


def record_llm_request(provider: str, model: str, success: bool, response_time_ms: float = 0.0):
    """Record a request result"""
    rotator.record_request(provider, model, success, response_time_ms)


def get_rotation_metrics() -> Dict[str, Any]:
    """Get current rotation metrics"""
    return rotator.get_metrics()
