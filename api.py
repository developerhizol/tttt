import aiohttp
from typing import Dict, Any, Optional

FRAGMENT_API_URL = "https://fragment-api.tech/api/v1"
FRAGMENT_HEADERS = {
    "accept": "application/json",
    "Content-Type": "application/json"
}

class FragmentAPIClient:
    
    def __init__(self, seed: str, wallet_version: str = "V5R1"):
        self.seed = seed
        self.wallet_version = wallet_version
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=FRAGMENT_HEADERS)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{FRAGMENT_API_URL}/{endpoint}"
        async with self.session.post(url, json=data) as resp:
            return await resp.json()
    
    async def buy_stars(
        self, 
        username: str, 
        quantity: int, 
        payment_method: str = "ton",
        show_sender: bool = True
    ) -> Dict[str, Any]:
        data = {
            "seed": self.seed,
            "wallet_version": self.wallet_version,
            "username": username if username.startswith("@") else f"@{username}",
            "quantity": quantity,
            "payment_method": payment_method,
            "show_sender": show_sender
        }
        return await self._post("stars/buy", data)
    
    async def buy_premium(
        self,
        username: str,
        months: int,
        payment_method: str = "ton",
        show_sender: bool = True
    ) -> Dict[str, Any]:
        data = {
            "seed": self.seed,
            "wallet_version": self.wallet_version,
            "username": username if username.startswith("@") else f"@{username}",
            "months": months,
            "payment_method": payment_method,
            "show_sender": show_sender
        }
        return await self._post("premium/gift", data)
    
    async def check_recipient(self, username: str, product_type: str = "stars") -> Dict[str, Any]:
        if product_type == "stars":
            endpoint = "stars/recipient"
        else:
            endpoint = "premium/recipient"
        
        data = {
            "username": username if username.startswith("@") else f"@{username}"
        }
        return await self._post(endpoint, data)

async def buy_stars_logic(username: str, quantity: int, seed: str, show_sender: bool = True) -> Dict[str, Any]:
    async with FragmentAPIClient(seed) as client:
        return await client.buy_stars(username, quantity, show_sender=show_sender)

async def buy_premium_logic(username: str, months: int, seed: str, show_sender: bool = True) -> Dict[str, Any]:
    async with FragmentAPIClient(seed) as client:
        return await client.buy_premium(username, months, show_sender=show_sender)

async def check_recipient(username: str, product_type: str = "stars", seed: str = "") -> Dict[str, Any]:
    async with FragmentAPIClient(seed) as client:
        return await client.check_recipient(username, product_type)
