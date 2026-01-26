"""
Subscription handlers.
"""
import logging
import os

from telegram import Update, LabeledPrice, InputFile
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, PreCheckoutQueryHandler, MessageHandler, filters

from bot.services.database import get_db
from bot.services.user_service import UserService
from bot.services.subscription_service import SubscriptionService, PaymentService, SUBSCRIPTION_PLANS
from bot.utils.keyboards import get_subscription_keyboard, get_payment_confirmation_keyboard, get_payment_method_keyboard
from bot.utils.texts import get_text
from bot.utils.qr_generator import generate_payment_qr

logger = logging.getLogger(__name__)


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /subscribe."""
    user = update.effective_user
    db = get_db()
    
    async with db.session() as session:
        db_user = await UserService.get_or_create_user(
            session,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name
        )
        lang = db_user.language_code
        
        # Check if already has active subscription
        active_sub = await SubscriptionService.get_active_subscription(session, user.id)
        if active_sub:
            plan = SUBSCRIPTION_PLANS[active_sub.plan_type]
            await update.message.reply_text(
                get_text(
                    "subscription_status",
                    lang,
                    plan_name=plan.get(f"name_{lang}", plan["name_ru"]),
                    status="✅ Активна" if lang == "ru" else "✅ Active",
                    expires_at=active_sub.expires_at.strftime("%d.%m.%Y"),
                    days_remaining=active_sub.days_remaining
                ),
                parse_mode="Markdown"
            )
            return
    
    await update.message.reply_text(
        get_text("subscription_prompt", lang),
        reply_markup=get_subscription_keyboard(lang),
        parse_mode="Markdown"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /status."""
    user = update.effective_user
    db = get_db()
    
    async with db.session() as session:
        db_user = await UserService.get_user(session, user.id)
        lang = db_user.language_code if db_user else "ru"
        
        active_sub = await SubscriptionService.get_active_subscription(session, user.id)
        
        if active_sub:
            plan = SUBSCRIPTION_PLANS[active_sub.plan_type]
            
            # Добавляем информацию об авто-продлении
            auto_renew_status = {
                "ru": "✅ Включено" if active_sub.auto_renew else "❌ Выключено",
                "en": "✅ Enabled" if active_sub.auto_renew else "❌ Disabled",
                "fr": "✅ Activé" if active_sub.auto_renew else "❌ Désactivé"
            }
            
            status_messages = {
                "ru": f"""
📊 **Статус подписки**

**План:** {plan['name_ru']}
**Статус:** ✅ Активна
**Действует до:** {active_sub.expires_at.strftime('%d.%m.%Y')}
**Осталось дней:** {active_sub.days_remaining}
**Авто-продление:** {auto_renew_status['ru']}

Управление:
• /cancel — отменить подписку
• /subscribe — продлить сейчас
""",
                "en": f"""
📊 **Subscription Status**

**Plan:** {plan['name_en']}
**Status:** ✅ Active
**Valid until:** {active_sub.expires_at.strftime('%d.%m.%Y')}
**Days remaining:** {active_sub.days_remaining}
**Auto-renewal:** {auto_renew_status['en']}

Management:
• /cancel — cancel subscription
• /subscribe — renew now
""",
                "fr": f"""
📊 **Statut de l'abonnement**

**Formule:** {plan['name_fr']}
**Statut:** ✅ Actif
**Valable jusqu'au:** {active_sub.expires_at.strftime('%d.%m.%Y')}
**Jours restants:** {active_sub.days_remaining}
**Renouvellement auto:** {auto_renew_status['fr']}

Gestion:
• /cancel — annuler l'abonnement
• /subscribe — renouveler maintenant
"""
            }
            
            await update.message.reply_text(
                status_messages.get(lang, status_messages["ru"]),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                get_text("no_subscription", lang),
                parse_mode="Markdown"
            )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /cancel — отмена подписки."""
    user = update.effective_user
    db = get_db()
    
    async with db.session() as session:
        db_user = await UserService.get_user(session, user.id)
        lang = db_user.language_code if db_user else "ru"
        
        active_sub = await SubscriptionService.get_active_subscription(session, user.id)
        
        if not active_sub:
            no_sub_messages = {
                "ru": "У вас нет активной подписки для отмены.",
                "en": "You don't have an active subscription to cancel.",
                "fr": "Vous n'avez pas d'abonnement actif à annuler."
            }
            await update.message.reply_text(no_sub_messages.get(lang, no_sub_messages["ru"]))
            return
        
        # Показываем опции отмены
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        cancel_messages = {
            "ru": f"""
