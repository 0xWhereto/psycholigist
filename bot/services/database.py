"""
Database service - connection and session management.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from bot.models import Base

logger = logging.getLogger(__name__)


class DatabaseService:
    """Сервис для работы с базой данных."""
    
    def __init__(self, database_url: str):
        self.engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=10,
            max_overflow=20
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def init_db(self):
        """Создаёт все таблицы."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")
    
    async def close(self):
        """Закрывает соединение с БД."""
        await self.engine.dispose()
        logger.info("Database connection closed")
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Контекстный менеджер для сессии."""
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


# Global instance
db: DatabaseService | None = None


def get_db() -> DatabaseService:
    """Возвращает экземпляр DatabaseService."""
    if db is None:
        raise RuntimeError("Database not initialized")
    return db


def init_database(database_url: str) -> DatabaseService:
    """Инициализирует базу данных."""
    global db
    db = DatabaseService(database_url)
    return db
