"""
Subscription model.
"""
from datetime import datetime
from sqlalchemy import BigInteger, String, Boolean, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Subscription(Base):
    """Модель подписки пользователя."""
    
    __tablename__ = "subscriptions"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    
    plan_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'monthly' или 'yearly'
    price_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Напоминания отправлены
    reminder_3_days_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_1_day_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_expired_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Авто-продление
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_renew_invoice_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Отмена
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")
    
    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, user_id={self.user_id}, plan={self.plan_type}, expires={self.expires_at})>"
    
    @property
    def is_expired(self) -> bool:
        """Проверяет, истекла ли подписка."""
        return datetime.utcnow() > self.expires_at
    
    @property
    def days_remaining(self) -> int:
        """Возвращает количество оставшихся дней."""
        if self.is_expired:
            return 0
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)
