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
        """Загружает системный промпт и сжатую клиническую базу знаний."""
        base_dir = Path(__file__).parent.parent.parent
        prompt_path = base_dir / "prompts" / "system_prompt.txt"
        knowledge_path = base_dir / "prompts" / "knowledge_base.md"
        
        # Загружаем основной промпт
        if prompt_path.exists():
            self.system_prompt = prompt_path.read_text(encoding="utf-8")
            logger.info(f"Loaded system prompt from {prompt_path}")
        else:
            self.system_prompt = "Tu es un assistant bienveillant en soutien psychologique."
            logger.warning(f"System prompt not found at {prompt_path}")
        
        # Загружаем сжатую клиническую базу знаний
        if knowledge_path.exists():
            knowledge_base = knowledge_path.read_text(encoding="utf-8")
            self.system_prompt += f"""

---

## БАЗА ЗНАНИЙ: КЛИНИЧЕСКИЕ МОДЕЛИ ПСИХОАНАЛИТИКА

Ниже — твоя клиническая база знаний. Используй эти модели при работе с клиентами, но НЕ цитируй их напрямую и НЕ упоминай, что у тебя есть «модели» или «таблицы». Естественно интегрируй эти знания в свои ответы, как если бы это был твой собственный клинический опыт.

{knowledge_base}
"""
            logger.info(f"Loaded knowledge base from {knowledge_path}")
        else:
            logger.warning(f"Knowledge base not found at {knowledge_path}")
        
        # Логируем размер промпта
        est_tokens = self._estimate_tokens(self.system_prompt)
        logger.info(f"Total system prompt: {len(self.system_prompt)} chars, ~{est_tokens} tokens")
    
    def _estimate_tokens(self, text: str) -> int:
        """Грубая оценка токенов (1 токен ≈ 4 символа для латиницы, ≈ 2 для кириллицы)."""
        return len(text) // 3  # Средняя оценка для мультиязычного текста
    
    def _trim_messages_to_fit(self, messages: list[dict], max_total_tokens: int = 25000) -> list[dict]:
        """Обрезает историю сообщений, чтобы уместиться в лимит токенов."""
        system_tokens = self._estimate_tokens(self.system_prompt)
        reserve_for_response = 1500  # токены на ответ + буфер
        available = max_total_tokens - system_tokens - reserve_for_response
        
        if available <= 0:
            logger.warning(f"System prompt too large: ~{system_tokens} tokens, trimming to last 2 messages")
            return messages[-2:] if len(messages) > 2 else messages
        
        # Считаем токены с конца (новые сообщения приоритетнее)
        trimmed = []
        total = 0
        for msg in reversed(messages):
            msg_tokens = self._estimate_tokens(msg["content"])
            if total + msg_tokens > available:
                break
            trimmed.insert(0, msg)
            total += msg_tokens
        
        if len(trimmed) < len(messages):
            logger.info(f"Trimmed messages: {len(messages)} → {len(trimmed)} (~{total} tokens, system ~{system_tokens})")
        
        return trimmed
    
    async def generate_response(self, messages: list[dict]) -> str:
        """Генерирует ответ на основе истории сообщений."""
        # Обрезаем если нужно, чтобы не превысить лимит токенов
        messages = self._trim_messages_to_fit(messages)
        
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
