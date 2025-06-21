"""OpenAI LLM provider implementation."""

import os
from typing import Optional, AsyncIterator
from ..base import LLMProvider, LLMResponse


class OpenAILLMProvider(LLMProvider):
    """OpenAI LLM provider."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        """Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (or OPENAI_API_KEY env var)
            base_url: Optional base URL for API (for OpenAI-compatible services)
            **kwargs: Additional configuration
        """
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        super().__init__(api_key, **kwargs)
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        self._client = None
    
    @property
    def name(self) -> str:
        """Return the provider name."""
        return "openai"
    
    @property
    def default_model(self) -> str:
        """Return the default model."""
        return "gpt-3.5-turbo"
    
    def validate_config(self) -> bool:
        """Validate the provider configuration."""
        return bool(self.api_key)
    
    def _get_client(self):
        """Get or create the OpenAI client."""
        if self._client is None:
            try:
                import openai
                self._client = openai.AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
            except ImportError:
                raise ImportError(
                    "openai package not installed. "
                    "Install with: pip install openai"
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
        """Send a query to OpenAI."""
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
            
            # OpenAI API parameters
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
                usage = {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            
            return LLMResponse(
                content=content,
                model=model,
                provider=self.name,
                usage=usage,
                metadata={"finish_reason": response.choices[0].finish_reason if not stream else None}
            )
            
        except Exception as e:
            return LLMResponse(
                content="",
                model=model or self.default_model,
                provider=self.name,
                error=f"OpenAI API error: {str(e)}"
            )
    
    async def stream_query(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream a query to OpenAI."""
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
            yield f"Error: OpenAI API error: {str(e)}"