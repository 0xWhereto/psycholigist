"""
Admin handlers for payment confirmation.
"""
import logging
import os

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler

from bot.services.database import get_db
from bot.services.subscription_service import PaymentService, SubscriptionService, SUBSCRIPTION_PLANS
from bot.services.user_service import UserService
from bot.utils.texts import get_text
from bot.utils.keyboards import get_admin_payment_keyboard

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь админом."""
    admin_id = os.getenv("ADMIN_USER_ID")
    return admin_id and str(user_id) == admin_id


async def admin_payments_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список ожидающих платежей."""
    user = update.effective_user
    
    if not is_admin(user.id):
        return
    
    db = get_db()
    
    async with db.session() as session:
        pending_payments = await PaymentService.get_pending_payments(session)
        
        if not pending_payments:
            await update.message.reply_text("✅ Нет ожидающих платежей")
            return
        
        for payment in pending_payments:
            payer = await UserService.get_user(session, payment.user_id)
            plan = SUBSCRIPTION_PLANS[payment.plan_type]
            
            text = f"""
🔔 **Платёж #{payment.id}**

**Пользователь:** {payment.user_id}
**Username:** @{payer.username if payer else 'N/A'}
**План:** {plan['name_ru']}
**Сумма:** ${payment.amount_usd:.2f}
**Создан:** {payment.created_at.strftime('%d.%m.%Y %H:%M')}
"""
            await update.message.reply_text(
                text,
                reply_markup=get_admin_payment_keyboard(payment.id),
                parse_mode="Markdown"
            )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает действия админа."""
    query = update.callback_query
    user = update.effective_user
    
    if not is_admin(user.id):
        await query.answer("⛔ Недостаточно прав", show_alert=True)
        return
    
    await query.answer()
    
    data = query.data
    if not data.startswith("admin:"):
        return
    
    parts = data.split(":")
    action = parts[1]
    payment_id = int(parts[2])
    
    db = get_db()
    
    async with db.session() as session:
        if action == "confirm":
            try:
                payment, subscription = await PaymentService.confirm_payment(
                    session,
                    payment_id=payment_id,
                    admin_id=user.id
                )
                
                # Notify user
                payer = await UserService.get_user(session, payment.user_id)
                plan = SUBSCRIPTION_PLANS[payment.plan_type]
                lang = payer.language_code if payer else "ru"
                
                try:
                    await context.bot.send_message(
                        chat_id=payment.user_id,
                        text=get_text(
                            "subscription_activated",
                            lang,
                            plan_name=plan.get(f"name_{lang}", plan["name_ru"]),
                            expires_at=subscription.expires_at.strftime("%d.%m.%Y")
                        ),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {payment.user_id}: {e}")
                
                await query.edit_message_text(
                    f"✅ Платёж #{payment_id} подтверждён.\n"
                    f"Подписка активирована для пользователя {payment.user_id}."
                )
                
            except ValueError as e:
                await query.edit_message_text(f"❌ Ошибка: {e}")
        
        elif action == "reject":
            try:
                payment = await PaymentService.cancel_payment(
                    session,
                    payment_id=payment_id,
                    admin_id=user.id,
                    reason="Rejected by admin"
                )
                
                # Notify user
                try:
                    await context.bot.send_message(
                        chat_id=payment.user_id,
                        text="❌ К сожалению, ваш платёж не был подтверждён. "
                             "Если вы считаете, что это ошибка, свяжитесь с поддержкой."
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {payment.user_id}: {e}")
                
                await query.edit_message_text(f"❌ Платёж #{payment_id} отклонён.")
                
            except ValueError as e:
                await query.edit_message_text(f"❌ Ошибка: {e}")


async def admin_grant_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Выдаёт подписку пользователю вручную.
    Использование: /grant <user_id> <plan_type>
    Пример: /grant 123456789 monthly
    """
    user = update.effective_user
    
    if not is_admin(user.id):
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Использование: /grant <user_id> <plan_type>\n"
            "Пример: /grant 123456789 monthly\n"
            "Планы: monthly, yearly"
        )
        return
    
    try:
        target_user_id = int(args[0])
        plan_type = args[1]
    except ValueError:
        await update.message.reply_text("❌ Неверный user_id")
        return
    
    if plan_type not in SUBSCRIPTION_PLANS:
        await update.message.reply_text(f"❌ Неверный план. Доступные: {', '.join(SUBSCRIPTION_PLANS.keys())}")
        return
    
    db = get_db()
    
    async with db.session() as session:
        # Ensure user exists
        await UserService.get_or_create_user(session, target_user_id)
        
        # Create subscription
        subscription = await SubscriptionService.create_subscription(
            session,
            user_id=target_user_id,
            plan_type=plan_type
        )
        
        plan = SUBSCRIPTION_PLANS[plan_type]
        
        # Notify target user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=get_text(
                    "subscription_activated",
                    "ru",
                    plan_name=plan["name_ru"],
                    expires_at=subscription.expires_at.strftime("%d.%m.%Y")
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to notify user {target_user_id}: {e}")
        
        await update.message.reply_text(
            f"✅ Подписка выдана!\n"
            f"Пользователь: {target_user_id}\n"
            f"План: {plan['name_ru']}\n"
            f"До: {subscription.expires_at.strftime('%d.%m.%Y')}"
        )


def register_admin_handlers(application):
    """Регистрирует обработчики админа."""
    application.add_handler(CommandHandler("payments", admin_payments_command))
    application.add_handler(CommandHandler("grant", admin_grant_command))
    application.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin:"))
