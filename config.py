"""
Configuration du chatbot psychologue.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Configuration centralisée du bot."""
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/autopsych")
    
    # AI Provider
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "anthropic")
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    # Anthropic
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    
    # Ollama (local)
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1")
    
    # Bot settings
    MAX_CONVERSATION_HISTORY: int = int(os.getenv("MAX_CONVERSATION_HISTORY", "20"))
    
    # Subscriptions
    FREE_TIER_DAILY_MESSAGES: int = int(os.getenv("FREE_TIER_DAILY_MESSAGES", "3"))
    GRACE_PERIOD_DAYS: int = int(os.getenv("GRACE_PERIOD_DAYS", "3"))
    
    # Crypto Wallet
    WALLET_ADDRESS: str = os.getenv("WALLET_ADDRESS", "")
    WALLET_CURRENCY: str = os.getenv("WALLET_CURRENCY", "USDT")
    
    # Admin
    ADMIN_USER_ID: str = os.getenv("ADMIN_USER_ID", "")
    
    # Paths
    BASE_DIR: Path = Path(__file__).parent
    PROMPTS_DIR: Path = BASE_DIR / "prompts"


settings = Settings()
