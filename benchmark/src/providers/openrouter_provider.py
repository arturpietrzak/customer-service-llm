import os
import asyncio
import aiohttp
import logging
from typing import List, Dict, Any, Optional, AsyncIterator
from .base import BaseLLMProvider, ModelConfig, Message, ModelResponse

logger = logging.getLogger(__name__)


class OpenRouterProvider(BaseLLMProvider):
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        super().__init__(api_key, base_url)
        
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = (base_url or "https://openrouter.ai/api/v1").rstrip('/')

        if not self.api_key:
            raise ValueError("OpenRouter API key is required")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    async def generate_response(
        self, 
        messages: List[Message], 
        model_config: ModelConfig,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> ModelResponse:
        
        is_gemini = "gemini" in model_config.model_name.lower()
        is_mistral = "mistral" in model_config.model_name.lower()
        is_openai = "openai/" in model_config.model_name.lower() or "gpt-" in model_config.model_name.lower()
        needs_tool_handling = is_gemini or is_mistral or is_openai
        
        formatted_messages = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            
            if msg.role == "tool" and needs_tool_handling:
                i += 1
                continue
            elif msg.role == "assistant" and hasattr(msg, 'tool_calls') and msg.tool_calls and needs_tool_handling:
                content = msg.content or ""
                
                j = i + 1
                tool_results_content = ""
                while j < len(messages) and messages[j].role == "tool":
                    tool_result = messages[j]
                    if tool_results_content:
                        tool_results_content += "\n"
                    tool_results_content += f"Tool result: {tool_result.content}"
                    j += 1
                
                if tool_results_content:
                    combined_content = f"{content}\n\nBased on the search results:\n{tool_results_content}"
                else:
                    combined_content = content
                
                formatted_messages.append({
                    "role": msg.role,
                    "content": combined_content
                })
                
                i = j
                continue
            else:
                formatted_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            i += 1
        
        payload = {
            "model": model_config.model_name,
            "messages": formatted_messages,
            "temperature": model_config.temperature,
            "max_tokens": model_config.max_tokens,
        }
        
        if tools:
            payload["tools"] = tools
        
        if hasattr(model_config, 'top_p') and model_config.top_p:
            payload["top_p"] = model_config.top_p
        if hasattr(model_config, 'frequency_penalty') and model_config.frequency_penalty:
            payload["frequency_penalty"] = model_config.frequency_penalty
        if hasattr(model_config, 'presence_penalty') and model_config.presence_penalty:
            payload["presence_penalty"] = model_config.presence_penalty
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("choices") and len(data["choices"]) > 0:
                            choice = data["choices"][0]
                            message = choice.get("message", {})
                            content = message.get("content", "")
                            model_used = data.get("model", model_config.model_name)
                            
                            tool_calls = None
                            if message.get("tool_calls"):
                                tool_calls = message["tool_calls"]
                            
                            return ModelResponse(
                                content=content,
                                model=model_used,
                                provider="openrouter",
                                tool_calls=tool_calls or [],
                                error=None
                            )
                        else:
                            error_msg = "No choices in OpenRouter response"
                            logger.error(f"OpenRouter API error: {error_msg}")
                            return ModelResponse(
                                content="",
                                model=model_config.model_name,
                                provider="openrouter",
                                tool_calls=[], 
                                error=error_msg
                            )
                    
                    else:
                        try:
                            error_data = await response.json() if response.content_type == 'application/json' else {}
                            error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status}")
                            
                            logger.error(f"OpenRouter API error {response.status} for model {model_config.model_name}")
                            logger.error(f"Error message: {error_msg}")
                            logger.error(f"Full error data: {error_data}")
                            logger.error(f"Request payload: {payload}")
                            
                        except Exception as e:
                            error_msg = f"HTTP {response.status} - Could not parse error response: {e}"
                            logger.error(f"OpenRouter API error {response.status} for model {model_config.model_name}: {error_msg}")
                        
                        return ModelResponse(
                            content="",
                            model=model_config.model_name,
                            provider="openrouter",
                            tool_calls=[],
                            error=f"Provider returned error"
                        )
                        
        except asyncio.TimeoutError:
            error_msg = "Request timeout"
            logger.error(f"OpenRouter API timeout for model {model_config.model_name}")
            return ModelResponse(
                content="",
                model=model_config.model_name,
                provider="openrouter",
                tool_calls=[],
                error=error_msg
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"OpenRouter API request failed: {error_msg}")
            return ModelResponse(
                content="",
                model=model_config.model_name,
                provider="openrouter",
                tool_calls=[],
                error=f"Request failed: {error_msg}"
            )
    
    async def stream_response(
        self, 
        messages: List[Message], 
        model_config: ModelConfig,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncIterator[str]:
        response = await self.generate_response(messages, model_config, tools)
        if response.content:
            yield response.content
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        return [
            {"id": "openai/gpt-4o", "name": "GPT-4o"},
            {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini"},
            {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet"},
            {"id": "google/gemini-2.0-flash-exp", "name": "Gemini 2.0 Flash"},
            {"id": "meta-llama/llama-3.3-70b-instruct", "name": "Llama 3.3 70B"},
            {"id": "mistralai/mistral-small", "name": "Mistral Small"},
            {"id": "deepseek/deepseek-chat", "name": "DeepSeek Chat"},
            {"id": "x-ai/grok-3", "name": "Grok 3"}
        ]