⚠️ **Отмена подписки**

Ваша подписка действует до **{active_sub.expires_at.strftime('%d.%m.%Y')}**.

Что вы хотите сделать?
""",
            "en": f"""
⚠️ **Cancel Subscription**

Your subscription is valid until **{active_sub.expires_at.strftime('%d.%m.%Y')}**.

What would you like to do?
""",
            "fr": f"""
⚠️ **Annuler l'abonnement**

Votre abonnement est valable jusqu'au **{active_sub.expires_at.strftime('%d.%m.%Y')}**.

Que souhaitez-vous faire?
"""
        }
        
        if lang == "ru":
            buttons = [
                [InlineKeyboardButton("🔕 Отключить авто-продление", callback_data="cancel:autorenew")],
                [InlineKeyboardButton("❌ Отменить подписку полностью", callback_data="cancel:full")],
                [InlineKeyboardButton("↩️ Назад", callback_data="cancel:back")]
            ]
        elif lang == "en":
            buttons = [
                [InlineKeyboardButton("🔕 Disable auto-renewal", callback_data="cancel:autorenew")],
                [InlineKeyboardButton("❌ Cancel subscription completely", callback_data="cancel:full")],
                [InlineKeyboardButton("↩️ Back", callback_data="cancel:back")]
            ]
        else:
            buttons = [
                [InlineKeyboardButton("🔕 Désactiver le renouvellement auto", callback_data="cancel:autorenew")],
                [InlineKeyboardButton("❌ Annuler complètement", callback_data="cancel:full")],
                [InlineKeyboardButton("↩️ Retour", callback_data="cancel:back")]
            ]
        
        await update.message.reply_text(
            cancel_messages.get(lang, cancel_messages["ru"]),
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор варианта отмены."""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    data = query.data
    
    if not data.startswith("cancel:"):
        return
    
    action = data.split(":")[1]
    db = get_db()
    
    async with db.session() as session:
        db_user = await UserService.get_user(session, user.id)
        lang = db_user.language_code if db_user else "ru"
        
        active_sub = await SubscriptionService.get_active_subscription(session, user.id)
        
        if action == "back":
            await query.edit_message_text("✅ Отменено / Cancelled")
            return
        
        if not active_sub:
            await query.edit_message_text("❌ Подписка не найдена / Subscription not found")
            return
        
        if action == "autorenew":
            # Только отключаем авто-продление
            active_sub.auto_renew = False
            
            messages = {
                "ru": f"""
✅ **Авто-продление отключено**

Ваша подписка останется активной до **{active_sub.expires_at.strftime('%d.%m.%Y')}**.
После этой даты она не будет продлена автоматически.

Вы можете продлить вручную в любой момент: /subscribe
""",
                "en": f"""
✅ **Auto-renewal disabled**

Your subscription will remain active until **{active_sub.expires_at.strftime('%d.%m.%Y')}**.
It will not be renewed automatically after that date.

You can renew manually anytime: /subscribe
""",
                "fr": f"""
✅ **Renouvellement automatique désactivé**

Votre abonnement restera actif jusqu'au **{active_sub.expires_at.strftime('%d.%m.%Y')}**.
Il ne sera pas renouvelé automatiquement après cette date.

Vous pouvez renouveler manuellement à tout moment: /subscribe
"""
            }
            
            await query.edit_message_text(
                messages.get(lang, messages["ru"]),
                parse_mode="Markdown"
            )
        
        elif action == "full":
            # Полная отмена — подписка остаётся до конца оплаченного периода
            from datetime import datetime
            active_sub.auto_renew = False
            active_sub.cancelled_at = datetime.utcnow()
            
            messages = {
                "ru": f"""
❌ **Подписка отменена**

Вы сможете пользоваться ботом до **{active_sub.expires_at.strftime('%d.%m.%Y')}**.
После этой даты подписка не будет продлена.

Мы будем рады видеть вас снова! 💙
Восстановить подписку: /subscribe
""",
                "en": f"""
❌ **Subscription cancelled**

You can continue using the bot until **{active_sub.expires_at.strftime('%d.%m.%Y')}**.
The subscription will not be renewed after that date.

We'd love to have you back! 💙
Restore subscription: /subscribe
""",
                "fr": f"""
❌ **Abonnement annulé**

Vous pouvez continuer à utiliser le bot jusqu'au **{active_sub.expires_at.strftime('%d.%m.%Y')}**.
L'abonnement ne sera pas renouvelé après cette date.

Nous serions ravis de vous revoir! 💙
Restaurer l'abonnement: /subscribe
"""
            }
            
            await query.edit_message_text(
                messages.get(lang, messages["ru"]),
                parse_mode="Markdown"
            )


