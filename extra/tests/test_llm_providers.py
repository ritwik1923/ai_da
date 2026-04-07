"""
Test LLM providers (OpenAI and Company GenAI API)
"""
import pytest
from app.utils.custom_llm import CompanyGenAILLM
from app.core.config import settings
from langchain_core.messages import HumanMessage


class TestCompanyGenAILLM:
    """Test Company GenAI API integration"""
    
    @pytest.mark.skipif(
        not settings.COMPANY_API_KEY or settings.LLM_PROVIDER != "company",
        reason="Company API key not configured"
    )
    def test_company_llm_initialization(self):
        """Test that Company LLM can be initialized"""
        llm = CompanyGenAILLM(
            api_key=settings.COMPANY_API_KEY,
            model=settings.COMPANY_MODEL,
            user_id=settings.COMPANY_USER_ID
        )
        
        assert llm is not None
        assert llm._llm_type == "company_genai"
        assert llm.model == settings.COMPANY_MODEL
    
    @pytest.mark.skipif(
        not settings.COMPANY_API_KEY or settings.LLM_PROVIDER != "company",
        reason="Company API key not configured"
    )
    def test_company_llm_simple_query(self):
        """Test simple query to Company API"""
        llm = CompanyGenAILLM(
            api_key=settings.COMPANY_API_KEY,
            model=settings.COMPANY_MODEL,
            user_id=settings.COMPANY_USER_ID,
            temperature=0
        )
        
        messages = [HumanMessage(content="What is 2+2? Answer with just the number.")]
        
        result = llm._generate(messages)
        
        assert result is not None
        assert len(result.generations) > 0
        assert "4" in result.generations[0].message.content
    
    @pytest.mark.skipif(
        not settings.COMPANY_API_KEY or settings.LLM_PROVIDER != "company",
        reason="Company API key not configured"
    )
    def test_company_llm_code_generation(self):
        """Test code generation capability"""
        llm = CompanyGenAILLM(
            api_key=settings.COMPANY_API_KEY,
            model=settings.COMPANY_MODEL,
            user_id=settings.COMPANY_USER_ID,
            temperature=0
        )
        
        messages = [HumanMessage(
            content="Write a Python function to calculate the sum of a list. Just show the code, no explanation."
        )]
        
        result = llm._generate(messages)
        response = result.generations[0].message.content
        
        assert "def" in response.lower()
        assert "sum" in response.lower()


class TestLLMProviderSwitch:
    """Test switching between LLM providers"""
    
    def test_provider_configuration(self):
        """Test that LLM provider is correctly configured"""
        assert settings.LLM_PROVIDER in ["openai", "company"]
        
        if settings.LLM_PROVIDER == "openai":
            assert settings.OPENAI_API_KEY, "OpenAI API key not set"
        elif settings.LLM_PROVIDER == "company":
            assert settings.COMPANY_API_KEY, "Company API key not set"
    
    def test_model_configuration(self):
        """Test that appropriate model is configured"""
        if settings.LLM_PROVIDER == "openai":
            assert settings.OPENAI_MODEL
            assert "gpt" in settings.OPENAI_MODEL.lower()
        elif settings.LLM_PROVIDER == "company":
            assert settings.COMPANY_MODEL
            # Verify it's a valid company model
            valid_models = [
                "ChatGPT4o", "ChatGPT4o-mini", "VertexGemini",
                "Claude-Sonnet-4", "Gemini-2_5-Flash"
            ]
            # Model should contain at least part of a valid model name
            assert any(m.lower() in settings.COMPANY_MODEL.lower() for m in valid_models)
