"""
Message service - conversation history management.
"""
import logging
from datetime import datetime

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Message

logger = logging.getLogger(__name__)


class MessageService:
    """Сервис для работы с историей сообщений."""
    
    @staticmethod
    async def add_message(
        session: AsyncSession,
        user_id: int,
        role: str,
        content: str
    ) -> Message:
        """Добавляет сообщение в историю."""
        message = Message(
            user_id=user_id,
            role=role,
            content=content
        )
        session.add(message)
        await session.flush()
        return message
    
    @staticmethod
    async def get_conversation_history(
        session: AsyncSession,
        user_id: int,
        limit: int = 20
    ) -> list[dict]:
        """
        Получает историю сообщений пользователя.
        Возвращает список в формате [{"role": "user/assistant", "content": "..."}]
        """
        result = await session.execute(
            select(Message)
            .where(Message.user_id == user_id)
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        messages = list(result.scalars().all())
        
        # Reverse to get chronological order
        messages.reverse()
        
        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
    
    @staticmethod
    async def clear_conversation(session: AsyncSession, user_id: int) -> int:
        """
        Очищает историю сообщений пользователя.
        Возвращает количество удалённых сообщений.
        """
        result = await session.execute(
            select(Message).where(Message.user_id == user_id)
        )
        messages = list(result.scalars().all())
        
        count = len(messages)
        for msg in messages:
            await session.delete(msg)
        
        logger.info(f"Cleared {count} messages for user {user_id}")
        return count
