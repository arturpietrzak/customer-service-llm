import time
import logging
import json
from typing import Dict, Any, List, Optional, AsyncGenerator
from .base import BaseLLMProvider, ModelResponse, Message, ModelConfig, ToolCall
import asyncio

logger = logging.getLogger(__name__)


class ReplicateProvider(BaseLLMProvider):
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        super().__init__(api_key, base_url)
        
    async def generate_response(
        self,
        messages: List[Message],
        model_config: ModelConfig,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> ModelResponse:
        if tools:
            return await self._generate_response_with_forced_tools(messages, model_config, tools)
        else:
            return await self._generate_simple_response(messages, model_config)
    
    async def _generate_simple_response(
        self,
        messages: List[Message],
        model_config: ModelConfig
    ) -> ModelResponse:
        return await self._call_replicate_api(messages, model_config, None)
    
    async def _generate_response_with_forced_tools(
        self,
        messages: List[Message],
        model_config: ModelConfig,
        tools: List[Dict[str, Any]]
    ) -> ModelResponse:
        try:
            logger.info("Step 1: Making initial request with tool calling instructions")
            first_response = await self._call_replicate_api(messages, model_config, tools)
            
            if not first_response.tool_calls:
                logger.info("No tool calls found in first response, returning as-is")
                return first_response
            
            logger.info(f"Step 2: Found {len(first_response.tool_calls)} tool calls, will be processed by executor")
            return first_response
            
        except Exception as e:
            logger.error(f"Error in forced tool calling: {e}")
            return ModelResponse(
                content="",
                model=model_config.model_name,
                provider="replicate",
                error=str(e),
                latency_ms=0
            )
    
    async def _call_replicate_api(
        self,
        messages: List[Message],
        model_config: ModelConfig,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> ModelResponse:
        try:
            import replicate
            
            client = replicate.Client(api_token=self.api_key)
            
            input_text = self._format_messages_for_replicate(messages, tools)
            
            input_params = {
                "input": input_text,
                "temperature": model_config.temperature,
                "max_tokens": model_config.max_tokens,
                "top_p": model_config.top_p,
            }
            
            start_time = time.time()
            
            output = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.run(model_config.model_name, input=input_params)
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            if isinstance(output, list):
                content = "".join(str(item) for item in output)
            elif isinstance(output, str):
                content = output
            else:
                content = str(output)
            
            tool_calls = []
            if tools:
                tool_calls = self._extract_tool_calls_from_content(content, tools)
            
            return ModelResponse(
                content=content,
                model=model_config.model_name,
                provider="replicate",
                tool_calls=tool_calls,
                latency_ms=latency_ms,
                usage=None
            )
            
        except Exception as e:
            logger.error(f"Replicate API error: {e}")
            return ModelResponse(
                content="",
                model=model_config.model_name,
                provider="replicate",
                error=str(e),
                latency_ms=0
            )
    
    def _format_messages_for_replicate(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None) -> str:
        formatted_parts = []
        
        if tools:
            tool_instructions = self._create_tool_instructions(tools)
            formatted_parts.append(tool_instructions)
            formatted_parts.append("")
        
        for msg in messages:
            if msg.role == "system":
                formatted_parts.append(f"System: {msg.content}")
            elif msg.role == "user":
                formatted_parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                formatted_parts.append(f"Assistant: {msg.content}")
            elif msg.role == "tool":
                formatted_parts.append(f"Tool Result: {msg.content}")
        
        if tools:
            formatted_parts.append("")
            formatted_parts.append("REMINDER: Use TOOL_CALL: function_name({\"param\": \"value\"}) format when needed!")
            formatted_parts.append("Assistant:")
        
        return "\n".join(formatted_parts)
    
    def _create_tool_instructions(self, tools: List[Dict[str, Any]]) -> str:
        tool_descriptions = []
        for tool in tools:
            if "function" in tool:
                func = tool["function"]
                name = func["name"]
                description = func.get("description", "")
                parameters = func.get("parameters", {})
                
                required_params = parameters.get("required", [])
                param_examples = []
                
                if "properties" in parameters:
                    for param_name, param_info in parameters["properties"].items():
                        param_type = param_info.get("type", "string")
                        param_desc = param_info.get("description", "")
                        if param_name in required_params:
                            param_examples.append(f'"{param_name}": "example_value"')
                
                example_call = f'{name}({{{", ".join(param_examples)}}})'
                tool_descriptions.append(f"- {name}: {description}\n  Example: {example_call}")
        
        instructions = f"""
=== OBOWIĄZKOWE INSTRUKCJE UŻYCIA NARZĘDZI ===
Jesteś asystentem obsługi klienta w sklepie elektronicznym.

Dostępne narzędzia:
{chr(10).join(tool_descriptions)}

KRYTYCZNA ZASADA: Gdy użytkownik pyta o produkty, ceny lub dostępność, MUSISZ użyć narzędzi do przeszukania bazy danych.

WYMAGANY DOKŁADNY FORMAT:
TOOL_CALL: nazwa_funkcji({{\"parametr\": \"wartość\"}})

Przykłady:
- Użytkownik pyta "Pokaż mi laptopy Lenovo" → MUSISZ odpowiedzieć: TOOL_CALL: search_products({{\"query\": \"Lenovo laptops\"}})
- Użytkownik pyta "Ile kosztuje iPhone?" → MUSISZ odpowiedzieć: TOOL_CALL: search_products({{\"query\": \"iPhone\"}})
- Użytkownik pyta "Jakie są dostępne monitory?" → MUSISZ odpowiedzieć: TOOL_CALL: search_products({{\"query\": \"monitory\"}})

NIE wymyślaj cen ani informacji o produktach. ZAWSZE używaj formatu TOOL_CALL najpierw.
=== KONIEC INSTRUKCJI ===
"""
        return instructions
    
    def _extract_tool_calls_from_content(self, content: str, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tool_calls = []
        
        if not tools:
            return tool_calls
        
        try:
            import re
            
            pattern = r'TOOL_CALL:\s*(\w+)\s*\((\{[^}]*\})\)'
            matches = re.findall(pattern, content, re.IGNORECASE)
            
            tool_names = [tool["function"]["name"] for tool in tools if "function" in tool]
            
            for func_name, args_str in matches:
                if func_name in tool_names:
                    try:
                        args_str = args_str.strip()
                        args_str = args_str.replace("'", '"')
                        
                        args = json.loads(args_str)
                        tool_calls.append({
                            "name": func_name,
                            "arguments": args,
                            "call_id": f"call_{len(tool_calls)}"
                        })
                        logger.info(f"Extracted tool call: {func_name} with args {args}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse tool arguments '{args_str}': {e}")
                        
                        try:
                            manual_args = self._extract_args_manually(args_str)
                            if manual_args:
                                tool_calls.append({
                                    "name": func_name,
                                    "arguments": manual_args,
                                    "call_id": f"call_{len(tool_calls)}"
                                })
                                logger.info(f"Manually extracted tool call: {func_name} with args {manual_args}")
                        except Exception as manual_e:
                            logger.warning(f"Manual extraction also failed: {manual_e}")
                
        except Exception as e:
            logger.warning(f"Failed to extract tool calls: {e}")
        
        return tool_calls
    
    def _extract_args_manually(self, args_str: str) -> Dict[str, Any]:
        import re
        
        pattern = r'["\']?(\w+)["\']?\s*:\s*["\']([^"\']*)["\']?'
        matches = re.findall(pattern, args_str)
        
        result = {}
        for key, value in matches:
            result[key] = value
        
        return result if result else {"query": args_str.strip('{}"\'')}
    
    async def stream_response(
        self,
        messages: List[Message],
        model_config: ModelConfig,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[str, None]:
        response = await self.generate_response(messages, model_config, tools)
        yield response.content
    
    def supports_streaming(self) -> bool:
        return False
    
    def supports_tools(self) -> bool:
        return True
    
    def get_available_models(self) -> List[str]:
        return [
            "aleksanderobuchowski/bielik-1.5b-v3.0-instruct:992a42f28592c96e95123cdccef12ae156ab24a147e48e973f04b3fa127f6a32",
            "meta/llama-2-70b-chat:02e509c789964a7ea8736978a43525956ef40397be9033abf9fd2badfe68c9e3",
            "meta/llama-2-13b-chat:f4e2de70d66816a838a89eeeb621910adffb0dd0baba3976c96980970978018d",
            "mistralai/mistral-7b-instruct-v0.1:5fe0a3d7ac2852264a25279d1dfb798acbc4d49711d126646594e212cb821749"
        ]