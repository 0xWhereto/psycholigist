"""
Main entry point for the Telegram bot.
"""
import asyncio
import logging
import os

import sqlalchemy
from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.ext import Application

from bot.services.database import init_database, get_db
from bot.services.ai_service import init_ai_service
from bot.services.payment_monitor import init_payment_monitor, get_payment_monitor
from bot.services.scheduler import init_scheduler, get_scheduler
from bot.services.crypto_pay import init_crypto_pay
from bot.handlers import register_all_handlers

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Background task references
_monitor_task = None
_scheduler_task = None


async def post_init(application: Application):
    """Инициализация после запуска приложения."""
    global _monitor_task
    
    # Initialize database
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is not set")
    
    db = init_database(database_url)
    await db.init_db()
    
    # Migrate: expand payments.status column if needed
    try:
        async with db.engine.begin() as conn:
            await conn.execute(
                sqlalchemy.text("ALTER TABLE payments ALTER COLUMN status TYPE VARCHAR(30)")
            )
            logger.info("Migrated payments.status to VARCHAR(30)")
    except Exception as e:
        logger.debug(f"payments.status migration skipped: {e}")
    
    # Initialize AI service
    ai_provider = os.getenv("AI_PROVIDER", "anthropic")
    
    ai_config = {}
    if ai_provider == "openai":
        ai_config = {
            "api_key": os.getenv("OPENAI_API_KEY"),
            "model": os.getenv("OPENAI_MODEL", "gpt-4o")
        }
    elif ai_provider == "anthropic":
        ai_config = {
            "api_key": os.getenv("ANTHROPIC_API_KEY"),
            "model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        }
    elif ai_provider == "ollama":
        ai_config = {
            "host": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            "model": os.getenv("OLLAMA_MODEL", "llama3.1")
        }
    
    init_ai_service(ai_provider, ai_config)
    
    # Initialize Crypto Pay (card payments with crypto conversion)
    crypto_pay_token = os.getenv("CRYPTO_PAY_TOKEN")
    if crypto_pay_token:
        init_crypto_pay(crypto_pay_token)
        logger.info("Crypto Pay initialized - card payments enabled")
    else:
        logger.warning("CRYPTO_PAY_TOKEN not set - card payments disabled")
    
    # Initialize payment monitor (auto-confirmation via blockchain)
    wallet_address = os.getenv("WALLET_ADDRESS")
    if wallet_address:
        monitor = init_payment_monitor(wallet_address, application.bot)
        _monitor_task = asyncio.create_task(monitor.start())
        logger.info("Payment monitor started - auto-confirmation enabled")
    else:
        logger.warning("WALLET_ADDRESS not set - payment auto-confirmation disabled")
    
    # Initialize subscription scheduler (reminders, auto-renewal)
    scheduler = init_scheduler(application.bot)
    _scheduler_task = asyncio.create_task(scheduler.start())
    logger.info("Subscription scheduler started - auto-renewal enabled")
    
    # Set bot commands menu (appears in Telegram's "/" menu)
    commands_ru = [
        BotCommand("menu", "📋 Главное меню"),
        BotCommand("start", "👋 Приветствие"),
        BotCommand("subscribe", "💎 Подписка"),
        BotCommand("status", "📊 Статус подписки"),
        BotCommand("reset", "🔄 Новый диалог"),
        BotCommand("help", "🆘 Помощь"),
    ]
    commands_en = [
        BotCommand("menu", "📋 Main menu"),
        BotCommand("start", "👋 Welcome"),
        BotCommand("subscribe", "💎 Subscribe"),
        BotCommand("status", "📊 Subscription status"),
        BotCommand("reset", "🔄 New conversation"),
        BotCommand("help", "🆘 Help"),
    ]
    commands_fr = [
        BotCommand("menu", "📋 Menu principal"),
        BotCommand("start", "👋 Bienvenue"),
        BotCommand("subscribe", "💎 S'abonner"),
        BotCommand("status", "📊 Statut abonnement"),
        BotCommand("reset", "🔄 Nouvelle conversation"),
        BotCommand("help", "🆘 Aide"),
    ]
    
    await application.bot.set_my_commands(commands_ru, language_code="ru")
    await application.bot.set_my_commands(commands_en, language_code="en")
    await application.bot.set_my_commands(commands_fr, language_code="fr")
    # Default fallback (English)
    await application.bot.set_my_commands(commands_en)
    
    logger.info("Bot commands menu set")
    logger.info("Bot initialized successfully")


async def post_shutdown(application: Application):
    """Очистка при остановке приложения."""
    global _monitor_task, _scheduler_task
    
    # Stop payment monitor
    monitor = get_payment_monitor()
    if monitor:
        await monitor.stop()
    
    if _monitor_task:
        _monitor_task.cancel()
        try:
            await _monitor_task
        except asyncio.CancelledError:
            pass
    
    # Stop scheduler
    scheduler = get_scheduler()
    if scheduler:
        await scheduler.stop()
    
    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
    
    # Close database
    try:
        db = get_db()
        await db.close()
    except RuntimeError:
        pass  # Database was not initialized
    
    logger.info("Bot shutdown complete")


async def error_handler(update: Update, context):
    """Глобальный обработчик ошибок."""
    logger.error(f"Exception during update handling: {context.error}")


def main():
    """Запуск бота."""
    logger.info("Starting bot...")
    
    # Get bot token
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set")
    
    # Create application
    application = (
        Application.builder()
        .token(bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
    # Register handlers
    register_all_handlers(application)
    
    # Register error handler
    application.add_error_handler(error_handler)
    
    # Start polling
    logger.info("Bot is ready, starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
