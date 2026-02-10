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
        """Загружает системный промпт и исследовательские работы как контекст."""
        base_dir = Path(__file__).parent.parent.parent
        prompt_path = base_dir / "prompts" / "system_prompt.txt"
        research_dir = base_dir / "research"
        
        # Загружаем основной промпт
        if prompt_path.exists():
            self.system_prompt = prompt_path.read_text(encoding="utf-8")
            logger.info(f"Loaded system prompt from {prompt_path}")
        else:
            self.system_prompt = "Tu es un assistant bienveillant en soutien psychologique."
            logger.warning(f"System prompt not found at {prompt_path}")
        
        # Загружаем исследовательские работы как базу знаний
        if research_dir.exists():
            research_texts = []
            for md_file in sorted(research_dir.glob("*.md")):
                content = md_file.read_text(encoding="utf-8")
                research_texts.append(f"### {md_file.stem}\n\n{content}")
                logger.info(f"Loaded research file: {md_file.name}")
            
            if research_texts:
                knowledge_base = "\n\n---\n\n".join(research_texts)
                self.system_prompt += f"""

---

## БАЗА ЗНАНИЙ: ИССЛЕДОВАТЕЛЬСКИЕ РАБОТЫ ПСИХОАНАЛИТИКА

Ниже представлены научные и клинические работы психоаналитика, чей подход ты воплощаешь. Используй эти материалы как свою теоретическую и клиническую базу. Опирайся на них при работе с клиентами, но НЕ цитируй их напрямую и НЕ упоминай, что у тебя есть "статьи" или "работы". Вместо этого, естественно интегрируй эти знания в свои ответы, как если бы это был твой собственный клинический опыт и понимание.

Ключевые модели из этих работ:
- Формула вагусного профиля X-Y-Z (T) — используй для понимания регуляторных паттернов клиента
- Связь типов привязанности (Боулби/Эйнсворт) с вагусными контурами
- Окситоциновая петля и её нарушения (дефицитарная, хаотичная, токсичная)
- Структурно-вагусная модель (невротический / пограничный / психотический уровни)
- Триггерные профили (привязанность, контроль, безопасность, идентичность, тело)

{knowledge_base}
"""
                logger.info(f"Loaded {len(research_texts)} research files into knowledge base")
    
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
