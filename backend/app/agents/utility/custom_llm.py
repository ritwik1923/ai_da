import time
import requests
import re
from typing import Any, List, Optional, Dict
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.callbacks import CallbackManagerForLLMRun

class OllamaLocalLLM(BaseChatModel):
    """
    Hardware-optimized wrapper for Ollama on Apple Silicon (M4).
    Supports dynamic model switching for Hybrid (Reasoning + Coding) tasks.
    """
    model: str = "llama3.1:8b" # Default to reasoning model
    base_url: str = "http://localhost:11434"
    temperature: float = 0.0
    num_ctx: int = 4096 # Default context
    num_thread: int = 8  # Optimized for M4 Performance Cores

    @property
    def _llm_type(self) -> str:
        return "ollama_local_m4"

    def _repair_response(self, content: str) -> str:
        """
        Targeted repairs for local LLM quirks:
        1. Strips Markdown code blocks that break ReAct parsers.
        2. Cleans up conversational prefixes DeepSeek adds to Action Inputs.
        """
        if not content: return content

        # Remove Triple Backticks (Markdown)
        content = re.sub(r"```(?:python)?\n?", "", content)
        content = re.sub(r"```", "", content)

        # Fix nested tool calls (e.g., Action Input: execute_pandas_code("..."))
        content = re.sub(r"execute_pandas_code\s*\(\s*['\"]+(.*?)['\"]+\s*\)", r"\1", content, flags=re.DOTALL)

        return content.strip()

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        start_time = time.time()

        # Convert LangChain objects to Ollama Chat JSON
        ollama_messages = []
        for m in messages:
            role = "user"
            if isinstance(m, SystemMessage): role = "system"
            elif isinstance(m, AIMessage): role = "assistant"
            ollama_messages.append({"role": role, "content": m.content})

        # DeepSeek-Coder needs larger context for 1000+ column schemas
        # We auto-bump context if using the heavy model
        current_ctx = 8192 if "deepseek" in self.model.lower() else self.num_ctx

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_ctx": current_ctx,
                "num_thread": self.num_thread,
                "stop": stop or ["Observation:", "\nObservation:", "Thought:"]
            }
        }

        try:
            response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=120)
            response.raise_for_status()
            
            raw_text = response.json().get("message", {}).get("content", "")
            
            # Post-processing repair
            clean_text = self._repair_response(raw_text)
            
            duration = time.time() - start_time
            print(f"--- [M4 GPU] {self.model} | {duration:.2f}s | ctx: {current_ctx} ---")
            
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=clean_text))])
            
        except Exception as e:
            print(f"--- [M4 Error] {self.model} failed: {str(e)} ---")
            raise ValueError(f"Ollama local connection failed: {str(e)}")

    async def _agenerate(self, *args, **kwargs):
        """Standard sync fallback for async calls."""
        return self._generate(*args, **kwargs)

# """
# Custom LLM wrapper for company's GenAI API
# Compatible with LangChain framework
# """
# from typing import Any, List, Optional, Dict
# from langchain_core.language_models.chat_models import BaseChatModel
# from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
# from langchain_core.outputs import ChatGeneration, ChatResult
# from langchain_core.callbacks import CallbackManagerForLLMRun
# import requests
# import uuid
# from pydantic import Field
# import requests
# from sympy import content
# import re
# import time
# class CompanyGenAILLM(BaseChatModel):
#     """
#     Custom LangChain LLM wrapper for company's GenAI service.
    
#     Usage:
#         llm = CompanyGenAILLM(
#             api_key="your-api-key",
#             model="ChatGPT4o",
#             user_id="your-email@motorolasolutions.com"
#         )
#     """
    
#     api_key: str
#     model: str = "ChatGPT4o"
#     user_id: Optional[str] = None
#     base_url: str = "https://genai-service.stage.commandcentral.com/app-gateway"
#     temperature: float = 0.7
#     max_tokens: int = 800
#     top_p: float = 1.0
#     frequency_penalty: float = 0
#     presence_penalty: float = 0
#     session_id: Optional[str] = None
#     client_id: Optional[str] = None
    
#     class Config:
#         arbitrary_types_allowed = True
    
#     @property
#     def _llm_type(self) -> str:
#         return "company_genai"
    
#     def _generate(
#         self,
#         messages: List[BaseMessage],
#         stop: Optional[List[str]] = None,
#         run_manager: Optional[CallbackManagerForLLMRun] = None,
#         **kwargs: Any,
#     ) -> ChatResult:
#         """Generate chat response from the company GenAI API."""
        
#         # Convert LangChain messages to API format
#         system_message = ""
#         prompt = ""
        
