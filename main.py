from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import aiosqlite
import asyncio
from datetime import datetime, timedelta
from aiocryptopay import AioCryptoPay, Networks
import jwt
from config import CRYPTO_PAY_TOKEN, JWT_SECRET, DB_PATH, SEED
from api import check_recipient, buy_stars_logic, buy_premium_logic

app = FastAPI()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

crypto = AioCryptoPay(token=CRYPTO_PAY_TOKEN, network=Networks.MAIN_NET)
security = HTTPBearer()

def create_jwt_token(user_id: int):
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def start_bot():
    from aiogram import Bot, Dispatcher
    from config import BOT_TOKEN
    from currency import rate_updater
    from webhook import create_app, set_bot
    from aiohttp import web
    
    bot = Bot(token=BOT_TOKEN)
    set_bot(bot)
    
    dp = Dispatcher()
    from bot import router
    dp.include_router(router)
    
    asyncio.create_task(rate_updater())
    
    webhook_app = create_app()
    runner = web.AppRunner(webhook_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8001)
    await site.start()
    
    await dp.start_polling(bot, handle_signals=False)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                avatar_url TEXT,
                created_at TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                recipient TEXT,
                product_type TEXT,
                stars_count INTEGER,
                months INTEGER,
                price REAL,
                status TEXT,
                payment_link TEXT,
                tx_hash TEXT,
                created_at TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                discount INTEGER,
                uses INTEGER DEFAULT 0
            )
        """)
        await db.execute("INSERT OR IGNORE INTO promo_codes (code, discount) VALUES ('STARS100', 100)")
        await db.commit()

@app.on_event("startup")
async def startup():
    await init_db()
    asyncio.create_task(start_bot())

@app.post("/auth")
async def authenticate(data: dict):
    user_id = data.get('user_id')
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID required")
    
    token = create_jwt_token(user_id)
    return {"token": token}

@app.get("/check-recipient")
async def check_recipient_endpoint(username: str, product_type: str = "stars", token: dict = Depends(verify_jwt_token)):
    result = await check_recipient(username, product_type, SEED)
    
    if result.get('found'):
        user_info = result['found']
        return {
            "valid": True,
            "username": username,
            "name": user_info.get('name', ''),
            "photo": user_info.get('photo', ''),
            "recipient": username
        }
    return {"valid": False}

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/payment/{order_hash}", response_class=HTMLResponse)
async def get_payment_page(request: Request, order_hash: str):
    return templates.TemplateResponse("payment.html", {"request": request, "order_hash": order_hash})

@app.get("/api/order-status/{order_hash}")
async def get_order_status(order_hash: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT id, product_type, stars_count, months, price, status, created_at, recipient
            FROM orders 
            WHERE id = ?
        """, (order_hash,))
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Order not found")
        
        return {
            "order_id": row[0],
            "product_type": row[1],
            "stars": row[2],
            "months": row[3],
            "total": row[4],
            "status": row[5],
            "created_at": row[6],
            "recipient": row[7]
        }

@app.get("/check-promo")
async def check_promo(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT discount FROM promo_codes WHERE code = ?", (code,))
        row = await cursor.fetchone()
        if row:
            return {"valid": True, "discount": row[0]}
        return {"valid": False}

@app.get("/get-price")
async def get_price(stars: int = None, months: int = None, product_type: str = "stars"):
    if product_type == "stars":
        if not stars or stars < 50:
            raise HTTPException(status_code=400, detail="Invalid stars amount")
        price_rub = round(stars * 1.5, 2)
        return {"price_rub": price_rub, "product_type": "stars", "stars": stars}
    else:
        if not months or months not in [3, 6, 12]:
            raise HTTPException(status_code=400, detail="Invalid months")
        prices = {3: 250, 6: 450, 12: 800}
        price_rub = prices.get(months, 0)
        return {"price_rub": price_rub, "product_type": "premium", "months": months}

@app.get("/transactions")
async def get_transactions(token: dict = Depends(verify_jwt_token)):
    user_id = token['user_id']
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT id, product_type, stars_count, months, price, status, created_at, recipient
            FROM orders 
            WHERE user_id = ? 
            ORDER BY id DESC 
            LIMIT 50
        """, (user_id,))
        rows = await cursor.fetchall()
        
        transactions = []
        for row in rows:
            transactions.append({
                "order_id": row[0],
                "product_type": row[1],
                "stars": row[2],
                "months": row[3],
                "total": row[4],
                "status": row[5],
                "created_at": row[6],
                "recipient": row[7]
            })
        
        return {"transactions": transactions}

@app.get("/order/{order_id}")
async def get_order_detail(order_id: int, token: dict = Depends(verify_jwt_token)):
    user_id = token['user_id']
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT id, product_type, stars_count, months, price, status, created_at, recipient
            FROM orders 
            WHERE id = ? AND user_id = ?
        """, (order_id, user_id))
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Order not found")
        
        return {
            "order_id": row[0],
            "product_type": row[1],
            "stars": row[2],
            "months": row[3],
            "total": row[4],
            "status": row[5],
            "created_at": row[6],
            "recipient": row[7]
        }