async def subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор плана подписки."""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    data = query.data
    
    if not data.startswith("subscribe:"):
        return
    
    action = data.split(":")[1]
    
    if action == "cancel":
        await query.edit_message_text("❌ Отменено / Cancelled")
        return
    
    plan_type = action
    if plan_type not in SUBSCRIPTION_PLANS:
        return
    
    plan = SUBSCRIPTION_PLANS[plan_type]
    db = get_db()
    
    async with db.session() as session:
        db_user = await UserService.get_user(session, user.id)
        lang = db_user.language_code if db_user else "ru"
    
    # Показываем выбор способа оплаты
    stars_price = plan.get('price_stars', 1000)
    
    payment_method_texts = {
        "ru": f"""
💰 **{plan.get('name_ru')}**
Сумма: **${plan['price_usd']:.0f}** или **{stars_price} ⭐**

Выберите способ оплаты:
""",
        "en": f"""
💰 **{plan.get('name_en')}**
Amount: **${plan['price_usd']:.0f}** or **{stars_price} ⭐**

Choose payment method:
""",
        "fr": f"""
💰 **{plan.get('name_fr')}**
Montant: **${plan['price_usd']:.0f}** ou **{stars_price} ⭐**

Choisissez le mode de paiement:
"""
    }
    
    await query.edit_message_text(
        payment_method_texts.get(lang, payment_method_texts["ru"]),
        reply_markup=get_payment_method_keyboard(plan_type, lang, stars_price),
        parse_mode="Markdown"
    )


async def payment_method_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор способа оплаты."""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    data = query.data
    
    if not data.startswith("paymethod:"):
        return
    
    parts = data.split(":")
    method = parts[1]  # card или crypto
    plan_type = parts[2]
    
    plan = SUBSCRIPTION_PLANS[plan_type]
    db = get_db()
    
    async with db.session() as session:
        db_user = await UserService.get_user(session, user.id)
        lang = db_user.language_code if db_user else "ru"
    
    if method == "stars":
        # Оплата через Telegram Stars
        await handle_stars_payment(query, context, user, plan_type, plan, lang)
    elif method == "card":
        # Оплата картой через Telegram Payments
        await handle_card_payment(query, context, user, plan_type, plan, lang)
    elif method == "crypto":
        # Оплата криптой
        await handle_crypto_payment(query, context, user, plan_type, plan, lang)


async def handle_stars_payment(query, context, user, plan_type: str, plan: dict, lang: str):
    """Обрабатывает оплату через Telegram Stars."""
    
    # Удаляем предыдущее сообщение
    await query.delete_message()
    
    # Создаём invoice для Stars
    title = plan.get(f"name_{lang}", plan["name_ru"])
    
    descriptions = {
        "ru": f"Полный доступ к боту психологической поддержки на {plan['duration_days']} дней",
        "en": f"Full access to psychological support bot for {plan['duration_days']} days",
        "fr": f"Accès complet au bot de soutien psychologique pendant {plan['duration_days']} jours"
    }
    
    stars_price = plan.get("price_stars", 1000)
    
    # Для Stars используем currency="XTR" и пустой provider_token
    await context.bot.send_invoice(
        chat_id=user.id,
        title=f"⭐ {title}",
        description=descriptions.get(lang, descriptions["ru"]),
        payload=f"stars:{plan_type}:{user.id}",
        provider_token="",  # Пустой для Stars
        currency="XTR",  # XTR = Telegram Stars
        prices=[LabeledPrice(label=title, amount=stars_price)],
        start_parameter=f"stars_{plan_type}"
    )