#         for message in messages:
#             if isinstance(message, SystemMessage):
#                 system_message = message.content
#             elif isinstance(message, HumanMessage):
#                 prompt = message.content
#             elif isinstance(message, AIMessage):
#                 # For conversation history, we'd need to maintain session
#                 pass
        
#         # Prepare request
#         headers = {
#             "x-msi-genai-api-key": self.api_key,
#             "Content-Type": "application/json"
#         }
        
#         if self.client_id:
#             headers["X-msi-genai-client"] = self.client_id
        
#         payload = {
#             "model": self.model,
#             "prompt": prompt,
#             "modelConfig": {
#                 "temperature": self.temperature,
#                 "max_tokens": self.max_tokens,
#                 "top_p": self.top_p,
#                 "frequency_penalty": self.frequency_penalty,
#                 "presence_penalty": self.presence_penalty
#             }
#         }
        
#         # Add optional fields
#         if self.user_id:
#             payload["userId"] = self.user_id
        
#         if system_message:
#             payload["system"] = system_message
        
#         if self.session_id:
#             payload["sessionId"] = self.session_id
        
#         # Make API call
#         try:
#             response = requests.post(
#                 f"{self.base_url}/api/v2/chat",
#                 headers=headers,
#                 json=payload,
#                 timeout=60
#             )
#             response.raise_for_status()
            
#             result = response.json()
            
#             if not result.get("status"):
#                 raise ValueError(f"API Error: {result.get('msg', 'Unknown error')}")
            
#             # Update session ID for future calls
#             if result.get("sessionId"):
#                 self.session_id = result["sessionId"]
            
#             # Extract response message
#             message_content = result.get("msg", "")
            
#             # Create ChatResult
#             message = AIMessage(content=message_content)
#             generation = ChatGeneration(message=message)
            
#             return ChatResult(generations=[generation])
            
#         except requests.exceptions.RequestException as e:
#             raise ValueError(f"API request failed: {str(e)}")
    
#     async def _agenerate(
#         self,
#         messages: List[BaseMessage],
#         stop: Optional[List[str]] = None,
#         run_manager: Optional[CallbackManagerForLLMRun] = None,
#         **kwargs: Any,
#     ) -> ChatResult:
#         """Async generation - not implemented, falls back to sync."""
#         return self._generate(messages, stop, run_manager, **kwargs)


# class OpenAICompatibleLLM(BaseChatModel):
#     """
#     Wrapper to use company's ChatGPT models with OpenAI-compatible interface.
#     This allows seamless switching between company API and OpenAI.
#     """
    
#     api_key: str
#     model: str = "ChatGPT4o"
#     user_id: Optional[str] = None
#     base_url: str = "https://genai-service.stage.commandcentral.com/app-gateway"
#     temperature: float = 0
#     max_tokens: int = 800
    
#     class Config:
#         arbitrary_types_allowed = True
    
#     @property
#     def _llm_type(self) -> str:
#         return "openai_compatible"
    
#     def _generate(
#         self,
#         messages: List[BaseMessage],
#         stop: Optional[List[str]] = None,
#         run_manager: Optional[CallbackManagerForLLMRun] = None,
#         **kwargs: Any,
#     ) -> ChatResult:
#         """Use the CompanyGenAILLM under the hood."""
#         llm = CompanyGenAILLM(
#             api_key=self.api_key,
#             model=self.model,
#             user_id=self.user_id,
#             base_url=self.base_url,
#             temperature=self.temperature,
#             max_tokens=self.max_tokens
#         )
#         return llm._generate(messages, stop, run_manager, **kwargs)
    
#     async def _agenerate(
#         self,
#         messages: List[BaseMessage],
#         stop: Optional[List[str]] = None,
#         run_manager: Optional[CallbackManagerForLLMRun] = None,
#         **kwargs: Any,
#     ) -> ChatResult:
#         return self._generate(messages, stop, run_manager, **kwargs)


# class OllamaLocalLLM_(BaseChatModel):
#     model: str = "mistral"
#     base_url: str = "http://localhost:11434"
#     temperature: float = 0.0  # Crucial: 0.0 for deterministic tool use
    
#     @property
#     def _llm_type(self) -> str:
#         return "ollama_local"

#     def _repair_react_format(self, content: str) -> str:
#         """Removes brackets and conversational junk that break the ReAct parser."""
#         if not content: return content
        
#         # 1. Remove brackets around tool names (Fixes the '[' is not a valid tool error)
#         content = content.replace("[", "").replace("]", "")
        
