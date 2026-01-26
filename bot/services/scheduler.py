"""
Background scheduler for subscription management.
- Reminders before expiry
- Auto-renewal invoices
- Deactivation of expired subscriptions
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta

from sqlalchemy import select, and_
from telegram import Bot, LabeledPrice

from bot.services.database import get_db
from bot.services.subscription_service import SubscriptionService, SUBSCRIPTION_PLANS
from bot.services.user_service import UserService
from bot.models import Subscription

logger = logging.getLogger(__name__)


class SubscriptionScheduler:
    """Планировщик задач для управления подписками."""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self._running = False
    
    async def start(self):
        """Запускает планировщик."""
        self._running = True
        logger.info("Subscription scheduler started")
        
        while self._running:
            try:
                await self.run_tasks()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            
            # Проверяем каждый час
            await asyncio.sleep(3600)
    
    async def stop(self):
        """Останавливает планировщик."""
        self._running = False
        logger.info("Subscription scheduler stopped")
    
    async def run_tasks(self):
        """Выполняет все запланированные задачи."""
        logger.info("Running scheduled tasks...")
        
        await self.send_expiry_reminders()
        await self.send_auto_renewal_invoices()
        await self.deactivate_expired_subscriptions()
    
    async def send_expiry_reminders(self):
        """Отправляет напоминания об истечении подписки."""
        db = get_db()
        
        async with db.session() as session:
            # 3 дня до окончания
            await self._send_reminder(session, days=3, reminder_field="reminder_3_days_sent")
            # 1 день до окончания
            await self._send_reminder(session, days=1, reminder_field="reminder_1_day_sent")
            # День истечения
            await self._send_reminder(session, days=0, reminder_field="reminder_expired_sent")
    
    async def _send_reminder(self, session, days: int, reminder_field: str):
        """Отправляет напоминания для подписок, истекающих через N дней."""
        target_date = datetime.utcnow() + timedelta(days=days)
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Находим подписки, для которых ещё не отправлено напоминание
        result = await session.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.is_active == True,
                    Subscription.expires_at >= start_of_day,
                    Subscription.expires_at <= end_of_day,
                    getattr(Subscription, reminder_field) == False
                )
            )
        )
        
        subscriptions = list(result.scalars().all())
        
        for sub in subscriptions:
            try:
                user = await UserService.get_user(session, sub.user_id)
                lang = user.language_code if user else "ru"
                
                if days == 3:
                    message = self._get_reminder_message(lang, "3_days", sub.expires_at)
                elif days == 1:
                    message = self._get_reminder_message(lang, "1_day", sub.expires_at)
                else:
                    message = self._get_reminder_message(lang, "expired", sub.expires_at)
                
                await self.bot.send_message(
                    chat_id=sub.user_id,
                    text=message,
                    parse_mode="Markdown"
                )
                
                # Отмечаем, что напоминание отправлено
                setattr(sub, reminder_field, True)
                logger.info(f"Sent {days}-day reminder to user {sub.user_id}")
                
            except Exception as e:
                logger.error(f"Failed to send reminder to user {sub.user_id}: {e}")
    
    def _get_reminder_message(self, lang: str, reminder_type: str, expires_at: datetime) -> str:
        """Возвращает текст напоминания."""
        expires_str = expires_at.strftime("%d.%m.%Y")
        
        messages = {
            "3_days": {
                "ru": f"⏰ Ваша подписка истекает через 3 дня ({expires_str}).\n\nПродлить: /subscribe",
                "en": f"⏰ Your subscription expires in 3 days ({expires_str}).\n\nRenew: /subscribe",
                "fr": f"⏰ Votre abonnement expire dans 3 jours ({expires_str}).\n\nRenouveler: /subscribe"
            },
            "1_day": {
                "ru": f"⏰ Ваша подписка истекает завтра ({expires_str})!\n\nПродлить сейчас: /subscribe",
                "en": f"⏰ Your subscription expires tomorrow ({expires_str})!\n\nRenew now: /subscribe",
                "fr": f"⏰ Votre abonnement expire demain ({expires_str})!\n\nRenouveler maintenant: /subscribe"
            },
            "expired": {
                "ru": f"⚠️ Ваша подписка истекла.\n\nУ вас есть 3 дня грейс-периода.\nПродлить: /subscribe",
                "en": f"⚠️ Your subscription has expired.\n\nYou have 3 days grace period.\nRenew: /subscribe",
                "fr": f"⚠️ Votre abonnement a expiré.\n\nVous avez 3 jours de grâce.\nRenouveler: /subscribe"
            }
        }
        
        return messages.get(reminder_type, {}).get(lang, messages[reminder_type]["ru"])
    
    async def send_auto_renewal_invoices(self):
        """Отправляет счета на авто-продление за 1 день до окончания."""
        db = get_db()
        payment_token = os.getenv("PAYMENT_PROVIDER_TOKEN")
        
        if not payment_token:
            return  # Авто-продление работает только с картами
        
        async with db.session() as session:
            # Подписки, истекающие завтра, с включённым авто-продлением
            target_date = datetime.utcnow() + timedelta(days=1)
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            result = await session.execute(
                select(Subscription)
                .where(
                    and_(
                        Subscription.is_active == True,
                        Subscription.auto_renew == True,
                        Subscription.auto_renew_invoice_sent == False,
                        Subscription.cancelled_at == None,
                        Subscription.expires_at >= start_of_day,
                        Subscription.expires_at <= end_of_day
                    )
                )
            )
            
            subscriptions = list(result.scalars().all())
            
            for sub in subscriptions:
                try:
                    user = await UserService.get_user(session, sub.user_id)
                    lang = user.language_code if user else "ru"
                    plan = SUBSCRIPTION_PLANS[sub.plan_type]
                    
                    # Отправляем счёт на продление
                    title = {
                        "ru": f"🔄 Продление: {plan['name_ru']}",
                        "en": f"🔄 Renewal: {plan['name_en']}",
                        "fr": f"🔄 Renouvellement: {plan['name_fr']}"
                    }
                    
                    description = {
                        "ru": "Ваша подписка истекает завтра. Оплатите для продления.",
                        "en": "Your subscription expires tomorrow. Pay to renew.",
                        "fr": "Votre abonnement expire demain. Payez pour renouveler."
                    }
                    
                    price_cents = int(plan["price_usd"] * 100)
                    
                    await self.bot.send_message(
                        chat_id=sub.user_id,
                        text=self._get_auto_renew_message(lang),
                        parse_mode="Markdown"
                    )
                    
                    await self.bot.send_invoice(
                        chat_id=sub.user_id,
                        title=title.get(lang, title["ru"]),
                        description=description.get(lang, description["ru"]),
                        payload=f"renewal:{sub.plan_type}:{sub.user_id}",
                        provider_token=payment_token,
                        currency="USD",
                        prices=[LabeledPrice(label=title.get(lang, title["ru"]), amount=price_cents)],
                        start_parameter=f"renew_{sub.plan_type}"
                    )
                    
                    sub.auto_renew_invoice_sent = True
                    logger.info(f"Sent auto-renewal invoice to user {sub.user_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to send renewal invoice to user {sub.user_id}: {e}")
    
    def _get_auto_renew_message(self, lang: str) -> str:
        """Сообщение перед счётом на авто-продление."""
        messages = {
            "ru": """
