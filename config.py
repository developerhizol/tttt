import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_TOKEN")
DB_PATH = os.getenv("DB_PATH", "stars.db")
JWT_SECRET = os.getenv("JWT_SECRET", "your_jwt_secret_key_here")
STAR_PRICE_USD = float(os.getenv("STAR_PRICE_USD", "0.015"))

MNEMONIC = os.getenv("MNEMONIC", "").split(",") if os.getenv("MNEMONIC") else []
SEED = " ".join(MNEMONIC)

RATE_UPDATE_INTERVAL = 1800
WEBHOOK_PATH = "/payment/callback"