"""
Main chat handler - AI conversation.
"""
import logging
import os
import re

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from bot.services.database import get_db
from bot.services.user_service import UserService
from bot.services.subscription_service import SubscriptionService
from bot.services.message_service import MessageService
from bot.services.ai_service import get_ai_service
from bot.services.summary_service import SummaryService
from bot.utils.texts import get_text

logger = logging.getLogger(__name__)

# Детекция кризиса
CRISIS_KEYWORDS = [
    r"\bsuicide\b", r"\bsuicid", r"\bсуицид", r"\bубить себя\b", r"\bпокончить\b",
    r"\bme tuer\b", r"\ben finir\b", r"\bне хочу жить\b", r"\bумереть\b",
    r"\bautomutilation\b", r"\bсамоповреждение\b", r"\bself.?harm\b",
]

CRISIS_RESPONSE = {
    "ru": """
Я слышу твою боль.
Это очень важно, и ты не один(а).

🆘 **Срочная помощь:**
• **8-800-2000-122** — Телефон доверия (бесплатно, круглосуточно)
• **112** — Экстренные службы

Пожалуйста, обратись за помощью сейчас. 💙
""",
    "en": """
I hear your pain.
This is important, and you're not alone.

🆘 **Immediate help:**
• **988** — Suicide & Crisis Lifeline (US)
• **116 123** — Samaritans (UK)
• **112** — Emergency services

Please reach out for help now. 💙
""",
    "fr": """
J'entends ta souffrance.
C'est important, et tu n'es pas seul(e).

🆘 **Aide immédiate:**
• **3114** — Prévention du suicide (24h/24)
• **112** — Services d'urgence

S'il te plaît, demande de l'aide maintenant. 💙
"""
}


def detect_crisis(text: str) -> bool:
    """Детектирует признаки кризиса в сообщении."""
    text_lower = text.lower()
    for pattern in CRISIS_KEYWORDS:
        if re.search(pattern, text_lower):
            return True
    return False


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения."""
    user = update.effective_user
    user_message = update.message.text
    
    db = get_db()
    free_limit = int(os.getenv("FREE_TIER_DAILY_MESSAGES", "10"))
    grace_days = int(os.getenv("GRACE_PERIOD_DAYS", "3"))
    
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
        
        # Check subscription
        has_subscription = await SubscriptionService.has_active_subscription(session, user.id)
        in_grace = await SubscriptionService.is_in_grace_period(session, user.id, grace_days)
        
        # Админ — безлимит без подписки
        from bot.handlers.admin import is_admin
        
        # Check free message limit
        if not has_subscription and not in_grace and not is_admin(user.id):
            remaining = await UserService.get_free_messages_remaining(session, db_user, free_limit)
            
            if remaining <= 0:
                await update.message.reply_text(
                    get_text("free_limit_reached", lang, limit=free_limit),
                    parse_mode="Markdown"
                )
                return
            
            # Increment counter
            await UserService.increment_free_messages(session, db_user)
        
        # Detect crisis
        if detect_crisis(user_message):
            logger.warning(f"Crisis detected for user {user.id}")
            await update.message.reply_text(
                CRISIS_RESPONSE.get(lang, CRISIS_RESPONSE["ru"]),
                parse_mode="Markdown"
            )
        
        # Show typing indicator
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
        
        # Save user message
        await MessageService.add_message(session, user.id, "user", user_message)
        
        # Get conversation history
        max_history = int(os.getenv("MAX_CONVERSATION_HISTORY", "20"))
        history = await MessageService.get_conversation_history(session, user.id, max_history)
        
        # Загружаем долговременную память (саммари предыдущих сессий)
        summary = await SummaryService.get_summary(session, user.id)
        
        # Если история переполнена — суммаризируем старые сообщения
        total_messages = await MessageService.get_message_count(session, user.id)
        if total_messages > max_history + 10:
            try:
                ai_service_for_summary = get_ai_service()
                # Берём все сообщения которые не вошли в текущее окно
                old_messages = await MessageService.get_old_messages(
                    session, user.id, offset=max_history
                )
                if old_messages and len(old_messages) >= 4:
                    await SummaryService.summarize_and_clear(
                        session, ai_service_for_summary, user.id, old_messages
                    )
                    # Удаляем старые сообщения, оставляем только последние max_history
                    await MessageService.trim_old_messages(session, user.id, keep=max_history)
                    # Обновляем саммари
                    summary = await SummaryService.get_summary(session, user.id)
                    logger.info(f"Auto-summarized old messages for user {user.id}")
            except Exception as e:
                logger.error(f"Auto-summary failed for user {user.id}: {e}")
        
        # Формируем контекст с долговременной памятью
        if summary:
            memory_message = {
                "role": "user",
                "content": (
                    f"[КОНТЕКСТ — долговременная память из предыдущих сессий, "
                    f"не отвечай на это сообщение, просто учитывай эту информацию "
                    f"о клиенте в своих ответах]\n\n{summary}"
                )
            }
            history_with_memory = [memory_message] + history
        else:
            history_with_memory = history
        
        # Generate response
        try:
            ai_service = get_ai_service()
            response = await ai_service.generate_response(history_with_memory)
            
            # Save assistant response
            await MessageService.add_message(session, user.id, "assistant", response)
            
            # Send response
            await update.message.reply_text(response)
            
        except Exception as e:
            logger.error(f"AI generation error: {e}", exc_info=True)
            error_msg = get_text("error_generic", lang)
            
            # Админу показываем детали ошибки
            if is_admin(user.id):
                error_msg += f"\n\n🔧 Debug: {type(e).__name__}: {e}"
            
            await update.message.reply_text(error_msg)


def register_chat_handlers(application):
    """Регистрирует обработчик чата."""
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
