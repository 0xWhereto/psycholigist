"""
Start command handler.
"""
import logging

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from bot.services.database import get_db
from bot.services.user_service import UserService
from bot.utils.texts import get_text

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /start."""
    user = update.effective_user
    db = get_db()
    
    async with db.session() as session:
        # Get or create user
        db_user = await UserService.get_or_create_user(
            session,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            language_code=user.language_code or "ru"
        )
        lang = db_user.language_code
    
    name = f", {user.first_name}" if user.first_name else ""
    
    await update.message.reply_text(
        get_text("welcome", lang, name=name),
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /help."""
    user = update.effective_user
    db = get_db()
    
    async with db.session() as session:
        db_user = await UserService.get_user(session, user.id)
        lang = db_user.language_code if db_user else "ru"
    
    help_text = {
        "ru": """
🤝 **Помощь и ресурсы**

**В случае кризиса:**
• 3114 — Телефон доверия (Франция)
• 8-800-2000-122 — Телефон доверия (Россия)
• 112 — Экстренные службы

**Команды бота:**
• /start — приветствие
• /subscribe — оформить подписку
• /status — статус подписки
• /reset — начать новый диалог
• /help — эта справка

Помни: просить о помощи — это проявление силы. 💙
""",
        "en": """
🤝 **Help and Resources**

**In case of crisis:**
• 988 — Suicide & Crisis Lifeline (US)
• 116 123 — Samaritans (UK)
• 112 — Emergency services

**Bot commands:**
• /start — welcome message
• /subscribe — get a subscription
• /status — subscription status
• /reset — start a new conversation
• /help — this help

Remember: asking for help is a sign of strength. 💙
""",
        "fr": """
🤝 **Aide et ressources**

**En cas de crise:**
• 3114 — Prévention du suicide
• 112 — Services d'urgence

**Commandes du bot:**
• /start — message d'accueil
• /subscribe — s'abonner
• /status — statut de l'abonnement
• /reset — nouvelle conversation
• /help — cette aide

N'oublie pas: demander de l'aide est un signe de force. 💙
"""
    }
    
    await update.message.reply_text(
        help_text.get(lang, help_text["ru"]),
        parse_mode="Markdown"
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /reset — сброс диалога."""
    user = update.effective_user
    db = get_db()
    
    from bot.services.message_service import MessageService
    
    async with db.session() as session:
        db_user = await UserService.get_user(session, user.id)
        lang = db_user.language_code if db_user else "ru"
        
        await MessageService.clear_conversation(session, user.id)
    
    await update.message.reply_text(
        get_text("conversation_reset", lang),
        parse_mode="Markdown"
    )


def register_start_handlers(application):
    """Регистрирует обработчики стартовых команд."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("aide", help_command))
    application.add_handler(CommandHandler("reset", reset_command))
