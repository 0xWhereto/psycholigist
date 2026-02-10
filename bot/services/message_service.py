"""
Message service - conversation history management.
"""
import logging
from datetime import datetime

from sqlalchemy import select, desc, func, asc
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
    async def get_message_count(session: AsyncSession, user_id: int) -> int:
        """Возвращает количество сообщений пользователя."""
        result = await session.execute(
            select(func.count(Message.id)).where(Message.user_id == user_id)
        )
        return result.scalar() or 0
    
    @staticmethod
    async def get_old_messages(
        session: AsyncSession,
        user_id: int,
        offset: int = 20
    ) -> list[dict]:
        """
        Получает старые сообщения (те, что НЕ входят в последние `offset`).
        Возвращает в хронологическом порядке.
        """
        # Находим ID последних `offset` сообщений
        recent_ids_query = (
            select(Message.id)
            .where(Message.user_id == user_id)
            .order_by(desc(Message.created_at))
            .limit(offset)
        )
        
        # Берём все остальные
        result = await session.execute(
            select(Message)
            .where(Message.user_id == user_id)
            .where(Message.id.not_in(recent_ids_query))
            .order_by(asc(Message.created_at))
        )
        messages = list(result.scalars().all())
        
        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
    
    @staticmethod
    async def trim_old_messages(
        session: AsyncSession,
        user_id: int,
        keep: int = 20
    ) -> int:
        """
        Удаляет старые сообщения, оставляя последние `keep`.
        Возвращает количество удалённых.
        """
        # Находим ID последних `keep` сообщений
        recent_ids_result = await session.execute(
            select(Message.id)
            .where(Message.user_id == user_id)
            .order_by(desc(Message.created_at))
            .limit(keep)
        )
        recent_ids = [row[0] for row in recent_ids_result.fetchall()]
        
        if not recent_ids:
            return 0
        
        # Удаляем все остальные
        old_result = await session.execute(
            select(Message)
            .where(Message.user_id == user_id)
            .where(Message.id.not_in(recent_ids))
        )
        old_messages = list(old_result.scalars().all())
        
        count = len(old_messages)
        for msg in old_messages:
            await session.delete(msg)
        
        logger.info(f"Trimmed {count} old messages for user {user_id}, kept {keep}")
        return count
    
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
