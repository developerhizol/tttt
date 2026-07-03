from aiohttp import web
from db import get_order, update_order_status
from api import buy_stars_logic, buy_premium_logic
from config import SEED

routes = web.RouteTableDef()

bot_instance = None

def set_bot(bot):
    global bot_instance
    bot_instance = bot

@routes.post("/payment/callback")
async def payment_callback(request: web.Request):
    try:
        data = await request.json()
        order_id = data.get("order_id")
        status = data.get("status")
        tx_hash = data.get("tx_hash", "")
        
        if not order_id or status != "success":
            return web.json_response({"ok": False})
        
        order = await get_order(order_id)
        if not order or order["status"] != "pending":
            return web.json_response({"ok": False, "error": "Order not found or already processed"})
        
        if order["product_type"] == "stars":
            result = await buy_stars_logic(order["recipient"].lstrip("@"), order["stars_count"], SEED, 0)
        else:
            result = await buy_premium_logic(order["recipient"].lstrip("@"), order["months"], SEED, 0)
        
        if result.get("data") or result.get("confirm_referer"):
            await update_order_status(order_id, "completed", tx_hash)
            
            if bot_instance:
                try:
                    product_text = f"⭐ {order['stars_count']} звёзд" if order["product_type"] == "stars" else f"👑 Premium {order['months']} мес"
                    await bot_instance.send_message(
                        order["user_id"],
                        f"✅ Заказ выполнен!\n\n"
                        f"📦 Заказ #{order_id}\n"
                        f"{product_text} → {order['recipient']}\n"
                        f"🔗 TX: {tx_hash}\n\n"
                        f"Товар уже отправлен!"
                    )
                except:
                    pass
            
            return web.json_response({"ok": True, "result": "completed"})
        else:
            await update_order_status(order_id, "failed")
            return web.json_response({"ok": False, "error": "Delivery failed"})
            
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})

@routes.get("/health")
async def health(request: web.Request):
    return web.json_response({"status": "ok"})

@routes.get("/")
async def index(request: web.Request):
    return web.json_response({"service": "stars-bot", "status": "running"})

def create_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    return app
