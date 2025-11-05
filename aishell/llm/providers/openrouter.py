"""OpenRouter LLM provider implementation."""

import os
from typing import Optional, AsyncIterator, Dict, Any
from ..base import LLMProvider, LLMResponse


class OpenRouterLLMProvider(LLMProvider):
    """OpenRouter LLM provider - unified access to multiple models."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        """Initialize OpenRouter provider.
        
        Args:
            api_key: OpenRouter API key (or OPENROUTER_API_KEY env var)
            base_url: OpenRouter API URL (default: https://openrouter.ai/api/v1)
            **kwargs: Additional configuration
        """
        api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        super().__init__(api_key, **kwargs)
        self.base_url = base_url or os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self._client = None
    
    @property
    def name(self) -> str:
        """Return the provider name."""
        return "openrouter"
    
    @property
    def default_model(self) -> str:
        """Return the default model."""
        from aishell.utils import get_env_manager
        env_manager = get_env_manager()
        # Default to Claude 3.5 Sonnet via OpenRouter
        return env_manager.get_var('OPENROUTER_MODEL', 'anthropic/claude-3.5-sonnet') or 'anthropic/claude-3.5-sonnet'
    
    def validate_config(self) -> bool:
        """Validate the provider configuration."""
        return bool(self.api_key)
    
    def _get_client(self):
        """Get or create the OpenAI-compatible client for OpenRouter."""
        if self._client is None:
            try:
                import openai
                self._client = openai.AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    default_headers={
                        "HTTP-Referer": "https://github.com/nborwankar/aishell",
                        "X-Title": "AIShell"
                    }
                )
            except ImportError:
                raise ImportError(
                    "openai package not installed. "
                    "Install with: pip install openai"
                )
        return self._client
    
    def _get_model_info(self, model: str) -> Dict[str, Any]:
        """Get model-specific information and pricing."""
        # Common models available on OpenRouter with their context windows
        model_info = {
            'anthropic/claude-3.5-sonnet': {'context': 200000, 'provider': 'Anthropic'},
            'anthropic/claude-3-opus': {'context': 200000, 'provider': 'Anthropic'},
            'anthropic/claude-3-haiku': {'context': 200000, 'provider': 'Anthropic'},
            'openai/gpt-4-turbo': {'context': 128000, 'provider': 'OpenAI'},
            'openai/gpt-4': {'context': 8192, 'provider': 'OpenAI'},
            'openai/gpt-3.5-turbo': {'context': 16385, 'provider': 'OpenAI'},
            'google/gemini-pro': {'context': 32768, 'provider': 'Google'},
            'google/gemini-pro-1.5': {'context': 1000000, 'provider': 'Google'},
            'meta-llama/llama-3-70b-instruct': {'context': 8192, 'provider': 'Meta'},
            'mistralai/mistral-large': {'context': 32768, 'provider': 'Mistral'},
        }
        return model_info.get(model, {'context': 4096, 'provider': 'Unknown'})
    
    async def query(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> LLMResponse:
        """Send a query to OpenRouter."""
        if not self.validate_config():
            return LLMResponse(
                content="",
                model=model or self.default_model,
                provider=self.name,
                error="API key not configured"
            )
        
        try:
            client = self._get_client()
            model = model or self.default_model
            
            # Get model info for metadata
            model_info = self._get_model_info(model)
            
            # OpenRouter uses OpenAI-compatible API
            params = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            }
            
            if max_tokens:
                params["max_tokens"] = max_tokens
            
            # Add any additional parameters
            params.update(kwargs)
            
            if stream:
                # For streaming, collect the full response
                content = ""
                stream_response = await client.chat.completions.create(**params, stream=True)
                
                async for chunk in stream_response:
                    if chunk.choices[0].delta.content:
                        content += chunk.choices[0].delta.content
                
                # We don't have usage data in streaming mode
                usage = None
            else:
                # Non-streaming query
                response = await client.chat.completions.create(**params)
                content = response.choices[0].message.content
                
                # OpenRouter returns usage in the same format as OpenAI
                if hasattr(response, 'usage'):
                    usage = {
                        "input_tokens": response.usage.prompt_tokens,
                        "output_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                else:
                    usage = None
            
            return LLMResponse(
                content=content,
                model=model,
                provider=self.name,
                usage=usage,
                metadata={
                    "finish_reason": response.choices[0].finish_reason if not stream else None,
                    "model_provider": model_info['provider'],
                    "context_window": model_info['context']
                }
            )
            
        except Exception as e:
            return LLMResponse(
                content="",
                model=model or self.default_model,
                provider=self.name,
                error=f"OpenRouter API error: {str(e)}"
            )
    
    async def stream_query(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream a query to OpenRouter."""
        if not self.validate_config():
            yield f"Error: API key not configured"
            return
        
        try:
            client = self._get_client()
            model = model or self.default_model
            
            params = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "stream": True,
            }
            
            if max_tokens:
                params["max_tokens"] = max_tokens
                
            params.update(kwargs)
            
            stream = await client.chat.completions.create(**params)
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            yield f"Error: OpenRouter API error: {str(e)}"