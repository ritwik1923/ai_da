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
import requests


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



class OllamaLocalLLM(BaseChatModel):
    """
    Custom LangChain LLM wrapper for local Ollama service running on the Host Mac.
    """
    model: str = "mistral"
    # Use host.docker.internal to reach the Mac host from inside a Docker container
    base_url: str = "http://localhost:11434"  # Default Ollama API URL; change if your setup differs
    # base_url: str = "http://host.docker.internal:11434"
    temperature: float = 0.7
    repair_count: int = 0  # Track consecutive repairs to break infinite loops
    
    @property
    def _llm_type(self) -> str:
        return "ollama_local"
    
    def _check_model_available(self) -> bool:
        """Check if the model is available in Ollama"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                models = response.json().get("models", [])
                available_models = [m.get("name", "").split(":")[0] for m in models]
                model_base = self.model.split(":")[0]
                return model_base in available_models
        except:
            pass
        return False

    def _get_available_models(self) -> List[str]:
        """Return a list of available model names from Ollama (base names)."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return [m.get("name", "").split(":")[0] for m in models]
        except Exception:
            pass
        return []

    def _repair_react_format(self, content: str) -> str:
        """
        Detect and repair malformed responses from the model.
        Mistral sometimes mixes explanations with code or formats incorrectly.
        """
        # If already in proper ReAct format, reset counter and return as-is
        if "Thought:" in content and "Action:" in content and "Action Input:" in content:
            self.repair_count = 0
            return content
        
        # Check for code blocks with explanations (Mistral's new pattern)
        if "```" in content and ("The issue" in content or "In Python" in content or "should resolve" in content):
            # Mistral is mixing explanation with code - extract just the code
            print(f"WARN: Detected mixed explanation+code response, extracting code...")
            import re
            code_blocks = re.findall(r'```(?:python)?\n(.*?)```', content, re.DOTALL)
            if code_blocks:
                # Return the first code block as action input
                self.repair_count = 0
                code = code_blocks[0].strip()
                return f"Thought: Execute the extracted code\nAction: execute_pandas_code\nAction Input: {code}"
        
        # Check for conversational patterns that indicate format violation
        conversational_triggers = [
            "i'm ready to help",
            "i am ready to help",
            "let me help",
            "since we had no previous",
            "i'll help you",
            "i will help you",
            "how can i help",
            "what would you like",
            "i understand",
            "i see what you",
            "let me analyze",
            "i can help",
            "certainly",
            "of course",
            "sure, i'll",
        ]
        
        content_lower = content.lower().strip()
        
        # Check if content starts with conversational trigger OR is too conversational
        is_conversational = (
            any(content_lower.startswith(trigger) for trigger in conversational_triggers) or
            # Also catch if first line doesn't have "Thought:", "Action:", etc.
            (not any(x in content.split('\n')[0] for x in ["Thought:", "Action:", "Final Answer:"])
             and len(content) < 200  # Short responses are usually conversational
             and content[0].isupper())  # Starts with capital letter (like natural text)
        )
        
        if is_conversational:
            # Increment repair counter; if we've repaired too many times, stop hard
            self.repair_count += 1
            print(f"WARN: Detected conversational response (repair #{self.repair_count}), repairing format: {content[:60]}...")
            
            # After 2 consecutive repairs, raise exception to stop the agent immediately
            if self.repair_count >= 2:
                print(f"ERROR: Model format deviation persists after {self.repair_count} repairs. Stopping agent.")
                raise ValueError(
                    "Model consistently reverts to conversational responses and cannot follow ReAct format. "
                    "Please re-run the query with a narrower scope, fewer iterations, or try a different model."
                )
            
            # First repair: return a valid tool call that executes and returns error
            return (
                "Thought: Model format deviation detected, need to report and stop\n"
                "Action: execute_pandas_code\n"
                "Action Input: result = {'status': 'error', 'message': 'Model reverted to conversational response. Cannot continue ReAct loop. Please re-run the query with a narrower scope or increase MAX_ITERATIONS.'}"
            )
        
        # Reset counter if valid format is detected
        self.repair_count = 0
        return content

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        
        # 1. Convert LangChain messages to Ollama's Chat API format
        ollama_messages = []
        for m in messages:
            if isinstance(m, SystemMessage):
                ollama_messages.append({"role": "system", "content": m.content})
            elif isinstance(m, HumanMessage):
                ollama_messages.append({"role": "user", "content": m.content})
            elif isinstance(m, AIMessage):
                ollama_messages.append({"role": "assistant", "content": m.content})

        # 2. Truncate messages to avoid Ollama context limit (~4000 chars for llama3)
        MAX_CHARS = 3000  # Conservative for reliable responses

        def _approx_len(msgs: List[Dict[str, str]]) -> int:
            return sum(len(m.get("content", "")) for m in msgs)

        # Keep the most recent messages until we're under MAX_CHARS
        if _approx_len(ollama_messages) > MAX_CHARS:
            # Always keep the last message (current user input)
            while _approx_len(ollama_messages) > MAX_CHARS and len(ollama_messages) > 1:
                # remove the oldest non-system message first
                dropped = False
                for i, m in enumerate(ollama_messages):
                    if m.get("role") in ("user", "assistant"):
                        ollama_messages.pop(i)
                        dropped = True
                        break
                if not dropped:
                    ollama_messages.pop(0)

        # If still too large, create a summary
        if _approx_len(ollama_messages) > MAX_CHARS:
            last_msg = ollama_messages[-1] if ollama_messages else {"role": "user", "content": ""}
            system_msgs = [m for m in ollama_messages if m.get("role") == "system"]
            summary = f"[Previous conversation summary]. {last_msg.get('content', '')[:150]}"
            ollama_messages = system_msgs + [{"role": "user", "content": summary}]

        # 3. Prepare Payload for /api/chat with response limits
        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": 200,  # Limit output to 200 tokens for faster responses and to prevent loops
                "stop": stop or ["\\nObservation:", "\\nQuestion:", "Observation:"]
            }
        }

        try:
            api_url = f"{self.base_url}/api/chat"
            print(f"DEBUG: Calling Ollama at {api_url} with model {self.model}")
            
            # Check model availability first; if not available, try to pick a faster available model
            if not self._check_model_available():
                available = self._get_available_models()
                if available:
                    # prefer 'mistral' if available (typically faster), else pick the first available
                    pref = None
                    for candidate in ("mistral", "mistral-7b", "mistral-small", "fast", "gptj"):
                        if candidate in available:
                            pref = candidate
                            break
                    chosen = pref or available[0]
                    print(f"WARNING: Model '{self.model}' not found in Ollama; switching to available model '{chosen}' for speed.")
                    self.model = chosen
                else:
                    print(f"WARNING: Model '{self.model}' not found and no models listed by Ollama")
            
            response = requests.post(
                api_url,
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            
            # 3. Extract content and repair if needed
            content = result.get("message", {}).get("content", "")
            
            # Post-process: Detect and fix conversational responses that violate ReAct format
            content = self._repair_react_format(content)
            
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])
            
        except requests.exceptions.ConnectionError as e:
            raise ValueError(
                f"Failed to connect to Ollama at {self.base_url}. "
                f"Make sure Ollama is running on your Mac:\n"
                f"  1. Run: ollama serve\n"
                f"  2. Verify model: ollama list\n"
                f"  3. Pull model if needed: ollama pull {self.model}\n"
                f"Error: {str(e)}"
            ) from e
        except requests.exceptions.HTTPError as e:
            error_msg = f"Ollama API error ({e.response.status_code})"
            
            if e.response.status_code == 404:
                error_msg += f"\nModel '{self.model}' not found. Pull it with:\n  ollama pull {self.model}"
            elif e.response.status_code == 405:
                error_msg += "\nMethod not allowed. This shouldn't happen - check Ollama version."
            
            try:
                error_msg += f"\nResponse: {e.response.text}"
            except:
                pass
            
            raise ValueError(error_msg)
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Ollama request failed: {str(e)}")

# --- Example Usage ---
# llm = OllamaLocalLLM(model="mistral")
# print(llm.invoke("Hello, how are you?"))