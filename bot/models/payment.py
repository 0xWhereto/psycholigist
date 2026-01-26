"""
Payment model.
"""
from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime, Numeric, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Payment(Base):
    """Модель платежа."""
    
    __tablename__ = "payments"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    
    amount_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USDT")  # USDT, TON
    
    # pending, awaiting_confirmation, completed, failed, cancelled
    status: Mapped[str] = mapped_column(String(20), default="pending")
    
    plan_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'monthly' или 'yearly'
    
    # Transaction hash если пользователь предоставил
    tx_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Комментарий от пользователя или админа
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # Admin user_id
    
    # Relationships
    user = relationship("User", back_populates="payments")
    
    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, user_id={self.user_id}, amount={self.amount_usd}, status={self.status})>"
