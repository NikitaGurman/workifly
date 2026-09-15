from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import TARIFFS


def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📂 Мои категории", callback_data="my_categories")
    b.button(text="💳 Подписка", callback_data="subscription")
    if is_admin:
        b.button(text="🛠 Админ-панель", callback_data="admin_panel")
    b.adjust(1)
    return b.as_markup()


def categories_kb(categories, selected_ids: set) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in categories:
        mark = "✅ " if c["id"] in selected_ids else "▫️ "
        b.button(text=f"{mark}{c['name']}", callback_data=f"togglecat_{c['id']}")
    b.button(text="⬅️ Назад", callback_data="main_menu")
    b.adjust(1)
    return b.as_markup()


def tariffs_kb(trial_available: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if trial_available:
        b.button(text="🎁 Пробный период 3 дня бесплатно", callback_data="start_trial")
    for key, t in TARIFFS.items():
        b.button(text=f"{t['title']} — {t['price']}₽", callback_data=f"buy_{key}")
    b.button(text="⬅️ Назад", callback_data="main_menu")
    b.adjust(1)
    return b.as_markup()


def payment_kb(pay_url: str, payment_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💳 Оплатить", url=pay_url)
    b.button(text="✅ Я оплатил / проверить", callback_data=f"check_{payment_id}")
    b.button(text="⬅️ Назад", callback_data="main_menu")
    b.adjust(1)
    return b.as_markup()


def admin_panel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить заявку", callback_data="admin_add_order")
    b.button(text="📁 Категории", callback_data="admin_categories")
    b.button(text="📊 Статистика", callback_data="admin_stats")
    b.button(text="⬅️ Назад", callback_data="main_menu")
    b.adjust(1)
    return b.as_markup()


def admin_categories_kb(categories) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in categories:
        b.button(text=f"❌ {c['name']}", callback_data=f"delcat_{c['id']}")
    b.button(text="➕ Новая категория", callback_data="admin_new_category")
    b.button(text="⬅️ Назад", callback_data="admin_panel")
    b.adjust(1)
    return b.as_markup()


def pick_category_for_order_kb(categories) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in categories:
        b.button(text=c["name"], callback_data=f"ordercat_{c['id']}")
    b.button(text="⬅️ Отмена", callback_data="admin_panel")
    b.adjust(1)
    return b.as_markup()


def confirm_order_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Отправить подписчикам", callback_data="order_send")
    b.button(text="✏️ Отменить", callback_data="admin_panel")
    b.adjust(1)
    return b.as_markup()
