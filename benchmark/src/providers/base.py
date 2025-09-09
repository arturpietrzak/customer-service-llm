from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncGenerator
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class ModelResponse(BaseModel):
    content: str
    usage: Optional[Dict[str, int]] = None
    model: str
    provider: str
    tool_calls: List[Dict[str, Any]] = []
    error: Optional[str] = None
    latency_ms: Optional[float] = None


class ToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any]
    call_id: Optional[str] = None


class Message(BaseModel):
    role: str
    content: str
    tool_calls: List[ToolCall] = []
    tool_call_id: Optional[str] = None


class ModelConfig(BaseModel):
    model_name: str
    temperature: float = 0.7
    max_tokens: int = 1000
    top_p: float = 0.9
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout: float = 30.0


class BaseLLMProvider(ABC):
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        self.provider_name = self.__class__.__name__.replace('Provider', '').lower()
    
    @abstractmethod
    async def generate_response(
        self,
        messages: List[Message],
        model_config: ModelConfig,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> ModelResponse:
        pass
    
    @abstractmethod
    async def stream_response(
        self,
        messages: List[Message],
        model_config: ModelConfig,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[str, None]:
        pass
    
    def get_default_system_prompt(self) -> str:
        return """Jesteś asystentem obsługi klienta w sklepie elektronicznym. 

DOSTĘPNE KATEGORIE PRODUKTÓW:
- Dyski
- Karty graficzne
- Klawiatury
- Laptopy
- Monitory
- Myszki
- Powerbanki
- Routery
- Smartfony
- Smartwatche
- Słuchawki
- Tablety

WAŻNE: Zawsze używaj narzędzi do wyszukiwania produktów w bazie danych. NIE pytaj klienta o dodatkowe szczegóły - po prostu wyszukaj najlepiej pasujące produkty.

PROCES:
1. Klient zadaje pytanie o produkt/kategorię
2. Użyj narzędzia search_products aby znaleźć odpowiednie produkty
3. Odpowiedz na podstawie wyników z bazy danych

JEŚLI KLIENT PYTA O SMARTFONY/TELEFONY:
- Poinformuj grzecznie, że nie sprzedajemy telefonów komórkowych
- Zaproponuj alternatywy jak smartwatche lub tablety

NIE PYTAJ O:
- Budżet klienta
- Preferencje kolorystyczne  
- Konkretne specyfikacje
- Dodatkowe wymagania

ZAMIAST TEGO:
- Od razu wyszukaj produkty pasujące do pytania
- Pokaż dostępne opcje z cenami w PLN
- Podaj podstawowe informacje o produktach

WAŻNE: NIE pokazuj jakich narzędzi używasz (np. [search_products]). 

Bądź pomocny i profesjonalny, ale nie dopytuj o szczegóły - działaj na podstawie dostępnych danych."""
    
    def format_messages_with_system_prompt(self, user_query: str) -> List[Message]:
        return [
            Message(role="system", content=self.get_default_system_prompt()),
            Message(role="user", content=user_query)
        ]
    
    def get_response_formatting_prompt(self) -> str:
        return """Jesteś asystentem obsługi klienta. Twoje zadanie to sformatować wyniki wyszukiwania produktów w przyjazną dla klienta odpowiedź.

ZASADY FORMATOWANIA:
1. NIE pokazuj jakich narzędzi używałeś
2. NIE wspominaj o "wyszukiwaniu w bazie danych"
3. Przedstaw produkty w przejrzystej formie z cenami w PLN
4. Bądź konkretny i pomocny
5. Jeśli wystąpił błąd narzędzia lub brak produktów, sprawdź czy nie było błędu w zapytaniu

PRZYKŁAD DOBREJ ODPOWIEDZI:
"Oto dostępne laptopy Lenovo:
1. Lenovo ThinkPad X1 - 4299,00 PLN
2. Lenovo IdeaPad Gaming - 3199,00 PLN

Mogę podać więcej szczegółów o którymś modelu?"

KATEGORYCZNIE ZABRONIONE:
- "Może chcesz sprecyzować..."
- "Jakiego typu ... Cię interesuje?"
- Pytania o preferencje (bezprzewodowe/przewodowe, nauszne/dokanałowe)
- Pytania o zastosowanie (gry/muzyka)
- Pytania o budżet lub szczegóły
- "Chętnie pomogę gdy będę miał więcej szczegółów"

JEŚLI BRAK WYNIKÓW:
"Przepraszam, obecnie nie mamy w ofercie [kategoria produktu]. Sprawdź nasze inne kategorie: [wymień 2-3 podobne]."

NIE PYTAJ O NICZYM - tylko prezentuj to co masz!"""
    
    def get_database_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_products",
                    "description": "Search for products by name, category, producer, or price range",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Product name or keywords to search for"
                            },
                            "category": {
                                "type": "string",
                                "description": "EXACT category name - one of: Dyski, Karty graficzne, Klawiatury, Laptopy, Monitory, Myszki, Powerbanki, Routery, Smartwatche, Słuchawki, Tablety"
                            },
                            "producer": {
                                "type": "string", 
                                "description": "Producer/brand name (e.g. Apple, Lenovo, Sony, Dell, ASUS)"
                            },
                            "min_price": {
                                "type": "number",
                                "description": "Minimum price in PLN"
                            },
                            "max_price": {
                                "type": "number",
                                "description": "Maximum price in PLN"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_product",
                    "description": "Get detailed information about a specific product by ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_id": {
                                "type": "integer",
                                "description": "Product ID"
                            }
                        },
                        "required": ["product_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_categories",
                    "description": "Get list of all available product categories",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_producers",
                    "description": "Get list of all available producers/manufacturers",
                    "parameters": {
                        "type": "object", 
                        "properties": {}
                    }
                }
            }
        ]
    
    async def execute_tool_call(self, tool_call: ToolCall) -> Dict[str, Any]:
        import aiohttp
        import json
        
        try:
            async with aiohttp.ClientSession() as session:
                if tool_call.name == "search_products":
                    url = f"http://localhost:8001/search_products"
                    async with session.post(url, json=tool_call.arguments) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            return {"error": f"HTTP {response.status}: {error_text}"}
                
                elif tool_call.name == "get_product":
                    product_id = tool_call.arguments.get("product_id")
                    url = f"http://localhost:8001/get_product/{product_id}"
                    async with session.get(url) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            return {"error": f"HTTP {response.status}: {error_text}"}
                
                elif tool_call.name == "get_categories":
                    url = f"http://localhost:8001/get_categories"
                    async with session.get(url) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            return {"error": f"HTTP {response.status}: {error_text}"}
                
                elif tool_call.name == "get_producers":
                    url = f"http://localhost:8001/get_producers"
                    async with session.get(url) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            return {"error": f"HTTP {response.status}: {error_text}"}
                
                else:
                    return {"error": f"Unknown tool: {tool_call.name}"}
        
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": f"Tool execution failed: {str(e)}"}


class MockProvider(BaseLLMProvider):
    
    async def generate_response(
        self,
        messages: List[Message],
        model_config: ModelConfig,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> ModelResponse:
        user_message = next((m.content for m in messages if m.role == "user"), "")
        
        return ModelResponse(
            content=f"Mock response to: {user_message}",
            model=model_config.model_name,
            provider="mock",
            usage={"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}
        )
    
    async def stream_response(
        self,
        messages: List[Message], 
        model_config: ModelConfig,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[str, None]:
        response = "Mock streaming response"
        for word in response.split():
            yield word + " "