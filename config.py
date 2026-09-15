import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# Данные магазина ЮKassa (из личного кабинета yookassa.ru -> Настройки -> API)
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")

# Строка подключения к PostgreSQL, напр.:
# postgresql://user:password@localhost:5432/freelance_bot
DATABASE_URL = os.getenv("DATABASE_URL")

# Пробный период для новых пользователей
TRIAL_DAYS = 3

# Тарифы подписки: ключ -> (название, дней, цена в рублях)
TARIFFS = {
    "week": {"title": "Неделя", "days": 7, "price": 549},
    "month": {"title": "Месяц", "days": 30, "price": 729},
    "3months": {"title": "3 месяца", "days": 90, "price": 1449},
}

# Баннеры (замените файлы в assets/ на свои — размер лучше сохранить одинаковым,
# например 1280x640, чтобы экраны не "прыгали" при переключении)
BANNER_MAIN = os.getenv("BANNER_MAIN", "assets/banner_main.png")
BANNER_CATEGORIES = os.getenv("BANNER_CATEGORIES", "assets/banner_categories.png")

# Как часто (в секундах) бот сам опрашивает ЮKassa о статусе неоплаченных счетов
PAYMENT_CHECK_INTERVAL = 15


WELCOME_TEXT = ( "👋 Привет! Это Workilfy, бот который помогает находить заказчиков и испольнителей на фрилансе.\n\n"
                    "Выберите нужные категории — и как только появится новая заявка, "
                    "она сразу придёт вам в бота.\n\n")