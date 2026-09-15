import uuid
from yookassa import Configuration, Payment
from config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY

Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY


def create_payment(amount: float, description: str, user_id: int, tariff: str, bot_username: str):
    """Создаёт платёж в ЮKassa и возвращает (payment_id, ссылка на оплату)."""
    idempotence_key = str(uuid.uuid4())
    payment = Payment.create(
        {
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": f"https://t.me/{bot_username}",
            },
            "capture": True,
            "description": description,
            "metadata": {"user_id": str(user_id), "tariff": tariff},
        },
        idempotence_key,
    )
    return payment.id, payment.confirmation.confirmation_url


def get_payment_status(payment_id: str) -> str:
    """Возвращает статус: pending / waiting_for_capture / succeeded / canceled."""
    payment = Payment.find_one(payment_id)
    return payment.status