🔄 **Авто-продление подписки**

Ваша подписка истекает завтра.
Ниже счёт для продления — просто оплатите его, чтобы продолжить пользоваться ботом.

Чтобы отключить авто-продление: /cancel
""",
            "en": """
🔄 **Auto-renewal**

Your subscription expires tomorrow.
Below is the renewal invoice — just pay it to continue using the bot.

To disable auto-renewal: /cancel
""",
            "fr": """
🔄 **Renouvellement automatique**

Votre abonnement expire demain.
Ci-dessous la facture de renouvellement — payez-la pour continuer à utiliser le bot.

Pour désactiver le renouvellement automatique: /cancel
"""
        }
        return messages.get(lang, messages["ru"])
    
    async def deactivate_expired_subscriptions(self):
        """Деактивирует подписки после грейс-периода."""
        db = get_db()
        grace_days = int(os.getenv("GRACE_PERIOD_DAYS", "3"))
        
        async with db.session() as session:
            count = await SubscriptionService.deactivate_expired_subscriptions(session, grace_days)
            if count > 0:
                logger.info(f"Deactivated {count} expired subscriptions")


# Global instance
scheduler: SubscriptionScheduler | None = None


def get_scheduler() -> SubscriptionScheduler | None:
    return scheduler


def init_scheduler(bot: Bot) -> SubscriptionScheduler:
    global scheduler
    scheduler = SubscriptionScheduler(bot)
    return scheduler
