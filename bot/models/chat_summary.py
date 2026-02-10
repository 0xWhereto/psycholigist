"""
Chat summary model for long-term memory.
"""
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Text, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ChatSummary(Base):
    """Саммари диалога — долговременная память бота."""
    
    __tablename__ = "chat_summaries"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    
    # Накопительное саммари всех предыдущих разговоров
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Сколько сообщений было суммаризировано
    messages_summarized: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="chat_summaries")
    
    def __repr__(self) -> str:
        return f"<ChatSummary(id={self.id}, user_id={self.user_id})>"
