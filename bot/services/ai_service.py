"""
AI service - wrapper for AI client.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class AIService:
    """Сервис для работы с AI."""
    
    def __init__(self, provider: str, config: dict):
        self.provider = provider
        self.config = config
        self.client = None
        self.system_prompt = ""
        self._init_client()
        self._load_system_prompt()
    
    def _init_client(self):
        """Инициализирует AI клиент."""
        if self.provider == "openai":
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=self.config["api_key"])
            self.model = self.config.get("model", "gpt-4o")
        elif self.provider == "anthropic":
            from anthropic import AsyncAnthropic
            self.client = AsyncAnthropic(api_key=self.config["api_key"])
            self.model = self.config.get("model", "claude-sonnet-4-20250514")
        elif self.provider == "ollama":
            import ollama
            self.client = ollama.AsyncClient(host=self.config.get("host", "http://localhost:11434"))
            self.model = self.config.get("model", "llama3.1")
        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}")
        
        logger.info(f"Initialized AI client: {self.provider} ({self.model})")
    
    def _load_system_prompt(self):
        """Загружает системный промпт."""
        prompt_path = Path(__file__).parent.parent.parent / "prompts" / "system_prompt.txt"
        
        if prompt_path.exists():
            self.system_prompt = prompt_path.read_text(encoding="utf-8")
            logger.info(f"Loaded system prompt from {prompt_path}")
        else:
            self.system_prompt = "Tu es un assistant bienveillant en soutien psychologique."
            logger.warning(f"System prompt not found at {prompt_path}")
    
    async def generate_response(self, messages: list[dict]) -> str:
        """Генерирует ответ на основе истории сообщений."""
        try:
            if self.provider == "openai":
                return await self._generate_openai(messages)
            elif self.provider == "anthropic":
                return await self._generate_anthropic(messages)
            elif self.provider == "ollama":
                return await self._generate_ollama(messages)
        except Exception as e:
            logger.error(f"AI generation error: {e}")
            raise
    
    async def _generate_openai(self, messages: list[dict]) -> str:
        """Генерирует ответ через OpenAI."""
        full_messages = [{"role": "system", "content": self.system_prompt}] + messages
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            max_tokens=1024,
            temperature=0.7,
        )
        
        return response.choices[0].message.content
    
    async def _generate_anthropic(self, messages: list[dict]) -> str:
        """Генерирует ответ через Anthropic."""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=self.system_prompt,
            messages=messages,
        )
        
        return response.content[0].text
    
    async def _generate_ollama(self, messages: list[dict]) -> str:
        """Генерирует ответ через Ollama."""
        full_messages = [{"role": "system", "content": self.system_prompt}] + messages
        
        response = await self.client.chat(
            model=self.model,
            messages=full_messages,
        )
        
        return response["message"]["content"]


# Global instance
ai_service: AIService | None = None


def get_ai_service() -> AIService:
    """Возвращает экземпляр AIService."""
    if ai_service is None:
        raise RuntimeError("AI service not initialized")
    return ai_service


def init_ai_service(provider: str, config: dict) -> AIService:
    """Инициализирует AI сервис."""
    global ai_service
    ai_service = AIService(provider, config)
    return ai_service
