"""
MixPay payment gateway integration.

Клиент платит картой → мерчант получает USDT.
Документация: https://mixpay.me/developers
"""
import logging
import uuid
from datetime import datetime, timedelta

import aiohttp

logger = logging.getLogger(__name__)

MIXPAY_API = "https://api.mixpay.me/v1"

# USDT asset ID в MixPay (Mixin network)
USDT_ASSET_ID = "4d8c508b-91c5-375b-92b0-ee702ed2dac5"


class MixPayService:
    """Сервис для работы с MixPay API."""
    
    def __init__(self, payee_id: str):
        self.payee_id = payee_id
    
    async def create_payment(
        self,
        amount_usd: float,
        order_id: str,
        description: str = "Subscription"
    ) -> dict | None:
        """
        Создаёт one-time payment через MixPay.
        
        Возвращает dict с code и payment_url, или None при ошибке.
        """
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "payeeId": self.payee_id,
                    "quoteAssetId": "usd",
                    "quoteAmount": str(amount_usd),
                    "settlementAssetId": USDT_ASSET_ID,
                    "strictMode": True,  # строго USDT
                    "orderId": order_id,
                    "expiredTimestamp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
                }
                
                async with session.post(
                    f"{MIXPAY_API}/one_time_payment",
                    json=payload
                ) as response:
                    data = await response.json()
                    
                    if data.get("success") and data.get("data", {}).get("code"):
                        code = data["data"]["code"]
                        payment_url = f"https://mixpay.me/code/{code}"
                        
                        logger.info(f"MixPay payment created: order={order_id}, url={payment_url}")
                        
                        return {
                            "code": code,
                            "payment_url": payment_url,
                            "order_id": order_id,
                        }
                    else:
                        logger.error(f"MixPay create payment failed: {data}")
                        return None
                        
        except Exception as e:
            logger.error(f"MixPay API error: {e}")
            return None
    
    async def check_payment_status(self, order_id: str) -> dict | None:
        """
        Проверяет статус платежа по orderId.
        
        Возвращает dict со статусом или None при ошибке.
        Статусы: unpaid, pending, success, failed
        """
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "orderId": order_id,
                    "payeeId": self.payee_id,
                }
                
                async with session.get(
                    f"{MIXPAY_API}/payments_result",
                    params=params
                ) as response:
                    data = await response.json()
                    
                    if data.get("success"):
                        result = data.get("data", {})
                        status = result.get("status", "unknown")
                        
                        return {
                            "status": status,  # unpaid, pending, success, failed
                            "order_id": order_id,
                            "quote_amount": result.get("quoteAmount"),
                            "payment_amount": result.get("paymentAmount"),
                            "settlement_amount": result.get("settlementAmount"),
                            "failure_reason": result.get("failureReason"),
                        }
                    else:
                        return {"status": "unpaid", "order_id": order_id}
                        
        except Exception as e:
            logger.error(f"MixPay check status error: {e}")
            return None
    
    @staticmethod
    def generate_order_id(user_id: int, plan_type: str) -> str:
        """Генерирует уникальный orderId для MixPay."""
        short_uuid = uuid.uuid4().hex[:8]
        return f"psy-{user_id}-{plan_type}-{short_uuid}"


# Global instance
mixpay_service: MixPayService | None = None


def get_mixpay() -> MixPayService | None:
    """Возвращает экземпляр MixPayService."""
    return mixpay_service


def init_mixpay(payee_id: str) -> MixPayService:
    """Инициализирует MixPay сервис."""
    global mixpay_service
    mixpay_service = MixPayService(payee_id)
    logger.info(f"MixPay initialized with payeeId: {payee_id[:8]}...")
    return mixpay_service