#         # 2. Strip "I will use" or "Calling" prefixes
#         content = re.sub(r"Action:\s*(?:I will use|Calling|Utilizing|Using|the)\s*", "Action: ", content, flags=re.IGNORECASE)
        
#         # 3. Handle 'Action Input:' missing or on wrong line
#         if "Action:" in content and "Action Input:" not in content:
#             lines = content.split('\n')
#             new_lines = []
#             for line in lines:
#                 new_lines.append(line)
#                 if line.startswith("Action:") and "Action Input:" not in content:
#                     new_lines.append("Action Input: ")
#             content = "\n".join(new_lines)

#         return content.strip()
    
#     def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, **kwargs: Any) -> ChatResult:
#         ollama_messages = []
#         for m in messages:
#             role = "user" if isinstance(m, HumanMessage) else "system" if isinstance(m, SystemMessage) else "assistant"
#             ollama_messages.append({"role": role, "content": m.content})

#         payload = {
#             "model": self.model,
#             "messages": ollama_messages,
#             "stream": False,
#             "options": {
#                 "temperature": self.temperature,
#                 "num_predict": 500,
#                 "stop": stop or ["Observation:", "Observation:"]
#             }
#         }

#         try:
#             response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=120)
#             response.raise_for_status()
#             content = response.json().get("message", {}).get("content", "")
            
#             # Apply the repair logic
#             content = self._repair_react_format(content)
#             print(f"DEBUG LLM OUTPUT:\n{content}\n---")
            
#             return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])
#         except Exception as e:
#             raise ValueError(f"Ollama Error: {str(e)}")
        
        
# class OllamaLocalLLM(BaseChatModel):
#     """
#     Optimized for DeepSeek-Coder-V2 on Apple Silicon (M4).
#     Handles large context for 1000+ column schemas and 100k+ row metadata.
#     """
#     # Use the 16b lite version for the best balance on 24GB RAM
#     model: str = "deepseek-coder-v2:16b"
#     base_url: str = "http://localhost:11434"
#     temperature: float = 0.0
#     context_window: int = 8192  # Increased for large schemas

#     @property
#     def _llm_type(self) -> str:
#         return "ollama_local_deepseek"

#     def _repair_react_format(self, content: str) -> str:
#         """
#         DeepSeek specific repairs: 
#         1. Removes markdown blocks (DeepSeek loves ```python).
#         2. Fixes the 'Action Input' syntax if it's missing or nested.
#         """
#         if not content: return content

#         # 1. Strip Markdown Code Blocks - LangChain parser hates these in ReAct
#         content = re.sub(r"```python\n?", "", content)
#         content = re.sub(r"```\n?", "", content)

#         # 2. Fix nested tool calls (e.g., Action Input: execute_pandas_code("..."))
#         content = re.sub(r"execute_pandas_code\s*\(\s*['\"]+(.*?)['\"]+\s*\)", r"\1", content, flags=re.DOTALL)

#         # 3. Clean up leading/trailing whitespace and stray dots
#         content = content.strip().lstrip('.')

#         return content

#     def _generate(
#         self,
#         messages: List[BaseMessage],
#         stop: Optional[List[str]] = None,
#         run_manager: Optional[CallbackManagerForLLMRun] = None,
#         **kwargs: Any,
#     ) -> ChatResult:
#         start_time = time.time()

#         # Convert LangChain messages to Ollama format
#         ollama_messages = []
#         for m in messages:
#             role = "user"
#             if isinstance(m, SystemMessage): role = "system"
#             elif isinstance(m, AIMessage): role = "assistant"
#             ollama_messages.append({"role": role, "content": m.content})

#         payload = {
#             "model": self.model,
#             "messages": ollama_messages,
#             "stream": False,
#             "options": {
#                 "temperature": self.temperature,
#                 "num_ctx": self.context_window, # Critical for 1000+ columns
#                 "num_thread": 8, # Optimized for M4 high-performance cores
#                 "stop": stop or ["Observation:", "\nObservation:", "Thought:"]
#             }
#         }

#         try:
#             response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=180)
#             response.raise_for_status()
            
#             raw_content = response.json().get("message", {}).get("content", "")
            
#             # Repair and Log
#             content = self._repair_react_format(raw_content)
            
#             duration = time.time() - start_time
#             print(f"--- [LLM] {self.model} generated in {duration:.2f}s ---")
            
#             return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])
            
#         except Exception as e:
#             print(f"--- [ERROR] Ollama call failed: {str(e)} ---")
#             raise ValueError(f"Ollama Request Failed: {str(e)}")

#     async def _agenerate(self, *args, **kwargs):
#         """Falls back to sync generation."""
#         return self._generate(*args, **kwargs)