"""
Start, help, menu command handlers.
"""
import logging

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from bot.services.database import get_db
from bot.services.user_service import UserService
from bot.services.message_service import MessageService
from bot.services.subscription_service import SubscriptionService, SUBSCRIPTION_PLANS
from bot.services.ai_service import get_ai_service
from bot.services.summary_service import SummaryService
from bot.utils.texts import get_text
from bot.utils.keyboards import get_main_menu_keyboard, get_back_to_menu_keyboard, get_subscription_keyboard, get_language_keyboard

logger = logging.getLogger(__name__)


# ─── Commands ────────────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /start."""
    user = update.effective_user
    db = get_db()
    
    async with db.session() as session:
        existing_user = await UserService.get_user(session, user.id)
    
    if existing_user is None:
        # New user — ask for language first
        choose_lang_text = (
            "🌐 Выберите язык / Choose your language / Choisissez votre langue:"
        )
        await update.message.reply_text(
            choose_lang_text,
            reply_markup=get_language_keyboard(),
        )
        return
    
    # Existing user — show welcome as usual
    async with db.session() as session:
        db_user = await UserService.get_or_create_user(
            session,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            language_code=existing_user.language_code
        )
        lang = db_user.language_code
    
    name = f", {user.first_name}" if user.first_name else ""
    
    await update.message.reply_text(
        get_text("welcome", lang, name=name),
        reply_markup=get_main_menu_keyboard(lang),
        parse_mode="Markdown"
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /menu — показывает главное меню."""
    user = update.effective_user
    db = get_db()
    
    async with db.session() as session:
        db_user = await UserService.get_or_create_user(
            session,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            language_code=user.language_code or "ru"
        )
        lang = db_user.language_code
    
    menu_texts = {
        "ru": "📋 **Главное меню**\n\nВыберите действие:",
        "en": "📋 **Main Menu**\n\nChoose an action:",
        "fr": "📋 **Menu principal**\n\nChoisissez une action:",
    }
    
    await update.message.reply_text(
        menu_texts.get(lang, menu_texts["ru"]),
        reply_markup=get_main_menu_keyboard(lang),
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /help."""
    user = update.effective_user
    db = get_db()
    
    async with db.session() as session:
        db_user = await UserService.get_user(session, user.id)
        lang = db_user.language_code if db_user else "ru"
    
    await update.message.reply_text(
        _get_help_text(lang),
        reply_markup=get_back_to_menu_keyboard(lang),
        parse_mode="Markdown"
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /reset — сброс диалога с сохранением саммари."""
    user = update.effective_user
    db = get_db()
    
    async with db.session() as session:
        db_user = await UserService.get_user(session, user.id)
        lang = db_user.language_code if db_user else "ru"
        
        # Суммаризируем перед очисткой (долговременная память)
        try:
            history = await MessageService.get_conversation_history(session, user.id, limit=100)
            if history and len(history) >= 4:
                ai_service = get_ai_service()
                await SummaryService.summarize_and_clear(
                    session, ai_service, user.id, history
                )
        except Exception as e:
            logger.warning(f"Summary before reset failed for {user.id}: {e}")
        
        await MessageService.clear_conversation(session, user.id)
    
    reset_texts = {
        "ru": "✨ Диалог сброшен. Мы можем начать сначала.\n\nНапиши мне или выбери действие:",
        "en": "✨ Conversation reset. We can start fresh.\n\nWrite to me or choose an action:",
        "fr": "✨ Conversation réinitialisée. Nous pouvons repartir de zéro.\n\nÉcris-moi ou choisis une action:",
    }
    
    await update.message.reply_text(
        reset_texts.get(lang, reset_texts["ru"]),
        reply_markup=get_main_menu_keyboard(lang),
        parse_mode="Markdown"
    )


# ─── Menu Callbacks ──────────────────────────────────────────────────────────

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия кнопок главного меню."""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    data = query.data
    
    if not data.startswith("menu:"):
        return
    
    action = data.split(":")[1]
    
    db = get_db()
    
    async with db.session() as session:
        db_user = await UserService.get_or_create_user(
            session,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            language_code=user.language_code or "ru"
        )
        lang = db_user.language_code
    
    if action == "back":
        # Вернуться в главное меню
        menu_texts = {
            "ru": "📋 **Главное меню**\n\nВыберите действие:",
            "en": "📋 **Main Menu**\n\nChoose an action:",
            "fr": "📋 **Menu principal**\n\nChoisissez une action:",
        }
        await query.edit_message_text(
            menu_texts.get(lang, menu_texts["ru"]),
            reply_markup=get_main_menu_keyboard(lang),
            parse_mode="Markdown"
        )
    
    elif action == "chat":
        # Приглашение к диалогу
        chat_texts = {
            "ru": "💬 Я тебя слушаю. Расскажи, что тебя беспокоит.\n\nПросто напиши мне сообщение.",
            "en": "💬 I'm listening. Tell me what's on your mind.\n\nJust send me a message.",
            "fr": "💬 Je t'écoute. Dis-moi ce qui te préoccupe.\n\nÉcris-moi simplement un message.",
        }
        await query.edit_message_text(
            chat_texts.get(lang, chat_texts["ru"]),
            reply_markup=get_back_to_menu_keyboard(lang),
            parse_mode="Markdown"
        )
    
    elif action == "reset":
        # Суммаризируем перед очисткой (долговременная память)
        async with db.session() as session:
            try:
                history = await MessageService.get_conversation_history(session, user.id, limit=100)
                if history and len(history) >= 4:
                    ai_service = get_ai_service()
                    await SummaryService.summarize_and_clear(
                        session, ai_service, user.id, history
                    )
            except Exception as e:
                logger.warning(f"Summary before reset failed for {user.id}: {e}")
            
            await MessageService.clear_conversation(session, user.id)
        
        reset_texts = {
            "ru": "✨ Диалог сброшен. Мы можем начать сначала.\n\nНапиши мне или выбери действие:",
            "en": "✨ Conversation reset. We can start fresh.\n\nWrite to me or choose an action:",
            "fr": "✨ Conversation réinitialisée. Nous pouvons repartir de zéro.\n\nÉcris-moi ou choisis une action:",
        }
        await query.edit_message_text(
            reset_texts.get(lang, reset_texts["ru"]),
            reply_markup=get_main_menu_keyboard(lang),
            parse_mode="Markdown"
        )
    
    elif action == "subscribe":
        # Показать подписку
        async with db.session() as session:
            active_sub = await SubscriptionService.get_active_subscription(session, user.id)
            
            if active_sub:
                plan = SUBSCRIPTION_PLANS[active_sub.plan_type]
                active_texts = {
                    "ru": f"""
✅ **У вас активная подписка**

**План:** {plan['name_ru']}
**Действует до:** {active_sub.expires_at.strftime('%d.%m.%Y')}
**Осталось дней:** {active_sub.days_remaining}
""",
                    "en": f"""
✅ **You have an active subscription**

**Plan:** {plan['name_en']}
**Valid until:** {active_sub.expires_at.strftime('%d.%m.%Y')}
**Days remaining:** {active_sub.days_remaining}
""",
                    "fr": f"""
✅ **Vous avez un abonnement actif**

**Formule:** {plan['name_fr']}
**Valable jusqu'au:** {active_sub.expires_at.strftime('%d.%m.%Y')}
**Jours restants:** {active_sub.days_remaining}
""",
                }
                await query.edit_message_text(
                    active_texts.get(lang, active_texts["ru"]),
                    reply_markup=get_back_to_menu_keyboard(lang),
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    get_text("subscription_prompt", lang),
                    reply_markup=get_subscription_keyboard(lang),
                    parse_mode="Markdown"
                )
    
    elif action == "status":
        # Статус подписки
        async with db.session() as session:
            active_sub = await SubscriptionService.get_active_subscription(session, user.id)
            
            if active_sub:
                plan = SUBSCRIPTION_PLANS[active_sub.plan_type]
                
                auto_renew_labels = {
                    "ru": "✅ Вкл" if active_sub.auto_renew else "❌ Выкл",
                    "en": "✅ On" if active_sub.auto_renew else "❌ Off",
                    "fr": "✅ Oui" if active_sub.auto_renew else "❌ Non",
                }
                
                status_texts = {
                    "ru": f"""
📊 **Статус подписки**

**План:** {plan['name_ru']}
**Статус:** ✅ Активна
**Действует до:** {active_sub.expires_at.strftime('%d.%m.%Y')}
**Осталось дней:** {active_sub.days_remaining}
**Авто-продление:** {auto_renew_labels['ru']}
""",
                    "en": f"""
📊 **Subscription Status**

**Plan:** {plan['name_en']}
**Status:** ✅ Active
**Valid until:** {active_sub.expires_at.strftime('%d.%m.%Y')}
**Days remaining:** {active_sub.days_remaining}
**Auto-renewal:** {auto_renew_labels['en']}
""",
                    "fr": f"""
📊 **Statut de l'abonnement**

**Formule:** {plan['name_fr']}
**Statut:** ✅ Actif
**Valable jusqu'au:** {active_sub.expires_at.strftime('%d.%m.%Y')}
**Jours restants:** {active_sub.days_remaining}
**Renouvellement auto:** {auto_renew_labels['fr']}
""",
                }
                await query.edit_message_text(
                    status_texts.get(lang, status_texts["ru"]),
                    reply_markup=get_back_to_menu_keyboard(lang),
                    parse_mode="Markdown"
                )
            else:
                no_sub_texts = {
                    "ru": "📊 У вас нет активной подписки.\n\n🆓 Бесплатно: 10 сообщений в день.\nДля безлимита — оформите подписку!",
                    "en": "📊 You don't have an active subscription.\n\n🆓 Free: 10 messages per day.\nFor unlimited — get a subscription!",
                    "fr": "📊 Vous n'avez pas d'abonnement actif.\n\n🆓 Gratuit: 10 messages par jour.\nPour l'illimité — abonnez-vous!",
                }
                
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        "💎 Подписка" if lang == "ru" else "💎 Subscribe" if lang == "en" else "💎 S'abonner",
                        callback_data="menu:subscribe"
                    )],
                    [InlineKeyboardButton(
                        "↩️ Главное меню" if lang == "ru" else "↩️ Main menu" if lang == "en" else "↩️ Menu principal",
                        callback_data="menu:back"
                    )],
                ])
                
                await query.edit_message_text(
                    no_sub_texts.get(lang, no_sub_texts["ru"]),
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
    
    elif action == "language":
        # Show language picker
        choose_lang_text = (
            "🌐 Выберите язык / Choose your language / Choisissez votre langue:"
        )
        await query.edit_message_text(
            choose_lang_text,
            reply_markup=get_language_keyboard(),
        )

    elif action == "help":
        # Помощь и кризисные ресурсы
        await query.edit_message_text(
            _get_help_text(lang),
            reply_markup=get_back_to_menu_keyboard(lang),
            parse_mode="Markdown"
        )


# ─── Language Callback ───────────────────────────────────────────────────────

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор языка (lang:ru / lang:en / lang:fr)."""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    lang_code = query.data.split(":")[1]  # ru / en / fr
    
    db = get_db()
    
    async with db.session() as session:
        existing_user = await UserService.get_user(session, user.id)
        
        if existing_user is None:
            # First time — create user with chosen language
            db_user = await UserService.get_or_create_user(
                session,
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                language_code=lang_code,
            )
        else:
            # Existing user — update language
            db_user = await UserService.update_language(session, user.id, lang_code)
    
    lang = lang_code
    name = f", {user.first_name}" if user.first_name else ""
    
    await query.edit_message_text(
        get_text("welcome", lang, name=name),
        reply_markup=get_main_menu_keyboard(lang),
        parse_mode="Markdown",
    )


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_help_text(lang: str) -> str:
    """Возвращает текст помощи с кризисными ресурсами."""
    help_texts = {
        "ru": """
🆘 **Помощь и ресурсы**

**В случае кризиса — звони:**
• **8-800-2000-122** — Телефон доверия (РФ, бесплатно)
• **3114** — Prévention du suicide (Франция)
• **112** — Экстренные службы

**О боте:**
Я использую психоаналитический интегративный подход для поддержки.
Я не заменяю настоящего терапевта.

**Совет:** Регулярные сеансы с профессионалом — лучший путь к себе.

Помни: просить о помощи — это проявление силы 💙
""",
        "en": """
🆘 **Help & Resources**

**In case of crisis — call:**
• **988** — Suicide & Crisis Lifeline (US)
• **116 123** — Samaritans (UK)
• **112** — Emergency services (EU)

**About the bot:**
I use a psychoanalytic integrative approach for support.
I do not replace a real therapist.

**Tip:** Regular sessions with a professional are the best path to self-understanding.

Remember: asking for help is a sign of strength 💙
""",
        "fr": """
🆘 **Aide & Ressources**

**En cas de crise — appelez:**
• **3114** — Prévention du suicide (24h/24)
• **112** — Services d'urgence

**À propos du bot:**
J'utilise une approche psychanalytique intégrative pour le soutien.
Je ne remplace pas un vrai thérapeute.

**Conseil:** Des séances régulières avec un professionnel sont le meilleur chemin vers soi.

N'oublie pas: demander de l'aide est un signe de force 💙
""",
    }
    return help_texts.get(lang, help_texts["ru"])


# ─── Registration ────────────────────────────────────────────────────────────

def register_start_handlers(application):
    """Регистрирует обработчики стартовых команд."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("aide", help_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CallbackQueryHandler(language_callback, pattern=r"^lang:"))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:"))
