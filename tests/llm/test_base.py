"""Tests for LLM base classes."""

import pytest
from unittest.mock import AsyncMock
from aishell.llm.base import LLMProvider, LLMResponse


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""
    
    @property
    def name(self) -> str:
        return "mock"
    
    @property
    def default_model(self) -> str:
        return "mock-model"
    
    async def query(self, prompt, model=None, temperature=0.7, max_tokens=None, stream=False, **kwargs):
        return LLMResponse(
            content=f"Mock response to: {prompt}",
            model=model or self.default_model,
            provider=self.name,
            usage={"total_tokens": 100}
        )
    
    async def stream_query(self, prompt, model=None, temperature=0.7, max_tokens=None, **kwargs):
        words = f"Mock response to: {prompt}".split()
        for word in words:
            yield word + " "


class TestLLMResponse:
    """Test LLMResponse class."""
    
    def test_normal_response(self):
        """Test normal response creation."""
        response = LLMResponse(
            content="Hello world",
            model="test-model",
            provider="test",
            usage={"total_tokens": 10}
        )
        
        assert response.content == "Hello world"
        assert response.model == "test-model"
        assert response.provider == "test"
        assert response.usage["total_tokens"] == 10
        assert not response.is_error
    
    def test_error_response(self):
        """Test error response creation."""
        response = LLMResponse(
            content="",
            model="test-model",
            provider="test",
            error="API key not found"
        )
        
        assert response.content == ""
        assert response.error == "API key not found"
        assert response.is_error


class TestLLMProvider:
    """Test LLMProvider base class."""
    
    def test_initialization(self):
        """Test provider initialization."""
        provider = MockLLMProvider(api_key="test-key", custom_param="value")
        
        assert provider.api_key == "test-key"
        assert provider.config["custom_param"] == "value"
        assert provider.name == "mock"
        assert provider.default_model == "mock-model"
    
    def test_validation(self):
        """Test configuration validation."""
        provider = MockLLMProvider()
        assert provider.validate_config()  # Base implementation returns True
    
    @pytest.mark.asyncio
    async def test_query(self):
        """Test query method."""
        provider = MockLLMProvider()
        
        response = await provider.query("What is 2+2?")
        
        assert response.content == "Mock response to: What is 2+2?"
        assert response.model == "mock-model"
        assert response.provider == "mock"
        assert not response.is_error
    
    @pytest.mark.asyncio
    async def test_stream_query(self):
        """Test streaming query method."""
        provider = MockLLMProvider()
        
        chunks = []
        async for chunk in provider.stream_query("Hello"):
            chunks.append(chunk)
        
        assert len(chunks) == 4  # "Mock", "response", "to:", "Hello"
        assert "".join(chunks).strip() == "Mock response to: Hello"
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        provider = MockLLMProvider()
        
        async with provider as p:
            assert p is provider
            response = await p.query("test")
            assert response.content == "Mock response to: test"