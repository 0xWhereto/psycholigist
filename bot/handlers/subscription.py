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
from bot.utils.keyboards import get_subscription_keyboard, get_payment_confirmation_keyboard, get_payment_keyboard
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
    """Обрабатывает выбор плана подписки — сразу показывает адрес для оплаты."""
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
    
    try:
        plan = SUBSCRIPTION_PLANS[plan_type]
        db = get_db()
        wallet_address = os.getenv("WALLET_ADDRESS", "")
        
        async with db.session() as session:
            db_user = await UserService.get_user(session, user.id)
            lang = db_user.language_code if db_user else "ru"
            
            # Создаём pending payment сразу
            payment = await PaymentService.create_pending_payment(
                session,
                user_id=user.id,
                plan_type=plan_type
            )
            payment_id = payment.id
        
        price_usd = plan.get('price_usd', 20)
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        payment_texts = {
            "ru": (
                "💳 <b>Оплата подписки</b>\n\n"
                f"<b>План:</b> {plan['name_ru']}\n"
                f"<b>Сумма:</b> {price_usd:.0f} USDT\n\n"
                f"📋 <b>Адрес для перевода:</b>\n"
                f"<code>{wallet_address}</code>\n\n"
                f"1️⃣ Нажмите «Открыть кошелёк»\n"
                f"2️⃣ Отправьте <b>{price_usd:.0f} USDT</b> на адрес выше\n"
                f"3️⃣ После перевода нажмите «Я оплатил(а)»\n\n"
                f"⚠️ <b>Нет USDT?</b>\n"
                f"В @wallet нажмите «Пополнить» → купите USDT картой"
            ),
            "en": (
                "💳 <b>Subscription Payment</b>\n\n"
                f"<b>Plan:</b> {plan['name_en']}\n"
                f"<b>Amount:</b> {price_usd:.0f} USDT\n\n"
                f"📋 <b>Transfer address:</b>\n"
                f"<code>{wallet_address}</code>\n\n"
                f"1️⃣ Click «Open Wallet»\n"
                f"2️⃣ Send <b>{price_usd:.0f} USDT</b> to the address above\n"
                f"3️⃣ After transfer click «I've paid»\n\n"
                f"⚠️ <b>No USDT?</b>\n"
                f"In @wallet click «Top up» → buy USDT with card"
            ),
            "fr": (
                "💳 <b>Paiement d'abonnement</b>\n\n"
                f"<b>Formule:</b> {plan['name_fr']}\n"
                f"<b>Montant:</b> {price_usd:.0f} USDT\n\n"
                f"📋 <b>Adresse de transfert:</b>\n"
                f"<code>{wallet_address}</code>\n\n"
                f"1️⃣ Cliquez sur «Ouvrir le portefeuille»\n"
                f"2️⃣ Envoyez <b>{price_usd:.0f} USDT</b> à l'adresse ci-dessus\n"
                f"3️⃣ Après le transfert, cliquez «J'ai payé»\n\n"
                f"⚠️ <b>Pas d'USDT?</b>\n"
                f"Dans @wallet cliquez «Recharger» → achetez USDT par carte"
            ),
        }
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "💰 Открыть кошелёк" if lang == "ru" else "💰 Open Wallet" if lang == "en" else "💰 Ouvrir le portefeuille",
                url="https://t.me/wallet"
            )],
            [InlineKeyboardButton(
                "✅ Я оплатил(а)" if lang == "ru" else "✅ I've paid" if lang == "en" else "✅ J'ai payé",
                callback_data=f"payment:confirm:{payment_id}"
            )],
            [InlineKeyboardButton(
                "❌ Отмена" if lang == "ru" else "❌ Cancel" if lang == "en" else "❌ Annuler",
                callback_data="subscribe:cancel"
            )]
        ])
        
        await query.edit_message_text(
            payment_texts.get(lang, payment_texts["ru"]),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    except Exception as e:
        logger.error(f"subscription_callback error for user {user.id}: {e}", exc_info=True)
        try:
            await query.edit_message_text(
                f"❌ Произошла ошибка. Попробуйте позже или напишите /subscribe\n\nОшибка: {e}"
            )
        except Exception:
            pass


async def pay_usdt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатие кнопки оплаты USDT."""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    data = query.data
    
    if not data.startswith("pay:usdt:"):
        return
    
    parts = data.split(":")
    plan_type = parts[2]
    
    plan = SUBSCRIPTION_PLANS[plan_type]
    db = get_db()
    wallet_address = os.getenv("WALLET_ADDRESS", "")
    
    async with db.session() as session:
        db_user = await UserService.get_user(session, user.id)
        lang = db_user.language_code if db_user else "ru"
        
        # Создаём pending payment
        payment = await PaymentService.create_pending_payment(
            session,
            user_id=user.id,
            plan_type=plan_type
        )
    
    price_usd = plan.get('price_usd', 20)
    
    # Генерируем ссылку на Telegram Wallet
    # Формат: https://t.me/wallet?startattach=transfer_{address}
    wallet_link = f"https://t.me/wallet?startattach=send-USDT-TON-{wallet_address}-{int(price_usd)}"
    
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    payment_messages = {
        "ru": f"""
💳 **Оплата подписки**

**План:** {plan['name_ru']}
**Сумма:** {price_usd:.0f} USDT

📋 **Адрес для перевода:**
`{wallet_address}`

1️⃣ Нажмите "Открыть кошелёк"
2️⃣ Отправьте **{price_usd:.0f} USDT** на адрес выше
3️⃣ После перевода нажмите "Я оплатил(а)"

⚠️ **Нет USDT?**
В @wallet нажмите "Пополнить" → купите USDT картой
""",
        "en": f"""
💳 **Subscription Payment**

**Plan:** {plan['name_en']}
**Amount:** {price_usd:.0f} USDT

📋 **Transfer address:**
`{wallet_address}`

1️⃣ Click "Open Wallet"
2️⃣ Send **{price_usd:.0f} USDT** to the address above
3️⃣ After transfer click "I've paid"

⚠️ **No USDT?**
In @wallet click "Top up" → buy USDT with card
""",
        "fr": f"""
💳 **Paiement d'abonnement**

**Formule:** {plan['name_fr']}
**Montant:** {price_usd:.0f} USDT

📋 **Adresse de transfert:**
`{wallet_address}`

1️⃣ Cliquez sur "Ouvrir le portefeuille"
2️⃣ Envoyez **{price_usd:.0f} USDT** à l'adresse ci-dessus
3️⃣ Après le transfert, cliquez "J'ai payé"

⚠️ **Pas d'USDT?**
Dans @wallet cliquez "Recharger" → achetez USDT par carte
"""
    }
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "💰 Открыть кошелёк" if lang == "ru" else "💰 Open Wallet" if lang == "en" else "💰 Ouvrir le portefeuille",
            url="https://t.me/wallet"
        )],
        [InlineKeyboardButton(
            "✅ Я оплатил(а)" if lang == "ru" else "✅ I've paid" if lang == "en" else "✅ J'ai payé",
            callback_data=f"payment:confirm:{payment.id}"
        )],
        [InlineKeyboardButton(
            "❌ Отмена" if lang == "ru" else "❌ Cancel" if lang == "en" else "❌ Annuler",
            callback_data="subscribe:cancel"
        )]
    ])
    
    await query.edit_message_text(
        payment_messages.get(lang, payment_messages["ru"]),
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def handle_card_payment(query, context, user, plan_type: str, plan: dict, lang: str):
    """Обрабатывает оплату картой через Crypto Pay (конвертация в крипту)."""
    from bot.services.crypto_pay import get_crypto_pay
    
    crypto_pay = get_crypto_pay()
    
    if not crypto_pay:
        error_messages = {
            "ru": "❌ Оплата картой временно недоступна. Пожалуйста, используйте криптовалюту.",
            "en": "❌ Card payment is temporarily unavailable. Please use cryptocurrency.",
            "fr": "❌ Le paiement par carte est temporairement indisponible. Veuillez utiliser la cryptomonnaie."
        }
        await query.edit_message_text(error_messages.get(lang, error_messages["ru"]))
        return
    
    db = get_db()
    
    async with db.session() as session:
        # Создаём pending payment
        payment = await PaymentService.create_pending_payment(
            session,
            user_id=user.id,
            plan_type=plan_type
        )
    
    try:
        # Создаём инвойс в Crypto Pay
        title = plan.get(f"name_{lang}", plan["name_ru"])
        
        invoice = await crypto_pay.create_invoice(
            amount=plan["price_usd"],
            currency="USDT",
            description=f"{title} - Психолог-бот",
            payload=f"card:{plan_type}:{user.id}:{payment.id}",
            expires_in=3600  # 1 час
        )
        
        pay_url = invoice.get("pay_url")
        invoice_id = invoice.get("invoice_id")
        
        # Сохраняем invoice_id в payment
        async with db.session() as session:
            from sqlalchemy import select
            from bot.models import Payment
            result = await session.execute(
                select(Payment).where(Payment.id == payment.id)
            )
            p = result.scalar_one()
            p.tx_hash = str(invoice_id)
            p.note = "Crypto Pay invoice"
        
        # Удаляем предыдущее сообщение
        await query.delete_message()
        
        # Отправляем ссылку на оплату
        card_messages = {
            "ru": f"""
💳 **Оплата картой**

**План:** {plan['name_ru']}
**Сумма:** ${plan['price_usd']:.2f}

Нажмите кнопку ниже для оплаты.
Принимаются Visa, MasterCard и криптовалюта.

После оплаты подписка активируется автоматически!
""",
            "en": f"""
💳 **Card Payment**

**Plan:** {plan['name_en']}
**Amount:** ${plan['price_usd']:.2f}

Click the button below to pay.
Visa, MasterCard and cryptocurrency accepted.

Subscription will be activated automatically after payment!
""",
            "fr": f"""
💳 **Paiement par carte**

**Formule:** {plan['name_fr']}
**Montant:** ${plan['price_usd']:.2f}

Cliquez sur le bouton ci-dessous pour payer.
Visa, MasterCard et cryptomonnaie acceptés.

L'abonnement sera activé automatiquement après le paiement!
"""
        }
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        pay_button_text = {
            "ru": "💳 Оплатить",
            "en": "💳 Pay Now",
            "fr": "💳 Payer"
        }
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                pay_button_text.get(lang, pay_button_text["ru"]),
                url=pay_url
            )],
            [InlineKeyboardButton(
                "✅ Я оплатил(а)" if lang == "ru" else "✅ I've paid" if lang == "en" else "✅ J'ai payé",
                callback_data=f"checkpay:{invoice_id}:{payment.id}"
            )]
        ])
        
        await context.bot.send_message(
            chat_id=user.id,
            text=card_messages.get(lang, card_messages["ru"]),
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Crypto Pay error: {e}")
        error_messages = {
            "ru": "❌ Ошибка создания платежа. Попробуйте позже или используйте криптовалюту.",
            "en": "❌ Error creating payment. Please try later or use cryptocurrency.",
            "fr": "❌ Erreur lors de la création du paiement. Réessayez plus tard ou utilisez la cryptomonnaie."
        }
        await query.edit_message_text(error_messages.get(lang, error_messages["ru"]))


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


async def check_crypto_pay_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет оплату через Crypto Pay."""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    data = query.data
    
    if not data.startswith("checkpay:"):
        return
    
    parts = data.split(":")
    invoice_id = int(parts[1])
    payment_id = int(parts[2])
    
    from bot.services.crypto_pay import get_crypto_pay
    crypto_pay = get_crypto_pay()
    
    if not crypto_pay:
        await query.edit_message_text("❌ Ошибка проверки платежа")
        return
    
    db = get_db()
    
    async with db.session() as session:
        db_user = await UserService.get_user(session, user.id)
        lang = db_user.language_code if db_user else "ru"
    
    try:
        # Проверяем статус инвойса
        is_paid = await crypto_pay.check_invoice_paid(invoice_id)
        
        if is_paid:
            async with db.session() as session:
                from sqlalchemy import select
                from bot.models import Payment
                
                result = await session.execute(
                    select(Payment).where(Payment.id == payment_id)
                )
                payment = result.scalar_one_or_none()
                
                if payment and payment.status != "completed":
                    payment.status = "completed"
                    payment.note = "Paid via Crypto Pay (card)"
                    
                    # Создаём подписку
                    subscription = await SubscriptionService.create_subscription(
                        session,
                        user_id=user.id,
                        plan_type=payment.plan_type,
                        payment_id=str(payment.id)
                    )
                    
                    plan = SUBSCRIPTION_PLANS[payment.plan_type]
                    
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
                    
                    await query.edit_message_text(
                        success_messages.get(lang, success_messages["ru"]),
                        parse_mode="Markdown"
                    )
                else:
                    await query.edit_message_text(
                        "✅ Подписка уже активирована!" if lang == "ru" else "✅ Subscription already activated!"
                    )
        else:
            # Не оплачено ещё
            pending_messages = {
                "ru": "⏳ Платёж ещё не получен. Если вы уже оплатили, подождите 1-2 минуты и нажмите снова.",
                "en": "⏳ Payment not received yet. If you've already paid, wait 1-2 minutes and try again.",
                "fr": "⏳ Paiement non reçu. Si vous avez déjà payé, attendez 1-2 minutes et réessayez."
            }
            await query.answer(pending_messages.get(lang, pending_messages["ru"]), show_alert=True)
    
    except Exception as e:
        logger.error(f"Error checking Crypto Pay invoice: {e}")
        await query.answer("❌ Ошибка проверки. Попробуйте позже.", show_alert=True)


def register_subscription_handlers(application):
    """Регистрирует обработчики подписки."""
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(subscription_callback, pattern=r"^subscribe:"))
    application.add_handler(CallbackQueryHandler(pay_usdt_callback, pattern=r"^pay:usdt:"))
    application.add_handler(CallbackQueryHandler(payment_callback, pattern=r"^payment:"))
    application.add_handler(CallbackQueryHandler(cancel_callback, pattern=r"^cancel:"))
