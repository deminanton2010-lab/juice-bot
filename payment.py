from abc import ABC, abstractmethod
from typing import Optional
import qrcode
from io import BytesIO

class PaymentResult:
    def __init__(self, ok: bool, qr_png: Optional[bytes] = None, link: Optional[str] = None, description: str = ""):
        self.ok = ok
        self.qr_png = qr_png
        self.link = link
        self.description = description

class PaymentProvider(ABC):
    @abstractmethod
    async def create_invoice(self, order_id: str, amount: float, description: str = "") -> PaymentResult:
        ...

class CashPayment(PaymentProvider):
    async def create_invoice(self, order_id: str, amount: float, description: str = "") -> PaymentResult:
        return PaymentResult(ok=True, link=None, description=f"Оплата наличными при получении. Сумма: {amount:.2f}")

class QRStaticPayment(PaymentProvider):
    def __init__(self, payload_prefix: str = "PAY"):
        self.payload_prefix = payload_prefix

    async def create_invoice(self, order_id: str, amount: float, description: str = "") -> PaymentResult:
        payload = f"{self.payload_prefix}|ORDER={order_id}|AMOUNT={amount:.2f}"
        img = qrcode.make(payload)
        buf = BytesIO(); img.save(buf, format="PNG")
        return PaymentResult(ok=True, qr_png=buf.getvalue(), description="Отсканируйте QR для оплаты")
