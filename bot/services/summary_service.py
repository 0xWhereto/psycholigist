"""
Summary service - long-term conversation memory.

Создаёт и обновляет саммари диалога, чтобы бот помнил
ключевые темы, проблемы и инсайты клиента между сессиями.
"""
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import ChatSummary, Message

logger = logging.getLogger(__name__)

# Промпт для создания саммари
SUMMARY_PROMPT = """Ты — помощник психоаналитика. Твоя задача — создать краткое резюме терапевтической сессии.

Сохрани ТОЛЬКО клинически важную информацию:
- Основные темы и проблемы клиента
- Ключевые эмоции и переживания
- Выявленные паттерны и защитные механизмы
- Важные факты из жизни (отношения, работа, семья, травмы)
- Инсайты и осознания клиента
- На каком этапе остановился диалог

НЕ включай:
- Приветствия и технические сообщения
- Дословные цитаты (только суть)
- Свои интерпретации — только факты из диалога

Формат: связный текст, 3-8 предложений. Пиши на языке клиента."""

MERGE_SUMMARY_PROMPT = """Ты — помощник психоаналитика. У тебя есть предыдущее резюме работы с клиентом и новая сессия.

Объедини предыдущее резюме с новой информацией в одно обновлённое резюме.

Правила:
- Сохрани все важные темы из предыдущего резюме
- Добавь новую информацию из последней сессии
- Отметь, если есть развитие ранее обсуждённых тем
- Убери устаревшую или неактуальную информацию
- Результат: связный текст, 5-15 предложений максимум

Предыдущее резюме:
{previous_summary}

Новая сессия (сообщения):
{new_messages}

Обновлённое резюме:"""


class SummaryService:
    """Сервис для управления долговременной памятью бота."""
    
    @staticmethod
    async def get_summary(session: AsyncSession, user_id: int) -> str | None:
        """Получает текущее саммари для пользователя."""
        result = await session.execute(
            select(ChatSummary)
            .where(ChatSummary.user_id == user_id)
            .order_by(ChatSummary.updated_at.desc())
            .limit(1)
        )
        summary = result.scalar_one_or_none()
        return summary.summary if summary else None
    
    @staticmethod
    async def save_summary(
        session: AsyncSession,
        user_id: int,
        summary_text: str,
        messages_count: int
    ) -> ChatSummary:
        """Сохраняет или обновляет саммари."""
        result = await session.execute(
            select(ChatSummary)
            .where(ChatSummary.user_id == user_id)
            .order_by(ChatSummary.updated_at.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.summary = summary_text
            existing.messages_summarized += messages_count
            existing.updated_at = datetime.utcnow()
            logger.info(f"Updated summary for user {user_id} (+{messages_count} msgs)")
            return existing
        else:
            new_summary = ChatSummary(
                user_id=user_id,
                summary=summary_text,
                messages_summarized=messages_count
            )
            session.add(new_summary)
            await session.flush()
            logger.info(f"Created new summary for user {user_id} ({messages_count} msgs)")
            return new_summary
    
    @staticmethod
    async def generate_summary(
        ai_service,
        messages: list[dict],
        previous_summary: str | None = None
    ) -> str:
        """Генерирует саммари через AI."""
        # Форматируем сообщения
        formatted = "\n".join(
            f"{'Клиент' if m['role'] == 'user' else 'Терапевт'}: {m['content']}"
            for m in messages
        )
        
        if previous_summary:
            prompt = MERGE_SUMMARY_PROMPT.format(
                previous_summary=previous_summary,
                new_messages=formatted
            )
        else:
            prompt = f"{SUMMARY_PROMPT}\n\nДиалог:\n{formatted}\n\nРезюме:"
        
        # Вызываем AI для суммаризации
        summary = await ai_service.generate_response([
            {"role": "user", "content": prompt}
        ])
        
        return summary.strip()
    
    @staticmethod
    async def summarize_and_clear(
        session: AsyncSession,
        ai_service,
        user_id: int,
        messages: list[dict]
    ) -> str | None:
        """
        Суммаризирует текущие сообщения, сохраняет саммари,
        и очищает историю. Возвращает текст саммари.
        """
        if not messages or len(messages) < 4:
            return None
        
        try:
            # Получаем предыдущее саммари
            previous = await SummaryService.get_summary(session, user_id)
            
            # Генерируем новое
            summary_text = await SummaryService.generate_summary(
                ai_service, messages, previous
            )
            
            # Сохраняем
            await SummaryService.save_summary(
                session, user_id, summary_text, len(messages)
            )
            
            logger.info(f"Summarized {len(messages)} messages for user {user_id}")
            return summary_text
            
        except Exception as e:
            logger.error(f"Failed to summarize for user {user_id}: {e}")
            return None
