"""
Интеграция с Crypto Pay API (@CryptoBot).
Позволяет принимать оплату картой с автоматической конвертацией в крипту.
"""
import logging
import aiohttp
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

CRYPTO_PAY_API_URL = "https://pay.crypt.bot/api"


class CryptoPayClient:
    """Клиент для работы с Crypto Pay API."""
    
    def __init__(self, api_token: str):
        """
        Инициализация клиента.
        
        Args:
            api_token: Токен от @CryptoBot (получить через /pay -> Create App)
        """
        self.api_token = api_token
        self.headers = {
            "Crypto-Pay-API-Token": api_token
        }
    
    async def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Выполняет запрос к API."""
        url = f"{CRYPTO_PAY_API_URL}/{endpoint}"
        
        logger.info(f"Crypto Pay request: {method} {endpoint} data={data}")
        
        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url, headers=self.headers, params=data) as response:
                    result = await response.json()
                    logger.info(f"Crypto Pay response: {result}")
            else:
                async with session.post(url, headers=self.headers, json=data) as response:
                    result = await response.json()
                    logger.info(f"Crypto Pay response: {result}")
            
            if not result.get("ok"):
                error = result.get("error", {})
                error_msg = result.get("error", result)
                logger.error(f"Crypto Pay API error: {error_msg}")
                raise Exception(f"Crypto Pay API error: {error_msg}")
            
            return result.get("result")
    
    async def get_me(self) -> dict:
        """Получает информацию о приложении."""
        return await self._request("GET", "getMe")
    
    async def create_invoice(
        self,
        amount: float,
        currency: str = "USDT",
        description: str = "",
        payload: str = "",
        allow_comments: bool = False,
        allow_anonymous: bool = True,
        expires_in: int = 3600  # 1 час
    ) -> dict:
        """
        Создаёт инвойс для оплаты.
        
        Args:
            amount: Сумма в указанной валюте
            currency: Валюта (USDT, TON, BTC, ETH и др.)
            description: Описание платежа
            payload: Произвольные данные (вернутся в webhook)
            allow_comments: Разрешить комментарии
            allow_anonymous: Разрешить анонимную оплату
            expires_in: Время жизни инвойса в секундах
        
        Returns:
            Данные инвойса с pay_url
        """
        data = {
            "asset": currency,
            "amount": str(amount),
            "description": description,
            "payload": payload,
            "allow_comments": allow_comments,
            "allow_anonymous": allow_anonymous,
            "expires_in": expires_in
        }
        
        return await self._request("POST", "createInvoice", data)
    
    async def get_invoices(
        self,
        asset: str = None,
        invoice_ids: list = None,
        status: str = None,
        offset: int = 0,
        count: int = 100
    ) -> list:
        """Получает список инвойсов."""
        data = {
            "offset": offset,
            "count": count
        }
        if asset:
            data["asset"] = asset
        if invoice_ids:
            data["invoice_ids"] = ",".join(map(str, invoice_ids))
        if status:
            data["status"] = status
        
        result = await self._request("GET", "getInvoices", data)
        return result.get("items", [])
    
    async def get_invoice(self, invoice_id: int) -> Optional[dict]:
        """Получает конкретный инвойс."""
        invoices = await self.get_invoices(invoice_ids=[invoice_id])
        return invoices[0] if invoices else None
    
    async def check_invoice_paid(self, invoice_id: int) -> bool:
        """Проверяет, оплачен ли инвойс."""
        invoice = await self.get_invoice(invoice_id)
        if invoice:
            return invoice.get("status") == "paid"
        return False
    
    async def get_balance(self) -> list:
        """Получает баланс кошелька."""
        return await self._request("GET", "getBalance")


# Глобальный клиент
crypto_pay_client: Optional[CryptoPayClient] = None


def init_crypto_pay(api_token: str) -> CryptoPayClient:
    """Инициализирует клиент Crypto Pay."""
    global crypto_pay_client
    crypto_pay_client = CryptoPayClient(api_token)
    logger.info("Crypto Pay client initialized")
    return crypto_pay_client


def get_crypto_pay() -> Optional[CryptoPayClient]:
    """Возвращает клиент Crypto Pay."""
    return crypto_pay_client