async def handle_card_payment(query, context, user, plan_type: str, plan: dict, lang: str):
    """Обрабатывает оплату банковской картой."""
    payment_token = os.getenv("PAYMENT_PROVIDER_TOKEN")
    
    if not payment_token:
        error_messages = {
            "ru": "❌ Оплата картой временно недоступна. Пожалуйста, используйте криптовалюту.",
            "en": "❌ Card payment is temporarily unavailable. Please use cryptocurrency.",
            "fr": "❌ Le paiement par carte est temporairement indisponible. Veuillez utiliser la cryptomonnaie."
        }
        await query.edit_message_text(error_messages.get(lang, error_messages["ru"]))
        return
    
    # Удаляем предыдущее сообщение
    await query.delete_message()
    
    # Создаём invoice
    title = plan.get(f"name_{lang}", plan["name_ru"])
    description = {
        "ru": f"Полный доступ к боту психологической поддержки на {plan['duration_days']} дней",
        "en": f"Full access to psychological support bot for {plan['duration_days']} days",
        "fr": f"Accès complet au bot de soutien psychologique pendant {plan['duration_days']} jours"
    }
    
    # Цена в копейках/центах (минимальная единица валюты)
    # Telegram Payments требует цену в минимальных единицах
    price_cents = int(plan["price_usd"] * 100)
    
    await context.bot.send_invoice(
        chat_id=user.id,
        title=title,
        description=description.get(lang, description["ru"]),
        payload=f"subscription:{plan_type}:{user.id}",
        provider_token=payment_token,
        currency="USD",
        prices=[LabeledPrice(label=title, amount=price_cents)],
        start_parameter=f"subscribe_{plan_type}",
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        is_flexible=False
    )


async def handle_crypto_payment(query, context, user, plan_type: str, plan: dict, lang: str):
    """Обрабатывает оплату криптовалютой."""
    db = get_db()
    
    async with db.session() as session:
        # Создаём pending payment
        payment = await PaymentService.create_pending_payment(
            session,
            user_id=user.id,
            plan_type=plan_type
        )
    
    wallet_address = os.getenv("WALLET_ADDRESS", "YOUR_WALLET_ADDRESS")
    currency = os.getenv("WALLET_CURRENCY", "USDT")
    
    # Удаляем предыдущее сообщение
    await query.delete_message()
    
    # Генерируем QR-код
    qr_buffer = generate_payment_qr(wallet_address, plan["price_usd"], currency)
    
    # Формируем сообщение
    crypto_messages = {
        "ru": f"""
🪙 **Оплата криптовалютой**

**План:** {plan['name_ru']}
**Сумма:** ${plan['price_usd']:.2f} {currency}

📱 **Отсканируйте QR-код** или скопируйте адрес:

`{wallet_address}`

После отправки средств нажмите кнопку ниже.
Платёж будет подтверждён автоматически (1-5 мин).
""",
        "en": f"""
🪙 **Cryptocurrency Payment**

**Plan:** {plan['name_en']}
**Amount:** ${plan['price_usd']:.2f} {currency}

📱 **Scan QR code** or copy address:

`{wallet_address}`

After sending funds, click the button below.
Payment will be confirmed automatically (1-5 min).
""",
        "fr": f"""
🪙 **Paiement en cryptomonnaie**

**Formule:** {plan['name_fr']}
**Montant:** ${plan['price_usd']:.2f} {currency}

📱 **Scannez le QR code** ou copiez l'adresse:

`{wallet_address}`

Après l'envoi, cliquez sur le bouton ci-dessous.
Le paiement sera confirmé automatiquement (1-5 min).
"""
    }
    
    # Отправляем QR-код с сообщением
    await context.bot.send_photo(
        chat_id=user.id,
        photo=InputFile(qr_buffer, filename="payment_qr.png"),
        caption=crypto_messages.get(lang, crypto_messages["ru"]),
        reply_markup=get_payment_confirmation_keyboard(lang),
        parse_mode="Markdown"
    )


async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает подтверждение оплаты пользователем."""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    data = query.data
    
    if not data.startswith("payment:"):
        return
    
    action = data.split(":")[1]
    db = get_db()
    
    async with db.session() as session:
        db_user = await UserService.get_user(session, user.id)
        lang = db_user.language_code if db_user else "ru"
        
        if action == "cancel":
            # Find and cancel pending payment
            payment = await PaymentService.get_user_pending_payment(session, user.id)
            if payment:
                payment.status = "cancelled"
            
            await query.edit_message_text("❌ Отменено / Cancelled")
            return
        
        if action == "confirm":
            # Get pending payment
            payment = await PaymentService.get_user_pending_payment(session, user.id)
            
            if not payment:
                await query.edit_message_text("❌ Платёж не найден / Payment not found")
                return
            
            # Сообщение об автоматической проверке
            auto_confirm_messages = {
                "ru": """
