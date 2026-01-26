"""
QR code generator for crypto payments.
"""
import io
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer


def generate_payment_qr(wallet_address: str, amount: float = None, currency: str = "USDT") -> io.BytesIO:
    """
    Генерирует QR-код для оплаты.
    
    Args:
        wallet_address: Адрес кошелька TON
        amount: Сумма платежа (опционально)
        currency: Валюта (USDT, TON)
    
    Returns:
        BytesIO объект с PNG изображением QR-кода
    """
    # Формируем URI для TON
    # Формат: ton://transfer/<address>?amount=<nanotons>&text=<comment>
    if currency == "TON" and amount:
        # TON использует наноединицы (1 TON = 10^9 nanotons)
        nano_amount = int(amount * 1_000_000_000)
        data = f"ton://transfer/{wallet_address}?amount={nano_amount}"
    else:
        # Для USDT просто адрес (сумму нельзя указать в URI)
        data = wallet_address
    
    # Создаём QR-код
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    # Создаём изображение с закруглёнными модулями
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer()
    )
    
    # Сохраняем в BytesIO
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return buffer


def generate_simple_qr(data: str) -> io.BytesIO:
    """Генерирует простой QR-код."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return buffer
