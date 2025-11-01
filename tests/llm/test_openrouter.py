"""Tests for OpenRouter LLM provider."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aishell.llm.providers.openrouter import OpenRouterLLMProvider


class TestOpenRouterLLMProvider:
    """Test the OpenRouter LLM provider."""
    
    def test_initialization_default(self):
        """Test provider initialization with defaults."""
        provider = OpenRouterLLMProvider()
        assert provider.api_key is None
        assert provider.base_url == "https://openrouter.ai/api/v1"
        assert provider.name == "openrouter"
    
    def test_initialization_with_params(self):
        """Test provider initialization with parameters."""
        provider = OpenRouterLLMProvider(
            api_key="test-key",
            base_url="https://custom.openrouter.ai/api/v1"
        )
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://custom.openrouter.ai/api/v1"
    
    def test_validate_config_no_key(self):
        """Test configuration validation without API key."""
        provider = OpenRouterLLMProvider()
        assert not provider.validate_config()
    
    def test_validate_config_with_key(self):
        """Test configuration validation with API key."""
        provider = OpenRouterLLMProvider(api_key="test-key")
        assert provider.validate_config()
    
    def test_model_metadata(self):
        """Test model metadata functionality."""
        provider = OpenRouterLLMProvider()
        
        # Test getting model info for known model
        model_info = provider._get_model_info("anthropic/claude-3.5-sonnet")
        assert model_info['context'] == 200000
        assert model_info['provider'] == 'Anthropic'
        
        # Test getting model info for unknown model
        model_info = provider._get_model_info("unknown/model")
        assert model_info['context'] == 4096
        assert model_info['provider'] == 'Unknown'
    
    @pytest.mark.asyncio
    async def test_query_no_api_key(self):
        """Test query without API key returns error."""
        provider = OpenRouterLLMProvider()
        response = await provider.query("Test query")
        
        assert response.is_error
        assert "API key not configured" in response.error
        assert response.provider == "openrouter"
    
    @pytest.mark.asyncio
    async def test_stream_query_no_api_key(self):
        """Test stream query without API key returns error."""
        provider = OpenRouterLLMProvider()
        
        chunks = []
        async for chunk in provider.stream_query("Test query"):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert "API key not configured" in chunks[0]