⏳ **Платёж проверяется автоматически**

Система проверяет поступление средств на кошелёк.
Как только платёж будет обнаружен, подписка активируется автоматически.

Обычно это занимает 1-5 минут.
Вы получите уведомление. 💙
""",
                "en": """
⏳ **Payment is being verified automatically**

The system is checking for incoming funds.
Once the payment is detected, your subscription will be activated automatically.

This usually takes 1-5 minutes.
You'll receive a notification. 💙
""",
                "fr": """
⏳ **Paiement en cours de vérification automatique**

Le système vérifie la réception des fonds.
Dès que le paiement sera détecté, votre abonnement sera activé automatiquement.

Cela prend généralement 1 à 5 minutes.
Vous recevrez une notification. 💙
"""
            }
            
            await query.edit_message_text(
                auto_confirm_messages.get(lang, auto_confirm_messages["ru"]),
                parse_mode="Markdown"
            )


async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает pre-checkout запрос от Telegram Payments."""
    query = update.pre_checkout_query
    
    # Проверяем, что payload валидный
    payload = query.invoice_payload
    if payload.startswith("subscription:") or payload.startswith("stars:") or payload.startswith("renewal:"):
        # Всё ок, подтверждаем
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Invalid payment")


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает успешный платёж через Telegram Payments (карты и Stars)."""
    payment = update.message.successful_payment
    user = update.effective_user
    
    # Парсим payload: "stars:plan_type:user_id" или "subscription:plan_type:user_id"
    payload = payment.invoice_payload
    parts = payload.split(":")
    
    if len(parts) < 2:
        logger.error(f"Invalid payment payload: {payload}")
        return
    
    payment_type = parts[0]  # "stars", "subscription", или "renewal"
    plan_type = parts[1]
    
    # Определяем тип оплаты для записи
    if payment_type == "stars":
        payment_note = f"Paid via Telegram Stars ({payment.total_amount} XTR)"
    else:
        payment_note = "Paid via Telegram Payments (card)"
    
    db = get_db()
    
    async with db.session() as session:
        db_user = await UserService.get_user(session, user.id)
        lang = db_user.language_code if db_user else "ru"
        
        # Создаём запись о платеже
        payment_record = await PaymentService.create_pending_payment(
            session,
            user_id=user.id,
            plan_type=plan_type
        )
        payment_record.status = "completed"
        payment_record.tx_hash = payment.telegram_payment_charge_id
        payment_record.note = payment_note
        
        # Активируем подписку
        subscription = await SubscriptionService.create_subscription(
            session,
            user_id=user.id,
            plan_type=plan_type,
            payment_id=str(payment_record.id)
        )
        
        plan = SUBSCRIPTION_PLANS[plan_type]
        
        success_messages = {
            "ru": f"""
✅ **Оплата прошла успешно!**

**План:** {plan['name_ru']}
**Действует до:** {subscription.expires_at.strftime('%d.%m.%Y')}

Спасибо за покупку! 💙
Теперь у вас неограниченный доступ.
""",
            "en": f"""
✅ **Payment successful!**

**Plan:** {plan['name_en']}
**Valid until:** {subscription.expires_at.strftime('%d.%m.%Y')}

Thank you for your purchase! 💙
You now have unlimited access.
""",
            "fr": f"""
✅ **Paiement réussi!**

**Formule:** {plan['name_fr']}
**Valable jusqu'au:** {subscription.expires_at.strftime('%d.%m.%Y')}

Merci pour votre achat! 💙
Vous avez maintenant un accès illimité.
"""
        }
        
        await update.message.reply_text(
            success_messages.get(lang, success_messages["ru"]),
            parse_mode="Markdown"
        )
        
        logger.info(f"Card payment successful for user {user.id}, plan {plan_type}")


def register_subscription_handlers(application):
    """Регистрирует обработчики подписки."""
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(subscription_callback, pattern=r"^subscribe:"))
    application.add_handler(CallbackQueryHandler(payment_method_callback, pattern=r"^paymethod:"))
    application.add_handler(CallbackQueryHandler(payment_callback, pattern=r"^payment:"))
    application.add_handler(CallbackQueryHandler(cancel_callback, pattern=r"^cancel:"))
    
    # Telegram Payments handlers
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
