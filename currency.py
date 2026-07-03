import aiohttp
import asyncio
from config import STAR_PRICE_USD, RATE_UPDATE_INTERVAL

_cache = {"usd_rub": 100.0, "last_update": 0}

async def fetch_usd_rate() -> float:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["rates"].get("RUB", 100.0)
    except:
        pass
    return _cache["usd_rub"]

async def update_rate():
    _cache["usd_rub"] = await fetch_usd_rate()
    _cache["last_update"] = asyncio.get_event_loop().time()

async def get_usd_rate() -> float:
    now = asyncio.get_event_loop().time()
    if now - _cache["last_update"] > RATE_UPDATE_INTERVAL:
        await update_rate()
    return _cache["usd_rub"]

async def calc_price_rub(stars: int) -> float:
    rate = await get_usd_rate()
    return round(stars * STAR_PRICE_USD * rate, 2)

async def rate_updater():
    while True:
        await update_rate()
        await asyncio.sleep(RATE_UPDATE_INTERVAL)
