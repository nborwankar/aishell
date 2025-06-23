"""Ollama LLM provider implementation."""

import os
import json
import aiohttp
from typing import Optional, AsyncIterator, Dict, Any
from ..base import LLMProvider, LLMResponse


class OllamaLLMProvider(LLMProvider):
    """Ollama LLM provider for local models."""
    
    def __init__(self, base_url: Optional[str] = None, **kwargs):
        """Initialize Ollama provider.
        
        Args:
            base_url: Ollama API base URL (default: http://localhost:11434)
            **kwargs: Additional configuration
        """
        super().__init__(api_key=None, **kwargs)
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    
    @property
    def name(self) -> str:
        """Return the provider name."""
        return "ollama"
    
    @property
    def default_model(self) -> str:
        """Return the default model."""
        from aishell.utils import get_env_manager
        env_manager = get_env_manager()
        return env_manager.get_var('OLLAMA_MODEL', 'llama3.2')
    
    def validate_config(self) -> bool:
        """Validate the provider configuration."""
        # Ollama doesn't require an API key
        return True
    
    async def _check_model_exists(self, model: str) -> bool:
        """Check if a model exists in Ollama."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [m["name"] for m in data.get("models", [])]
                        return model in models
        except Exception:
            return False
        return False
    
    async def query(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> LLMResponse:
        """Send a query to Ollama."""
        model = model or self.default_model
        
        try:
            # Check if model exists
            if not await self._check_model_exists(model):
                return LLMResponse(
                    content="",
                    model=model,
                    provider=self.name,
                    error=f"Model '{model}' not found. Pull it with: ollama pull {model}"
                )
            
            # Prepare the request
            data = {
                "model": model,
                "prompt": prompt,
                "stream": stream,
                "options": {
                    "temperature": temperature,
                }
            }
            
            if max_tokens:
                data["options"]["num_predict"] = max_tokens
            
            # Add any additional options
            if "options" in kwargs:
                data["options"].update(kwargs["options"])
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=300)  # 5 minute timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return LLMResponse(
                            content="",
                            model=model,
                            provider=self.name,
                            error=f"Ollama API error: {error_text}"
                        )
                    
                    if stream:
                        # For streaming, collect the full response
                        content = ""
                        total_duration = 0
                        eval_count = 0
                        
                        async for line in response.content:
                            if line:
                                try:
                                    chunk = json.loads(line)
                                    if "response" in chunk:
                                        content += chunk["response"]
                                    if "total_duration" in chunk:
                                        total_duration = chunk["total_duration"]
                                    if "eval_count" in chunk:
                                        eval_count = chunk["eval_count"]
                                except json.JSONDecodeError:
                                    continue
                        
                        usage = {
                            "output_tokens": eval_count,
                            "total_tokens": eval_count,  # Ollama doesn't provide input tokens
                        }
                        
                        metadata = {
                            "total_duration_ms": total_duration // 1_000_000 if total_duration else None
                        }
                    else:
                        # Non-streaming response
                        result = await response.json()
                        content = result.get("response", "")
                        
                        usage = {
                            "output_tokens": result.get("eval_count", 0),
                            "total_tokens": result.get("eval_count", 0),
                        }
                        
                        metadata = {
                            "total_duration_ms": result.get("total_duration", 0) // 1_000_000,
                            "model": result.get("model"),
                        }
                    
                    return LLMResponse(
                        content=content,
                        model=model,
                        provider=self.name,
                        usage=usage,
                        metadata=metadata
                    )
                    
        except aiohttp.ClientError as e:
            return LLMResponse(
                content="",
                model=model,
                provider=self.name,
                error=f"Connection error: {str(e)}. Is Ollama running?"
            )
        except Exception as e:
            return LLMResponse(
                content="",
                model=model,
                provider=self.name,
                error=f"Ollama error: {str(e)}"
            )
    
    async def stream_query(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream a query to Ollama."""
        model = model or self.default_model
        
        try:
            # Check if model exists
            if not await self._check_model_exists(model):
                yield f"Error: Model '{model}' not found. Pull it with: ollama pull {model}"
                return
            
            data = {
                "model": model,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": temperature,
                }
            }
            
            if max_tokens:
                data["options"]["num_predict"] = max_tokens
                
            if "options" in kwargs:
                data["options"].update(kwargs["options"])
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        yield f"Error: Ollama API error: {error_text}"
                        return
                    
                    async for line in response.content:
                        if line:
                            try:
                                chunk = json.loads(line)
                                if "response" in chunk:
                                    yield chunk["response"]
                            except json.JSONDecodeError:
                                continue
                                
        except aiohttp.ClientError as e:
            yield f"Error: Connection error: {str(e)}. Is Ollama running?"
        except Exception as e:
            yield f"Error: {str(e)}"