@app.post("/create-order")
@limiter.limit("5/minute")
async def create_order(request: Request, data: dict, token: dict = Depends(verify_jwt_token)):
    if data.get('user_id') != token['user_id']:
        raise HTTPException(status_code=403, detail="User ID mismatch")
    
    product_type = data.get('product_type', 'stars')
    stars = data.get('stars', 0)
    months = data.get('months', 0)
    payment_method = data.get('payment_method', 'crypto')
    recipient = data.get('recipient')
    
    if not recipient:
        raise HTTPException(status_code=400, detail="Recipient required")
    
    if product_type == "stars":
        if not isinstance(stars, int) or stars < 50 or stars > 4999:
            raise HTTPException(status_code=400, detail="Invalid stars amount")
        price = round(stars * 1.5, 2)
    else:
        if months not in [3, 6, 12]:
            raise HTTPException(status_code=400, detail="Invalid months")
        prices = {3: 250, 6: 450, 12: 800}
        price = prices.get(months, 0)
    
    if payment_method not in ['crypto']:
        raise HTTPException(status_code=400, detail="Invalid payment method")
    
    discount = 0
    if data.get('promo_code'):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT discount FROM promo_codes WHERE code = ?", (data['promo_code'],))
            row = await cursor.fetchone()
            if row:
                discount = row[0]
    
    total = price - discount
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO orders (user_id, recipient, product_type, stars_count, months, price, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (data['user_id'], recipient, product_type, stars, months, total, datetime.now()))
        await db.commit()
        order_id = cursor.lastrowid
    
    invoice = await crypto.create_invoice(
        asset='RUB',
        fiat='RUB',
        currency_type='fiat',
        amount=total,
        description=f"Покупка {stars if product_type == 'stars' else 'Premium'}",
        payload=str(order_id)
    )
    payment_url = invoice.bot_invoice_url
    
    await db.execute(
        "UPDATE orders SET payment_link = ? WHERE id = ?",
        (payment_url, order_id)
    )
    await db.commit()
    
    return {
        "order_id": order_id,
        "payment_url": payment_url,
        "total": total
    }

@app.post("/webhooks/cryptobot")
async def cryptobot_webhook(request: Request):
    body = await request.json()
    
    if body.get('update_type') == 'invoice_paid':
        payload = body.get('payload', {})
        order_id = payload.get('payload')
        
        if not order_id:
            return {"ok": False}
        
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT status, user_id, product_type, stars_count, months, recipient FROM orders WHERE id = ?",
                (order_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return {"ok": True}
            
            status, user_id, product_type, stars, months, recipient = row
            
            if status == 'completed':
                return {"ok": True}
            
            if product_type == "stars":
                result = await buy_stars_logic(recipient, stars, SEED, 0)
            else:
                result = await buy_premium_logic(recipient, months, SEED, 0)
            
            if result.get('data') or result.get('confirm_referer'):
                await db.execute(
                    "UPDATE orders SET status = ? WHERE id = ?",
                    ('completed', order_id)
                )
                await db.commit()
                
                try:
                    from webhook import bot_instance
                    if bot_instance:
                        product_text = f"⭐ {stars} звёзд" if product_type == "stars" else f"👑 Premium {months} мес"
                        await bot_instance.send_message(
                            user_id,
                            f"✅ Заказ выполнен!\n\n"
                            f"{product_text} успешно отправлены @{recipient}\n"
                            f"📦 Заказ #{order_id}\n\n"
                            f"Спасибо за покупку!"
                        )
                except:
                    pass
            else:
                await db.execute(
                    "UPDATE orders SET status = ? WHERE id = ?",
                    ('failed', order_id)
                )
                await db.commit()
    
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
