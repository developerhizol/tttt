import aiosqlite
from config import DB_PATH
from datetime import datetime

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, avatar_url TEXT, created_at TEXT
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, recipient TEXT, product_type TEXT,
            stars_count INTEGER, months INTEGER,
            price_rub REAL, status TEXT, payment_link TEXT, tx_hash TEXT, created_at TEXT
        )''')
        await db.commit()

async def add_user(user_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?)", (user_id, username, None, datetime.now().isoformat()))
        await db.commit()

async def create_order(user_id: int, recipient: str, product_type: str, stars: int, months: int, price_rub: float, payment_link: str = "") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO orders (user_id, recipient, product_type, stars_count, months, price_rub, status, payment_link, created_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
            (user_id, recipient, product_type, stars, months, price_rub, payment_link, datetime.now().isoformat())
        )
        await db.commit()
        return cursor.lastrowid

async def get_order(order_id: int, user_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        q = "SELECT * FROM orders WHERE id = ?" + (" AND user_id = ?" if user_id else "")
        params = (order_id, user_id) if user_id else (order_id,)
        cursor = await db.execute(q, params)
        return await cursor.fetchone()

async def get_orders(user_id: int, limit: int = 5, offset: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?", (user_id, limit, offset))
        return await cursor.fetchall()

async def count_orders(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,))
        return (await cursor.fetchone())[0]

async def update_order_status(order_id: int, status: str, tx_hash: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if tx_hash:
            await db.execute("UPDATE orders SET status = ?, tx_hash = ? WHERE id = ?", (status, tx_hash, order_id))
        else:
            await db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        await db.commit()

async def get_user_stats(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*), COALESCE(SUM(stars_count), 0) FROM orders WHERE user_id = ? AND status = 'completed'", (user_id,))
        return await cursor.fetchone()
