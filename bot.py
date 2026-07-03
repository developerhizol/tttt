import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart

from config import BOT_TOKEN
from db import init_db, add_user
from currency import rate_updater
from webhook import create_app, set_bot

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    await add_user(message.from_user.id, message.from_user.username)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⭐ Купить звёзды или Premium",
            web_app=WebAppInfo(url="https://your-domain.com/")
        )]
    ])
    
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "💎 Выбери товар в магазине:\n"
        "⭐ Telegram Stars — от 50 шт.\n"
        "👑 Telegram Premium — 3/6/12 месяцев\n\n"
        "🛒 Нажми кнопку ниже, чтобы открыть магазин",
        reply_markup=kb
    )

async def main():
    await init_db()
    
    global bot, dp
    bot = Bot(token=BOT_TOKEN)
    set_bot(bot)
    
    dp = Dispatcher()
    dp.include_router(router)
    
    asyncio.create_task(rate_updater())
    
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8001)
    await site.start()
    print("Webhook server started on :8001")
    
    print("Bot polling started...")
    try:
        await dp.start_polling(bot, handle_signals=False)
    finally:
        await runner.cleanup()

bot = None
dp = None

if __name__ == "__main__":
    asyncio.run(main())
