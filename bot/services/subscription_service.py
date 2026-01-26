"""
Subscription service - subscription management.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import User, Subscription, Payment

logger = logging.getLogger(__name__)


# Тарифные планы
# 1 Star ≈ $0.02, поэтому $20 ≈ 1000 Stars, $168 ≈ 8400 Stars
SUBSCRIPTION_PLANS = {
    "monthly": {
        "name_ru": "Месячная подписка",
        "name_en": "Monthly subscription",
        "name_fr": "Abonnement mensuel",
        "price_usd": 20.00,
        "price_stars": 1000,  # ~$20
        "duration_days": 30,
        "description_ru": "Полный доступ на 1 месяц",
    },
    "yearly": {
        "name_ru": "Годовая подписка",
        "name_en": "Yearly subscription",
        "name_fr": "Abonnement annuel",
        "price_usd": 168.00,
        "price_stars": 8400,  # ~$168
        "duration_days": 365,
        "description_ru": "Полный доступ на 1 год (скидка 30%)",
    }
}


class SubscriptionService:
    """Сервис для работы с подписками."""
    
    @staticmethod
    async def get_active_subscription(session: AsyncSession, user_id: int) -> Subscription | None:
        """Получает активную подписку пользователя."""
        result = await session.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.is_active == True,
                    Subscription.expires_at > datetime.utcnow()
                )
            )
            .order_by(Subscription.expires_at.desc())
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def has_active_subscription(session: AsyncSession, user_id: int) -> bool:
        """Проверяет, есть ли активная подписка."""
        sub = await SubscriptionService.get_active_subscription(session, user_id)
        return sub is not None
    
    @staticmethod
    async def is_in_grace_period(
        session: AsyncSession, 
        user_id: int, 
        grace_days: int = 3
    ) -> bool:
        """Проверяет, находится ли пользователь в грейс-периоде."""
        grace_threshold = datetime.utcnow() - timedelta(days=grace_days)
        
        result = await session.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.is_active == True,
                    Subscription.expires_at <= datetime.utcnow(),
                    Subscription.expires_at > grace_threshold
                )
            )
        )
        return result.scalar_one_or_none() is not None
    
    @staticmethod
    async def create_subscription(
        session: AsyncSession,
        user_id: int,
        plan_type: str,
        payment_id: str | None = None
    ) -> Subscription:
        """Создаёт новую подписку."""
        plan = SUBSCRIPTION_PLANS.get(plan_type)
        if not plan:
            raise ValueError(f"Unknown plan type: {plan_type}")
        
        # Деактивируем предыдущие подписки
        result = await session.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.is_active == True
                )
            )
        )
        for old_sub in result.scalars():
            old_sub.is_active = False
        
        now = datetime.utcnow()
        subscription = Subscription(
            user_id=user_id,
            plan_type=plan_type,
            price_usd=plan["price_usd"],
            started_at=now,
            expires_at=now + timedelta(days=plan["duration_days"]),
            is_active=True,
            payment_id=payment_id
        )
        session.add(subscription)
        await session.flush()
        
        logger.info(f"Created subscription for user {user_id}: {plan_type}")
        return subscription
    
    @staticmethod
    async def get_expiring_subscriptions(
        session: AsyncSession,
        days_until_expiry: int
    ) -> list[Subscription]:
        """Получает подписки, истекающие через N дней."""
        target_date = datetime.utcnow() + timedelta(days=days_until_expiry)
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        result = await session.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.is_active == True,
                    Subscription.expires_at >= start_of_day,
                    Subscription.expires_at <= end_of_day
                )
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def deactivate_expired_subscriptions(
        session: AsyncSession,
        grace_days: int = 3
    ) -> int:
        """Деактивирует просроченные подписки после грейс-периода."""
        grace_threshold = datetime.utcnow() - timedelta(days=grace_days)
        
        result = await session.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.is_active == True,
                    Subscription.expires_at < grace_threshold
                )
            )
        )
        
        count = 0
        for sub in result.scalars():
            sub.is_active = False
            count += 1
        
        if count > 0:
            logger.info(f"Deactivated {count} expired subscriptions")
        
        return count


class PaymentService:
    """Сервис для работы с платежами."""
    
    @staticmethod
    async def create_pending_payment(
        session: AsyncSession,
        user_id: int,
        plan_type: str,
        currency: str = "USDT"
    ) -> Payment:
        """Создаёт ожидающий платёж."""
        plan = SUBSCRIPTION_PLANS.get(plan_type)
        if not plan:
            raise ValueError(f"Unknown plan type: {plan_type}")
        
        payment = Payment(
            user_id=user_id,
            amount_usd=plan["price_usd"],
            currency=currency,
            status="awaiting_confirmation",
            plan_type=plan_type
        )
        session.add(payment)
        await session.flush()
        
        logger.info(f"Created pending payment for user {user_id}: {plan_type}")
        return payment
    
    @staticmethod
    async def get_pending_payments(session: AsyncSession) -> list[Payment]:
        """Получает все ожидающие подтверждения платежи."""
        result = await session.execute(
            select(Payment)
            .where(Payment.status == "awaiting_confirmation")
            .order_by(Payment.created_at.asc())
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_user_pending_payment(session: AsyncSession, user_id: int) -> Payment | None:
        """Получает ожидающий платёж пользователя."""
        result = await session.execute(
            select(Payment)
            .where(
                and_(
                    Payment.user_id == user_id,
                    Payment.status == "awaiting_confirmation"
                )
            )
            .order_by(Payment.created_at.desc())
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def confirm_payment(
        session: AsyncSession,
        payment_id: int,
        admin_id: int
    ) -> tuple[Payment, Subscription]:
        """Подтверждает платёж и активирует подписку."""
        result = await session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        
        if not payment:
            raise ValueError(f"Payment not found: {payment_id}")
        
        if payment.status != "awaiting_confirmation":
            raise ValueError(f"Payment is not awaiting confirmation: {payment.status}")
        
        # Update payment
        payment.status = "completed"
        payment.confirmed_at = datetime.utcnow()
        payment.confirmed_by = admin_id
        
        # Create subscription
        subscription = await SubscriptionService.create_subscription(
            session,
            payment.user_id,
            payment.plan_type,
            payment_id=str(payment.id)
        )
        
        logger.info(f"Confirmed payment {payment_id} by admin {admin_id}")
        return payment, subscription
    
    @staticmethod
    async def cancel_payment(
        session: AsyncSession,
        payment_id: int,
        admin_id: int,
        reason: str | None = None
    ) -> Payment:
        """Отменяет платёж."""
        result = await session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        
        if not payment:
            raise ValueError(f"Payment not found: {payment_id}")
        
        payment.status = "cancelled"
        payment.confirmed_by = admin_id
        if reason:
            payment.note = reason
        
        logger.info(f"Cancelled payment {payment_id} by admin {admin_id}")
        return payment
