import asyncpg
from datetime import datetime, timedelta
from typing import Optional

from config import DATABASE_URL, TRIAL_DAYS

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    tg_id BIGINT PRIMARY KEY,
    username TEXT,
    is_admin BOOLEAN DEFAULT FALSE,
    trial_used BOOLEAN DEFAULT FALSE,
    sub_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS user_categories (
    user_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, category_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    category_id INTEGER,
    text TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    yk_payment_id TEXT,
    amount NUMERIC(10, 2),
    tariff TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT now()
);
"""

_pool: Optional[asyncpg.Pool] = None


async def init_db():
    global _pool
    if not DATABASE_URL:
        raise RuntimeError("Не задан DATABASE_URL в .env")
    _pool = await asyncpg.create_pool(dsn=DATABASE_URL, min_size=1, max_size=10)
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA)


def _get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("База данных не инициализирована. Вызовите init_db() при старте приложения.")
    return _pool


# ---------- Пользователи ----------

async def get_or_create_user(tg_id: int, username: str, is_admin: bool = False) -> bool:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT tg_id FROM users WHERE tg_id=$1", tg_id)
        if row is None:
            await conn.execute(
                "INSERT INTO users (tg_id, username, is_admin) VALUES ($1, $2, $3)",
                tg_id, username, is_admin,
            )
            return True  # новый пользователь
        return False


async def get_user(tg_id: int):
    pool = _get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE tg_id=$1", tg_id)


async def activate_trial(tg_id: int) -> datetime:
    until = datetime.utcnow() + timedelta(days=TRIAL_DAYS)
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET trial_used=TRUE, sub_until=$1 WHERE tg_id=$2",
            until, tg_id,
        )
    return until


async def extend_subscription(tg_id: int, days: int) -> datetime:
    user = await get_user(tg_id)
    base = datetime.utcnow()
    if user and user["sub_until"] and user["sub_until"] > base:
        base = user["sub_until"]
    new_until = base + timedelta(days=days)
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET sub_until=$1 WHERE tg_id=$2", new_until, tg_id)
    return new_until


async def has_active_access(tg_id: int) -> bool:
    user = await get_user(tg_id)
    if not user or not user["sub_until"]:
        return False
    return user["sub_until"] > datetime.utcnow()


# ---------- Категории ----------

async def add_category(name: str):
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO categories (name) VALUES ($1) ON CONFLICT (name) DO NOTHING", name
        )


async def get_categories():
    pool = _get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM categories ORDER BY name")


async def delete_category(category_id: int):
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM categories WHERE id=$1", category_id)


async def get_user_categories(tg_id: int):
    pool = _get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT c.* FROM categories c
               JOIN user_categories uc ON uc.category_id = c.id
               WHERE uc.user_id=$1""",
            tg_id,
        )


async def toggle_user_category(tg_id: int, category_id: int) -> bool:
    """Возвращает True если категория была добавлена, False если удалена."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchrow(
            "SELECT 1 FROM user_categories WHERE user_id=$1 AND category_id=$2",
            tg_id, category_id,
        )
        if exists:
            await conn.execute(
                "DELETE FROM user_categories WHERE user_id=$1 AND category_id=$2",
                tg_id, category_id,
            )
            return False
        else:
            await conn.execute(
                "INSERT INTO user_categories (user_id, category_id) VALUES ($1, $2)",
                tg_id, category_id,
            )
            return True


# ---------- Заявки ----------

async def add_order(category_id: int, text: str) -> int:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO orders (category_id, text) VALUES ($1, $2) RETURNING id",
            category_id, text,
        )
        return row["id"]


async def get_subscribers_for_category(category_id: int):
    """Пользователи с активной подпиской/пробным периодом, выбравшие эту категорию."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT u.tg_id FROM users u
               JOIN user_categories uc ON uc.user_id = u.tg_id
               WHERE uc.category_id=$1 AND u.sub_until IS NOT NULL AND u.sub_until > now()""",
            category_id,
        )
        return [r["tg_id"] for r in rows]


# ---------- Платежи ----------

async def create_payment_record(user_id: int, yk_payment_id: str, amount: float, tariff: str):
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO payments (user_id, yk_payment_id, amount, tariff, status)
               VALUES ($1, $2, $3, $4, 'pending')""",
            user_id, yk_payment_id, amount, tariff,
        )


async def update_payment_status(yk_payment_id: str, status: str):
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE payments SET status=$1 WHERE yk_payment_id=$2", status, yk_payment_id
        )


async def get_pending_payments():
    pool = _get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM payments WHERE status='pending'")


async def get_payment(yk_payment_id: str):
    pool = _get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM payments WHERE yk_payment_id=$1", yk_payment_id)


# ---------- Статистика для админа ----------

async def get_stats():
    pool = _get_pool()
    async with pool.acquire() as conn:
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
        active_subs = await conn.fetchval("SELECT COUNT(*) FROM users WHERE sub_until > now()")
        total_orders = await conn.fetchval("SELECT COUNT(*) FROM orders")
        paid_row = await conn.fetchrow(
            "SELECT COUNT(*) AS c, COALESCE(SUM(amount), 0) AS s FROM payments WHERE status='succeeded'"
        )
        return {
            "total_users": total_users,
            "active_subs": active_subs,
            "total_orders": total_orders,
            "paid_count": paid_row["c"],
            "paid_sum": float(paid_row["s"]),
        }
