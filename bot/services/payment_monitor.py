"""
Automatic payment monitoring via TON blockchain.
Periodically checks for incoming transactions and activates subscriptions.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal

import aiohttp
from sqlalchemy import select, and_

from bot.models import Payment, User
from bot.services.database import get_db
from bot.services.subscription_service import SubscriptionService, PaymentService, SUBSCRIPTION_PLANS

logger = logging.getLogger(__name__)

# TON API endpoints
TONCENTER_API = "https://toncenter.com/api/v2"
TONAPI_ENDPOINT = "https://tonapi.io/v2"


class PaymentMonitor:
    """
    Мониторинг платежей через блокчейн TON.
    Автоматически проверяет транзакции и активирует подписки.
    """
    
    def __init__(self, wallet_address: str, bot=None):
        self.wallet_address = wallet_address
        self.bot = bot  # Telegram bot instance for notifications
        self.last_check_time = datetime.utcnow() - timedelta(hours=1)
        self.processed_transactions = set()  # Кэш обработанных транзакций
        self._running = False
    
    async def start(self):
        """Запускает мониторинг в фоновом режиме."""
        self._running = True
        logger.info(f"Payment monitor started for wallet: {self.wallet_address}")
        
        while self._running:
            try:
                await self.check_transactions()
            except Exception as e:
                logger.error(f"Payment monitor error: {e}")
            
            # Проверяем каждые 30 секунд
            await asyncio.sleep(30)
    
    async def stop(self):
        """Останавливает мониторинг."""
        self._running = False
        logger.info("Payment monitor stopped")
    
    async def check_transactions(self):
        """Проверяет новые транзакции на кошелёк."""
        try:
            transactions = await self._fetch_transactions()
            
            if not transactions:
                return
            
            db = get_db()
            
            async with db.session() as session:
                # Получаем все ожидающие платежи
                pending_payments = await PaymentService.get_pending_payments(session)
                
                if not pending_payments:
                    return
                
                for tx in transactions:
                    tx_hash = tx.get("hash") or tx.get("transaction_id", {}).get("hash", "")
                    
                    # Пропускаем уже обработанные
                    if tx_hash in self.processed_transactions:
                        continue
                    
                    # Получаем сумму транзакции
                    amount_nano = self._extract_amount(tx)
                    if amount_nano <= 0:
                        continue
                    
                    # Конвертируем в USD (приблизительно, для USDT на TON = 1:1)
                    amount_usd = self._nano_to_usd(amount_nano, tx)
                    
                    # Ищем соответствующий платёж
                    matched_payment = self._match_payment(pending_payments, amount_usd)
                    
                    if matched_payment:
                        await self._process_payment(session, matched_payment, tx_hash)
                        self.processed_transactions.add(tx_hash)
            
        except Exception as e:
            logger.error(f"Error checking transactions: {e}")
    
    async def _fetch_transactions(self) -> list:
        """Получает последние транзакции с кошелька."""
        try:
            async with aiohttp.ClientSession() as session:
                # Используем TonCenter API
                url = f"{TONCENTER_API}/getTransactions"
                params = {
                    "address": self.wallet_address,
                    "limit": 20
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("ok"):
                            return data.get("result", [])
                    
                    logger.warning(f"TonCenter API returned status {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Failed to fetch transactions: {e}")
            return []
    
    def _extract_amount(self, tx: dict) -> int:
        """Извлекает сумму из транзакции в наноединицах."""
        try:
            # Структура TonCenter API
            in_msg = tx.get("in_msg", {})
            value = in_msg.get("value", 0)
            return int(value)
        except (KeyError, TypeError, ValueError):
            return 0
    
    def _nano_to_usd(self, nano_amount: int, tx: dict) -> Decimal:
        """
        Конвертирует наноединицы в USD.
        Для USDT на TON: 1 USDT = 1,000,000 наноединиц (6 decimals)
        Для TON: нужен курс обмена
        """
        # Проверяем, это USDT или TON
        in_msg = tx.get("in_msg", {})
        
        # Для Jetton (USDT) транзакций структура другая
        # Упрощённо считаем как USDT с 6 decimals
        # В реальности нужно проверять тип токена
        
        # USDT имеет 6 decimals
        amount = Decimal(nano_amount) / Decimal(1_000_000)
        return amount
    
    def _match_payment(self, pending_payments: list, amount_usd: Decimal) -> Payment | None:
        """
        Сопоставляет сумму транзакции с ожидающим платежом.
        Допускает погрешность 1% для учёта комиссий.
        """
        tolerance = Decimal("0.01")  # 1% погрешность
        
        for payment in pending_payments:
            expected = Decimal(str(payment.amount_usd))
            min_amount = expected * (1 - tolerance)
            max_amount = expected * (1 + tolerance)
            
            if min_amount <= amount_usd <= max_amount:
                return payment
        
        return None
    
    async def _process_payment(self, session, payment: Payment, tx_hash: str):
        """Обрабатывает подтверждённый платёж."""
        logger.info(f"Auto-confirming payment {payment.id} with tx {tx_hash}")
        
        try:
            # Обновляем платёж
            payment.status = "completed"
            payment.tx_hash = tx_hash
            payment.confirmed_at = datetime.utcnow()
            payment.note = "Auto-confirmed via blockchain"
            
            # Создаём подписку
            subscription = await SubscriptionService.create_subscription(
                session,
                user_id=payment.user_id,
                plan_type=payment.plan_type,
                payment_id=str(payment.id)
            )
            
            # Отправляем уведомление пользователю
            if self.bot:
                plan = SUBSCRIPTION_PLANS[payment.plan_type]
                
                # Получаем язык пользователя
                from bot.services.user_service import UserService
                user = await UserService.get_user(session, payment.user_id)
                lang = user.language_code if user else "ru"
                
                messages = {
                    "ru": f"""
✅ **Подписка активирована!**

**План:** {plan['name_ru']}
**Действует до:** {subscription.expires_at.strftime('%d.%m.%Y')}

Платёж подтверждён автоматически. 
Приятного использования! 💙
""",
                    "en": f"""
✅ **Subscription activated!**

**Plan:** {plan['name_en']}
**Valid until:** {subscription.expires_at.strftime('%d.%m.%Y')}

Payment confirmed automatically.
Enjoy! 💙
""",
                    "fr": f"""
✅ **Abonnement activé!**

**Formule:** {plan['name_fr']}
**Valable jusqu'au:** {subscription.expires_at.strftime('%d.%m.%Y')}

Paiement confirmé automatiquement.
Bonne utilisation! 💙
"""
                }
                
                try:
                    await self.bot.send_message(
                        chat_id=payment.user_id,
                        text=messages.get(lang, messages["ru"]),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {payment.user_id}: {e}")
            
            logger.info(f"Payment {payment.id} auto-confirmed, subscription created until {subscription.expires_at}")
            
        except Exception as e:
            logger.error(f"Failed to process payment {payment.id}: {e}")
            raise


# Global instance
payment_monitor: PaymentMonitor | None = None


def get_payment_monitor() -> PaymentMonitor | None:
    """Возвращает экземпляр PaymentMonitor."""
    return payment_monitor


def init_payment_monitor(wallet_address: str, bot=None) -> PaymentMonitor:
    """Инициализирует мониторинг платежей."""
    global payment_monitor
    payment_monitor = PaymentMonitor(wallet_address, bot)
    return payment_monitor
