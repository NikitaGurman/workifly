import asyncio
import logging
from aiogram import Bot

import database as db
from config import TARIFFS, PAYMENT_CHECK_INTERVAL
from payments.yookassa_service import get_payment_status

logger = logging.getLogger(__name__)


async def payment_polling_loop(bot: Bot):
    """Каждые N секунд проверяет незавершённые платежи и активирует подписку при успехе."""
    while True:
        try:
            pending = await db.get_pending_payments()
            for payment in pending:
                status = get_payment_status(payment["yk_payment_id"])
                if status == "succeeded":
                    tariff = TARIFFS.get(payment["tariff"])
                    if tariff:
                        new_until = await db.extend_subscription(payment["user_id"], tariff["days"])
                        await db.update_payment_status(payment["yk_payment_id"], "succeeded")
                        try:
                            await bot.send_message(
                                payment["user_id"],
                                f"✅ Оплата получена! Подписка «{tariff['title']}» активна до "
                                f"{new_until.strftime('%d.%m.%Y %H:%M')} (UTC).",
                            )
                        except Exception:
                            pass
                elif status == "canceled":
                    await db.update_payment_status(payment["yk_payment_id"], "canceled")
        except Exception as e:
            logger.exception("Ошибка при проверке платежей: %s", e)

        await asyncio.sleep(PAYMENT_CHECK_INTERVAL)
