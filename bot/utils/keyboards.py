"""
Inline keyboards for the bot.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.services.subscription_service import SUBSCRIPTION_PLANS


def get_subscription_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Возвращает клавиатуру выбора подписки."""
    monthly = SUBSCRIPTION_PLANS["monthly"]
    yearly = SUBSCRIPTION_PLANS["yearly"]
    
    if lang == "ru":
        buttons = [
            [InlineKeyboardButton(
                f"📅 Месяц — ${monthly['price_usd']:.0f}",
                callback_data="subscribe:monthly"
            )],
            [InlineKeyboardButton(
                f"📅 Год — ${yearly['price_usd']:.0f} (скидка 30%)",
                callback_data="subscribe:yearly"
            )],
            [InlineKeyboardButton("❌ Отмена", callback_data="subscribe:cancel")]
        ]
    elif lang == "en":
        buttons = [
            [InlineKeyboardButton(
                f"📅 Monthly — ${monthly['price_usd']:.0f}",
                callback_data="subscribe:monthly"
            )],
            [InlineKeyboardButton(
                f"📅 Yearly — ${yearly['price_usd']:.0f} (30% off)",
                callback_data="subscribe:yearly"
            )],
            [InlineKeyboardButton("❌ Cancel", callback_data="subscribe:cancel")]
        ]
    else:  # fr
        buttons = [
            [InlineKeyboardButton(
                f"📅 Mensuel — ${monthly['price_usd']:.0f}",
                callback_data="subscribe:monthly"
            )],
            [InlineKeyboardButton(
                f"📅 Annuel — ${yearly['price_usd']:.0f} (30% de réduction)",
                callback_data="subscribe:yearly"
            )],
            [InlineKeyboardButton("❌ Annuler", callback_data="subscribe:cancel")]
        ]
    
    return InlineKeyboardMarkup(buttons)


def get_payment_method_keyboard(plan_type: str, lang: str = "ru", stars_price: int = 0) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру выбора способа оплаты."""
    if lang == "ru":
        buttons = [
            [InlineKeyboardButton(
                f"⭐ Telegram Stars ({stars_price} ⭐)",
                callback_data=f"paymethod:stars:{plan_type}"
            )],
            [InlineKeyboardButton(
                "🪙 Криптовалюта (USDT/TON)",
                callback_data=f"paymethod:crypto:{plan_type}"
            )],
            [InlineKeyboardButton("❌ Отмена", callback_data="subscribe:cancel")]
        ]
    elif lang == "en":
        buttons = [
            [InlineKeyboardButton(
                f"⭐ Telegram Stars ({stars_price} ⭐)",
                callback_data=f"paymethod:stars:{plan_type}"
            )],
            [InlineKeyboardButton(
                "🪙 Cryptocurrency (USDT/TON)",
                callback_data=f"paymethod:crypto:{plan_type}"
            )],
            [InlineKeyboardButton("❌ Cancel", callback_data="subscribe:cancel")]
        ]
    else:  # fr
        buttons = [
            [InlineKeyboardButton(
                f"⭐ Telegram Stars ({stars_price} ⭐)",
                callback_data=f"paymethod:stars:{plan_type}"
            )],
            [InlineKeyboardButton(
                "🪙 Cryptomonnaie (USDT/TON)",
                callback_data=f"paymethod:crypto:{plan_type}"
            )],
            [InlineKeyboardButton("❌ Annuler", callback_data="subscribe:cancel")]
        ]
    
    return InlineKeyboardMarkup(buttons)


def get_payment_confirmation_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Возвращает клавиатуру подтверждения оплаты."""
    if lang == "ru":
        buttons = [
            [InlineKeyboardButton("✅ Я оплатил(а)", callback_data="payment:confirm")],
            [InlineKeyboardButton("❌ Отмена", callback_data="payment:cancel")]
        ]
    elif lang == "en":
        buttons = [
            [InlineKeyboardButton("✅ I've paid", callback_data="payment:confirm")],
            [InlineKeyboardButton("❌ Cancel", callback_data="payment:cancel")]
        ]
    else:  # fr
        buttons = [
            [InlineKeyboardButton("✅ J'ai payé", callback_data="payment:confirm")],
            [InlineKeyboardButton("❌ Annuler", callback_data="payment:cancel")]
        ]
    
    return InlineKeyboardMarkup(buttons)


def get_admin_payment_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для админа для подтверждения платежа."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"admin:confirm:{payment_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"admin:reject:{payment_id}")
        ]
    ])
