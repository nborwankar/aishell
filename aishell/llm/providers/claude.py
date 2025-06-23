"""Claude LLM provider implementation."""

import os
from typing import Optional, AsyncIterator
from ..base import LLMProvider, LLMResponse


class ClaudeLLMProvider(LLMProvider):
    """Claude LLM provider using Anthropic API."""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """Initialize Claude provider.
        
        Args:
            api_key: Anthropic API key (or ANTHROPIC_API_KEY env var)
            **kwargs: Additional configuration
        """
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        super().__init__(api_key, **kwargs)
        self._client = None
    
    @property
    def name(self) -> str:
        """Return the provider name."""
        return "claude"
    
    @property
    def default_model(self) -> str:
        """Return the default model."""
        from aishell.utils import get_env_manager
        env_manager = get_env_manager()
        return env_manager.get_var('CLAUDE_MODEL', 'claude-3-5-sonnet-20241022')
    
    def validate_config(self) -> bool:
        """Validate the provider configuration."""
        return bool(self.api_key)
    
    def _get_client(self):
        """Get or create the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. "
                    "Install with: pip install anthropic"
                )
        return self._client
    
    async def query(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> LLMResponse:
        """Send a query to Claude."""
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
            
            # Claude API parameters
            params = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens or 4096,
            }
            
            # Add any additional parameters
            params.update(kwargs)
            
            if stream:
                # For streaming, we'll collect the full response
                content = ""
                async with client.messages.stream(**params) as stream:
                    async for text in stream.text_stream:
                        content += text
                
                message = await stream.get_final_message()
                usage = {
                    "input_tokens": message.usage.input_tokens,
                    "output_tokens": message.usage.output_tokens,
                    "total_tokens": message.usage.input_tokens + message.usage.output_tokens
                }
            else:
                # Non-streaming query
                response = await client.messages.create(**params)
                content = response.content[0].text
                usage = {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                }
            
            return LLMResponse(
                content=content,
                model=model,
                provider=self.name,
                usage=usage,
                metadata={"stop_reason": response.stop_reason if not stream else None}
            )
            
        except Exception as e:
            return LLMResponse(
                content="",
                model=model or self.default_model,
                provider=self.name,
                error=f"Claude API error: {str(e)}"
            )
    
    async def stream_query(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream a query to Claude."""
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
                "max_tokens": max_tokens or 4096,
            }
            params.update(kwargs)
            
            async with client.messages.stream(**params) as stream:
                async for text in stream.text_stream:
                    yield text
                    
        except Exception as e:
            yield f"Error: Claude API error: {str(e)}"