"""
Custom LLM wrapper for company's GenAI API
Compatible with LangChain framework
"""
from typing import Any, List, Optional, Dict
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.callbacks import CallbackManagerForLLMRun
import requests
import uuid
from pydantic import Field


class CompanyGenAILLM(BaseChatModel):
    """
    Custom LangChain LLM wrapper for company's GenAI service.
    
    Usage:
        llm = CompanyGenAILLM(
            api_key="your-api-key",
            model="ChatGPT4o",
            user_id="your-email@motorolasolutions.com"
        )
    """
    
    api_key: str
    model: str = "ChatGPT4o"
    user_id: Optional[str] = None
    base_url: str = "https://genai-service.stage.commandcentral.com/app-gateway"
    temperature: float = 0.7
    max_tokens: int = 800
    top_p: float = 1.0
    frequency_penalty: float = 0
    presence_penalty: float = 0
    session_id: Optional[str] = None
    client_id: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True
    
    @property
    def _llm_type(self) -> str:
        return "company_genai"
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate chat response from the company GenAI API."""
        
        # Convert LangChain messages to API format
        system_message = ""
        prompt = ""
        
        for message in messages:
            if isinstance(message, SystemMessage):
                system_message = message.content
            elif isinstance(message, HumanMessage):
                prompt = message.content
            elif isinstance(message, AIMessage):
                # For conversation history, we'd need to maintain session
                pass
        
        # Prepare request
        headers = {
            "x-msi-genai-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        if self.client_id:
            headers["X-msi-genai-client"] = self.client_id
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "modelConfig": {
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "top_p": self.top_p,
                "frequency_penalty": self.frequency_penalty,
                "presence_penalty": self.presence_penalty
            }
        }
        
        # Add optional fields
        if self.user_id:
            payload["userId"] = self.user_id
        
        if system_message:
            payload["system"] = system_message
        
        if self.session_id:
            payload["sessionId"] = self.session_id
        
        # Make API call
        try:
            response = requests.post(
                f"{self.base_url}/api/v2/chat",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            
            if not result.get("status"):
                raise ValueError(f"API Error: {result.get('msg', 'Unknown error')}")
            
            # Update session ID for future calls
            if result.get("sessionId"):
                self.session_id = result["sessionId"]
            
            # Extract response message
            message_content = result.get("msg", "")
            
            # Create ChatResult
            message = AIMessage(content=message_content)
            generation = ChatGeneration(message=message)
            
            return ChatResult(generations=[generation])
            
        except requests.exceptions.RequestException as e:
            raise ValueError(f"API request failed: {str(e)}")
    
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Async generation - not implemented, falls back to sync."""
        return self._generate(messages, stop, run_manager, **kwargs)


class OpenAICompatibleLLM(BaseChatModel):
    """
    Wrapper to use company's ChatGPT models with OpenAI-compatible interface.
    This allows seamless switching between company API and OpenAI.
    """
    
    api_key: str
    model: str = "ChatGPT4o"
    user_id: Optional[str] = None
    base_url: str = "https://genai-service.stage.commandcentral.com/app-gateway"
    temperature: float = 0
    max_tokens: int = 800
    
    class Config:
        arbitrary_types_allowed = True
    
    @property
    def _llm_type(self) -> str:
        return "openai_compatible"
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Use the CompanyGenAILLM under the hood."""
        llm = CompanyGenAILLM(
            api_key=self.api_key,
            model=self.model,
            user_id=self.user_id,
            base_url=self.base_url,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        return llm._generate(messages, stop, run_manager, **kwargs)
    
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)
