import functools

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import database as db
import keyboards as kb
from config import ADMIN_IDS, BANNER_MAIN
from states import AddOrder, NewCategory
from render import send_screen, edit_screen

router = Router()


def admin_only(handler):
    @functools.wraps(handler)
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id
        if user_id not in ADMIN_IDS:
            if isinstance(event, CallbackQuery):
                await event.answer("Недостаточно прав", show_alert=True)
            else:
                await event.answer("Недостаточно прав.")
            return
        return await handler(event, *args, **kwargs)
    return wrapper


@router.message(Command("admin"))
@admin_only
async def cmd_admin(message: Message):
    await send_screen(message, BANNER_MAIN, "🛠 Админ-панель:", kb.admin_panel_kb())


@router.callback_query(F.data == "admin_panel")
@admin_only
async def cb_admin_panel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await edit_screen(call, BANNER_MAIN, "🛠 Админ-панель:", kb.admin_panel_kb())
    await call.answer()


# ---------- Статистика ----------

@router.callback_query(F.data == "admin_stats")
@admin_only
async def cb_admin_stats(call: CallbackQuery):
    stats = await db.get_stats()
    text = (
        "📊 Статистика\n\n"
        f"Всего пользователей: {stats['total_users']}\n"
        f"С активной подпиской/пробным периодом: {stats['active_subs']}\n"
        f"Заявок отправлено: {stats['total_orders']}\n"
        f"Успешных оплат: {stats['paid_count']} на сумму {stats['paid_sum']:.0f}₽"
    )
    await edit_screen(call, BANNER_MAIN, text, kb.admin_panel_kb())
    await call.answer()


# ---------- Категории ----------

@router.callback_query(F.data == "admin_categories")
@admin_only
async def cb_admin_categories(call: CallbackQuery):
    categories = await db.get_categories()
    await edit_screen(
        call,
        BANNER_MAIN,
        "📁 Категории заказов (нажмите, чтобы удалить):",
        kb.admin_categories_kb(categories),
    )
    await call.answer()


@router.callback_query(F.data == "admin_new_category")
@admin_only
async def cb_new_category(call: CallbackQuery, state: FSMContext):
    await state.set_state(NewCategory.entering_name)
    await edit_screen(call, BANNER_MAIN, "Введите название новой категории сообщением:")
    await call.answer()


@router.message(NewCategory.entering_name)
@admin_only
async def process_new_category(message: Message, state: FSMContext):
    await db.add_category(message.text.strip())
    await state.clear()
    categories = await db.get_categories()
    await send_screen(
        message,
        BANNER_MAIN,
        f"Категория «{message.text.strip()}» добавлена.",
        kb.admin_categories_kb(categories),
    )


@router.callback_query(F.data.startswith("delcat_"))
@admin_only
async def cb_delete_category(call: CallbackQuery):
    category_id = int(call.data.split("_")[1])
    await db.delete_category(category_id)
    categories = await db.get_categories()
    await edit_screen(call, BANNER_MAIN, "📁 Категории заказов:", kb.admin_categories_kb(categories))
    await call.answer("Удалено")


# ---------- Добавление и рассылка заявки ----------

@router.callback_query(F.data == "admin_add_order")
@admin_only
async def cb_add_order(call: CallbackQuery, state: FSMContext):
    categories = await db.get_categories()
    if not categories:
        await call.answer("Сначала добавьте хотя бы одну категорию.", show_alert=True)
        return
    await state.set_state(AddOrder.choosing_category)
    await edit_screen(
        call,
        BANNER_MAIN,
        "Выберите категорию для новой заявки:",
        kb.pick_category_for_order_kb(categories),
    )
    await call.answer()


@router.callback_query(AddOrder.choosing_category, F.data.startswith("ordercat_"))
@admin_only
async def cb_order_category_chosen(call: CallbackQuery, state: FSMContext):
    category_id = int(call.data.split("_")[1])
    await state.update_data(category_id=category_id)
    await state.set_state(AddOrder.entering_text)
    await edit_screen(
        call,
        BANNER_MAIN,
        "Отправьте текст заявки одним сообщением (описание заказа, бюджет, контакты и т.д.):",
    )
    await call.answer()


@router.message(AddOrder.entering_text)
@admin_only
async def process_order_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(AddOrder.confirming)
    data = await state.get_data()
    categories = await db.get_categories()
    cat_name = next((c["name"] for c in categories if c["id"] == data["category_id"]), "—")
    # Текст заявки может быть длинным и не влезть в подпись к фото (лимит 1024 символа),
    # поэтому этот экран — обычное текстовое сообщение без баннера.
    await message.answer(
        f"Проверьте заявку перед отправкой:\n\n"
        f"Категория: {cat_name}\n"
        f"Текст:\n{message.text}",
        reply_markup=kb.confirm_order_kb(),
    )


@router.callback_query(AddOrder.confirming, F.data == "order_send")
@admin_only
async def cb_order_send(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    category_id = data["category_id"]
    text = data["text"]

    order_id = await db.add_order(category_id, text)
    subscribers = await db.get_subscribers_for_category(category_id)

    sent = 0
    for tg_id in subscribers:
        try:
            await bot.send_message(
                tg_id,
                text,
            )
            sent += 1
        except Exception:
            pass  # пользователь мог заблокировать бота

    await state.clear()
    await edit_screen(
        call,
        BANNER_MAIN,
        f"✅ Заявка #{order_id} отправлена {sent} из {len(subscribers)} подписчиков категории.",
        kb.admin_panel_kb(),
    )
    await call.answer()
