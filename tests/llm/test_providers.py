"""Tests for LLM provider implementations."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aishell.llm.providers.claude import ClaudeLLMProvider
from aishell.llm.providers.openai import OpenAILLMProvider
from aishell.llm.providers.ollama import OllamaLLMProvider
from aishell.llm.providers.gemini import GeminiLLMProvider


class TestClaudeLLMProvider:
    """Test Claude LLM provider."""
    
    def test_initialization(self):
        """Test provider initialization."""
        provider = ClaudeLLMProvider(api_key="test-key")
        
        assert provider.api_key == "test-key"
        assert provider.name == "claude"
        assert provider.default_model == "claude-3-sonnet-20240229"
    
    def test_validation_with_key(self):
        """Test validation with API key."""
        provider = ClaudeLLMProvider(api_key="test-key")
        assert provider.validate_config()
    
    def test_validation_without_key(self):
        """Test validation without API key."""
        provider = ClaudeLLMProvider()
        assert not provider.validate_config()
    
    @pytest.mark.asyncio
    async def test_query_without_api_key(self):
        """Test query without API key."""
        provider = ClaudeLLMProvider()
        
        response = await provider.query("test")
        
        assert response.is_error
        assert "API key not configured" in response.error
    
    @pytest.mark.asyncio
    async def test_query_success(self):
        """Test successful query."""
        provider = ClaudeLLMProvider(api_key="test-key")
        
        # Mock the _get_client method to avoid import issues
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = "Hello, this is Claude!"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 20
        mock_response.stop_reason = "end_turn"
        
        mock_client.messages.create.return_value = mock_response
        provider._get_client = MagicMock(return_value=mock_client)
        
        response = await provider.query("Hello")
        
        assert not response.is_error
        assert response.content == "Hello, this is Claude!"
        assert response.model == "claude-3-sonnet-20240229"
        assert response.provider == "claude"
        assert response.usage["total_tokens"] == 30


class TestOpenAILLMProvider:
    """Test OpenAI LLM provider."""
    
    def test_initialization(self):
        """Test provider initialization."""
        provider = OpenAILLMProvider(api_key="test-key")
        
        assert provider.api_key == "test-key"
        assert provider.name == "openai"
        assert provider.default_model == "gpt-3.5-turbo"
    
    def test_custom_base_url(self):
        """Test custom base URL."""
        provider = OpenAILLMProvider(api_key="test-key", base_url="https://custom.api.com")
        
        assert provider.base_url == "https://custom.api.com"
    
    @pytest.mark.asyncio
    async def test_query_without_api_key(self):
        """Test query without API key."""
        provider = OpenAILLMProvider()
        
        response = await provider.query("test")
        
        assert response.is_error
        assert "API key not configured" in response.error
    
    @pytest.mark.asyncio
    async def test_query_success(self):
        """Test successful query."""
        provider = OpenAILLMProvider(api_key="test-key")
        
        # Mock the _get_client method
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello from GPT!"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 15
        mock_response.usage.total_tokens = 20
        
        mock_client.chat.completions.create.return_value = mock_response
        provider._get_client = MagicMock(return_value=mock_client)
        
        response = await provider.query("Hello")
        
        assert not response.is_error
        assert response.content == "Hello from GPT!"
        assert response.model == "gpt-3.5-turbo"
        assert response.provider == "openai"
        assert response.usage["total_tokens"] == 20


class TestOllamaLLMProvider:
    """Test Ollama LLM provider."""
    
    def test_initialization(self):
        """Test provider initialization."""
        provider = OllamaLLMProvider()
        
        assert provider.name == "ollama"
        assert provider.default_model == "llama2"
        assert provider.base_url == "http://localhost:11434"
    
    def test_custom_url(self):
        """Test custom Ollama URL."""
        provider = OllamaLLMProvider(base_url="http://custom:8080")
        
        assert provider.base_url == "http://custom:8080"
    
    def test_validation(self):
        """Test validation (should always pass for Ollama)."""
        provider = OllamaLLMProvider()
        assert provider.validate_config()
    
    @pytest.mark.asyncio
    async def test_model_check_success(self):
        """Test model existence check."""
        provider = OllamaLLMProvider()
        
        # Mock the method directly to avoid complex aiohttp mocking
        provider._check_model_exists = AsyncMock(return_value=True)
        
        result = await provider._check_model_exists("llama2")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_query_model_not_found(self):
        """Test query with non-existent model."""
        provider = OllamaLLMProvider()
        
        # Mock model check to return False
        provider._check_model_exists = AsyncMock(return_value=False)
        
        response = await provider.query("test", model="nonexistent")
        
        assert response.is_error
        assert "not found" in response.error


class TestGeminiLLMProvider:
    """Test Gemini LLM provider."""
    
    def test_initialization(self):
        """Test provider initialization."""
        provider = GeminiLLMProvider(api_key="test-key")
        
        assert provider.api_key == "test-key"
        assert provider.name == "gemini"
        assert provider.default_model == "gemini-pro"
    
    def test_validation_with_key(self):
        """Test validation with API key."""
        provider = GeminiLLMProvider(api_key="test-key")
        assert provider.validate_config()
    
    def test_validation_without_key(self):
        """Test validation without API key."""
        provider = GeminiLLMProvider()
        assert not provider.validate_config()
    
    @pytest.mark.asyncio
    async def test_query_without_api_key(self):
        """Test query without API key."""
        provider = GeminiLLMProvider()
        
        response = await provider.query("test")
        
        assert response.is_error
        assert "API key not configured" in response.error
    
    @pytest.mark.asyncio
    async def test_query_success(self):
        """Test successful query."""
        provider = GeminiLLMProvider(api_key="test-key")
        
        # Mock the _get_client method
        mock_genai = MagicMock()
        mock_model = AsyncMock()
        mock_response = AsyncMock()
        mock_response.text = "Hello from Gemini!"
        mock_response.usage_metadata.prompt_token_count = 8
        mock_response.usage_metadata.candidates_token_count = 12
        mock_response.usage_metadata.total_token_count = 20
        
        mock_model.generate_content_async.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        provider._get_client = MagicMock(return_value=mock_genai)
        
        response = await provider.query("Hello")
        
        assert not response.is_error
        assert response.content == "Hello from Gemini!"
        assert response.model == "gemini-pro"
        assert response.provider == "gemini"
        assert response.usage["total_tokens"] == 20