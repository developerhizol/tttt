#!/bin/bash

echo "Setting up Telegram Stars/Premium Purchase System..."

python_version=$(python3 --version 2>&1 | grep -Po '(?<=Python )\d+\.\d+')
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" = "$required_version" ]; then
    echo "Python $python_version is compatible"
else
    echo "Python $python_version is not compatible. Please install Python 3.8 or higher."
    exit 1
fi

echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "Please edit .env file with your configuration"
else
    echo ".env file already exists"
fi

if [ ! -f config.py ]; then
    echo "Creating config.py..."
    cat > config.py << 'EOF'
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
EOF
    echo "Please edit config.py with your actual configuration"
else
    echo "config.py already exists"
fi

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your configuration"
echo "2. Run: source venv/bin/activate"
echo "3. Run: python main.py"
