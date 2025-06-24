"""Gemini LLM provider implementation."""

import os
from typing import Optional, AsyncIterator
from ..base import LLMProvider, LLMResponse


class GeminiLLMProvider(LLMProvider):
    """Google Gemini LLM provider."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        """Initialize Gemini provider.
        
        Args:
            api_key: Google API key (or GOOGLE_API_KEY env var)
            base_url: Optional base URL for API (for Gemini-compatible services)
            **kwargs: Additional configuration
        """
        api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        super().__init__(api_key, **kwargs)
        self.base_url = base_url or os.environ.get("GEMINI_BASE_URL")
        self._client = None
    
    @property
    def name(self) -> str:
        """Return the provider name."""
        return "gemini"
    
    @property
    def default_model(self) -> str:
        """Return the default model."""
        from aishell.utils import get_env_manager
        env_manager = get_env_manager()
        return env_manager.get_var('GEMINI_MODEL', 'gemini-1.5-flash')
    
    def validate_config(self) -> bool:
        """Validate the provider configuration."""
        return bool(self.api_key)
    
    def _get_client(self):
        """Get or create the Gemini client."""
        if self._client is None:
            try:
                import google.generativeai as genai
                # Note: Google's SDK doesn't currently support custom base URLs
                # but we store it for future compatibility
                genai.configure(api_key=self.api_key)
                self._client = genai
            except ImportError:
                raise ImportError(
                    "google-generativeai package not installed. "
                    "Install with: pip install google-generativeai"
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
        """Send a query to Gemini."""
        if not self.validate_config():
            return LLMResponse(
                content="",
                model=model or self.default_model,
                provider=self.name,
                error="API key not configured"
            )
        
        try:
            genai = self._get_client()
            model_name = model or self.default_model
            
            # Get the model
            model = genai.GenerativeModel(model_name)
            
            # Configure generation parameters
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            
            # Add any additional parameters
            for key, value in kwargs.items():
                if hasattr(generation_config, key):
                    setattr(generation_config, key, value)
            
            if stream:
                # Streaming response
                response = await model.generate_content_async(
                    prompt,
                    generation_config=generation_config,
                    stream=True
                )
                
                # Collect the full response
                content = ""
                async for chunk in response:
                    if chunk.text:
                        content += chunk.text
                
                # Get usage data from the final response
                usage = None
                if hasattr(response, "usage_metadata"):
                    usage = {
                        "input_tokens": response.usage_metadata.prompt_token_count,
                        "output_tokens": response.usage_metadata.candidates_token_count,
                        "total_tokens": response.usage_metadata.total_token_count,
                    }
            else:
                # Non-streaming response
                response = await model.generate_content_async(
                    prompt,
                    generation_config=generation_config
                )
                
                content = response.text
                
                # Extract usage information if available
                usage = None
                if hasattr(response, "usage_metadata"):
                    usage = {
                        "input_tokens": response.usage_metadata.prompt_token_count,
                        "output_tokens": response.usage_metadata.candidates_token_count,
                        "total_tokens": response.usage_metadata.total_token_count,
                    }
            
            metadata = {}
            if hasattr(response, "finish_reason"):
                metadata["finish_reason"] = str(response.finish_reason)
            
            return LLMResponse(
                content=content,
                model=model_name,
                provider=self.name,
                usage=usage,
                metadata=metadata
            )
            
        except Exception as e:
            return LLMResponse(
                content="",
                model=model or self.default_model,
                provider=self.name,
                error=f"Gemini API error: {str(e)}"
            )
    
    async def stream_query(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream a query to Gemini."""
        if not self.validate_config():
            yield f"Error: API key not configured"
            return
        
        try:
            genai = self._get_client()
            model_name = model or self.default_model
            
            # Get the model
            model = genai.GenerativeModel(model_name)
            
            # Configure generation parameters
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            
            for key, value in kwargs.items():
                if hasattr(generation_config, key):
                    setattr(generation_config, key, value)
            
            # Stream the response
            response = await model.generate_content_async(
                prompt,
                generation_config=generation_config,
                stream=True
            )
            
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            yield f"Error: Gemini API error: {str(e)}"