"""
Local LLM wrapper for Ollama integration with LangChain
"""
from typing import Any, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.callbacks import CallbackManagerForLLMRun
import ollama


class LocalLLM(BaseChatModel):
    """
    LangChain wrapper for local Ollama-based LLM.
    
    Usage:
        llm = LocalLLM(model="llama3", temperature=0.7)
    
    Requirements:
        - Ollama installed and running (ollama serve)
        - Model pulled (ollama pull llama3)
    """
    
    model: str = "llama3"
    temperature: float = 0.7
    top_p: float = 1.0
    top_k: int = 40
    
    class Config:
        arbitrary_types_allowed = True
    
    @property
    def _llm_type(self) -> str:
        return "local_ollama"
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate chat response using Ollama."""
        
        # Convert LangChain messages to Ollama format
        ollama_messages = []
        for message in messages:
            if isinstance(message, SystemMessage):
                ollama_messages.append({
                    "role": "system",
                    "content": message.content
                })
            elif isinstance(message, HumanMessage):
                ollama_messages.append({
                    "role": "user",
                    "content": message.content
                })
            elif isinstance(message, AIMessage):
                ollama_messages.append({
                    "role": "assistant",
                    "content": message.content
                })
        
        # Call Ollama API
        try:
            response = ollama.chat(
                model=self.model,
                messages=ollama_messages,
                stream=False,
                options={
                    "temperature": self.temperature,
                    "top_p": self.top_p,
                    "top_k": self.top_k,
                }
            )
            
            # Extract the response content
            content = response['message']['content']
            
            # Create ChatGeneration from the response
            generation = ChatGeneration(
                message=AIMessage(content=content)
            )
            
            return ChatResult(generations=[generation])
            
        except Exception as e:
            raise ValueError(f"Error calling Ollama: {str(e)}. Make sure Ollama is running and the model '{self.model}' is available.")
    
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Async generate - uses sync version for Ollama"""
        return self._generate(messages, stop, run_manager, **kwargs)