from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
import asyncio
import logging

import database as db
import keyboards as kb
from config import ADMIN_IDS, TARIFFS, TRIAL_DAYS, BANNER_MAIN, BANNER_CATEGORIES, WELCOME_TEXT
from payments.yookassa_service import create_payment
from render import send_screen, edit_screen

router = Router()


async def _is_admin(tg_id: int) -> bool:
    return tg_id in ADMIN_IDS


@router.message(CommandStart())
async def cmd_start(message: Message):
    is_admin = await _is_admin(message.from_user.id)
    is_new = await db.get_or_create_user(
        message.from_user.id, message.from_user.username or "", is_admin
    )
    text = WELCOME_TEXT


    if is_new:
        text += "Чтобы начать получать заявки, откройте раздел «Подписка» — там доступен бесплатный пробный период на 3 дня."
    else:
        has_access = await db.has_active_access(message.from_user.id)
        text += "✅ У вас активна подписка." if has_access else "⚠️ Подписка не активна. Оформите её в разделе «Подписка»."

    await send_screen(message, BANNER_MAIN, text, kb.main_menu_kb(is_admin))


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery):
    is_admin = await _is_admin(call.from_user.id)
    
    await edit_screen(call, BANNER_MAIN, WELCOME_TEXT, kb.main_menu_kb(is_admin))
    await call.answer()


# ---------- Категории пользователя ----------

@router.callback_query(F.data == "my_categories")
async def cb_my_categories(call: CallbackQuery):
    has_access = await db.has_active_access(call.from_user.id)
    if not has_access:
        await call.answer(
            "Чтобы выбрать категории, нужна активная подписка или пробный период.",
            show_alert=True,
        )
        return
    categories = await db.get_categories()
    if not categories:
        await call.answer("Категории пока не добавлены администратором.", show_alert=True)
        return
    user_cats = await db.get_user_categories(call.from_user.id)
    selected_ids = {c["id"] for c in user_cats}
    await edit_screen(
        call,
        BANNER_CATEGORIES,
        "Выберите категории заказов, которые вам интересны (можно несколько):",
        kb.categories_kb(categories, selected_ids),
    )
    await call.answer()


@router.callback_query(F.data.startswith("togglecat_"))
async def cb_toggle_category(call: CallbackQuery):
    category_id = int(call.data.split("_")[1])
    await db.toggle_user_category(call.from_user.id, category_id)
    categories = await db.get_categories()
    user_cats = await db.get_user_categories(call.from_user.id)
    selected_ids = {c["id"] for c in user_cats}
    # Баннер и подпись не меняются — обновляем только клавиатуру, это быстрее
    await call.message.edit_reply_markup(reply_markup=kb.categories_kb(categories, selected_ids))
    await call.answer("Обновлено")


# ---------- Подписка и оплата ----------

@router.callback_query(F.data == "subscription")
async def cb_subscription(call: CallbackQuery):
    user = await db.get_user(call.from_user.id)
    status = "нет активной подписки"
    if user and user["sub_until"]:
        has_access = await db.has_active_access(call.from_user.id)
        if has_access:
            status = f"активна до {user['sub_until'].strftime('%d.%m.%Y %H:%M')} (UTC)"
    trial_available = bool(user) and not user["trial_used"]
    await edit_screen(
        call,
        BANNER_MAIN,
        f"Ваша подписка: {status}\n\nВыберите тариф:",
        kb.tariffs_kb(trial_available),
    )
    await call.answer()


@router.callback_query(F.data == "start_trial")
async def cb_start_trial(call: CallbackQuery):
    user = await db.get_user(call.from_user.id)
    if not user or user["trial_used"]:
        await call.answer("Пробный период уже был использован ранее.", show_alert=True)
        return
    until = await db.activate_trial(call.from_user.id)
    await edit_screen(
        call,
        BANNER_MAIN,
        f"🎁 Пробный период на {TRIAL_DAYS} дня активирован (до {until.strftime('%d.%m.%Y')}).\n\n"
        f"Теперь откройте «📂 Мои категории» в главном меню и выберите нужные категории заказов.",
        kb.main_menu_kb(await _is_admin(call.from_user.id)),
    )
    await call.answer()


@router.callback_query(F.data.startswith("buy_"))
async def cb_buy(call: CallbackQuery, bot: Bot):
    tariff_key = call.data.split("_", 1)[1]
    tariff = TARIFFS.get(tariff_key)
    if not tariff:
        await call.answer("Неизвестный тариф", show_alert=True)
        return

    me = await bot.get_me()

    loop = asyncio.get_event_loop()
    try:
        payment_id, pay_url = await loop.run_in_executor(
            None,
            lambda: create_payment(
                amount=tariff["price"],
                description=f"Подписка «{tariff['title']}» для пользователя {call.from_user.id}",
                user_id=call.from_user.id,
                tariff=tariff_key,
                bot_username=me.username,
            ),
        )
    except Exception as e:
        logging.error(f"Ошибка создания платежа: {e}")
        await call.answer("Не удалось создать платёж, попробуйте позже.", show_alert=True)
        return

    await db.create_payment_record(call.from_user.id, payment_id, tariff["price"], tariff_key)

    await edit_screen(
        call,
        BANNER_MAIN,
        f"Тариф «{tariff['title']}» — {tariff['price']}₽.\n\n"
        f"1. Нажмите «Оплатить» и завершите оплату.\n"
        f"2. Вернитесь в бота и нажмите «Я оплатил» (или подождите — доступ включится автоматически).",
        kb.payment_kb(pay_url, payment_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("check_"))
async def cb_check_payment(call: CallbackQuery):
    payment_id = call.data.split("_", 1)[1]
    payment = await db.get_payment(payment_id)
    if not payment:
        await call.answer("Платёж не найден", show_alert=True)
        return
    if payment["status"] == "succeeded":
        await call.answer("Оплата подтверждена, подписка активна ✅", show_alert=True)
    else:
        await call.answer("Пока не видим оплату. Если вы уже оплатили — подождите немного, статус обновится автоматически.", show_alert=True)
