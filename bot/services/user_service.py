"""
User service - user management.
"""
import logging
from datetime import datetime, date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import User

logger = logging.getLogger(__name__)


class UserService:
    """Сервис для работы с пользователями."""
    
    @staticmethod
    async def get_or_create_user(
        session: AsyncSession,
        user_id: int,
        username: str | None = None,
        first_name: str | None = None,
        language_code: str = "ru"
    ) -> User:
        """Получает или создаёт пользователя."""
        result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            user = User(
                user_id=user_id,
                username=username,
                first_name=first_name,
                language_code=language_code
            )
            session.add(user)
            await session.flush()
            logger.info(f"Created new user: {user_id}")
        else:
            # Update last interaction
            user.last_interaction = datetime.utcnow()
            if username:
                user.username = username
            if first_name:
                user.first_name = first_name
        
        return user
    
    @staticmethod
    async def get_user(session: AsyncSession, user_id: int) -> User | None:
        """Получает пользователя по ID."""
        result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_language(session: AsyncSession, user_id: int, lang_code: str) -> User | None:
        """Обновляет язык пользователя."""
        result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.language_code = lang_code
            logger.info(f"Updated language for user {user_id}: {lang_code}")
        return user
    
    @staticmethod
    async def increment_free_messages(session: AsyncSession, user: User) -> int:
        """
        Увеличивает счётчик бесплатных сообщений.
        Возвращает новое значение счётчика.
        """
        today = date.today()
        
        # Reset counter if it's a new day
        if user.free_messages_reset_date is None or user.free_messages_reset_date.date() < today:
            user.free_messages_today = 0
            user.free_messages_reset_date = datetime.utcnow()
        
        user.free_messages_today += 1
        return user.free_messages_today
    
    @staticmethod
    async def get_free_messages_remaining(session: AsyncSession, user: User, daily_limit: int) -> int:
        """Возвращает количество оставшихся бесплатных сообщений на сегодня."""
        today = date.today()
        
        if user.free_messages_reset_date is None or user.free_messages_reset_date.date() < today:
            return daily_limit
        
        return max(0, daily_limit - user.free_messages_today)
