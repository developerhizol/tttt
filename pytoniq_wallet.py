from typing import Dict, Any
import asyncio
import aiohttp
from pytoniq_core import Address, StateInit, begin_cell, WalletMessage, WalletV4Data
from pytoniq_core.crypto.keys import mnemonic_to_private_key
from pytoniq_core.crypto.signature import sign_message
from config import MNEMONIC

class PytoniqWalletManager:
    
    def __init__(self):
        self.mnemonic = MNEMONIC
        self.keypair = None
        self.public_key = None
        self.private_key = None
        self.address = None
        self.seqno = 0
        
    async def init_wallet(self):
        try:
            mnemonic_list = self.mnemonic if isinstance(self.mnemonic, list) else self.mnemonic.split()
            self.public_key, self.private_key = mnemonic_to_private_key(mnemonic_list)
            
            from pytoniq_core import Cell
            
            code = Cell.one_from_boc("b5ee9c7241021001000228000114ff00f4a413f4bcf2c80b01020120020d020148030402dcd020d749c120915b8f6320d70b1f2082106578746ebd21821073696e74bdb0925f03e082106578746eba8eb48020d72101d074d721fa4030fa44f828fa443058bd915be0ed44d0810140d721f404305c810108f40a6fa131b3925f05e004d33ffa00fa4021f001ed44d0810140d720c801cf16f400c9ed540172b08e23821064737472bdb0925f06e05f04840ff2f00082028e3526f0018210d53276db103744006d71708010c8cb055003cf1622fa0212cb6acb1fcb3fc98042fb00007801fa00f40430f8276f2230500aa121bef2e0508210706c7567bd22821064737472ba925f06e30d06070201200809007801fa00f40430f8276f2230500aa121bef2e0508210706c7567bd22821064737472ba925f06e30d02012009200a0201480b0c8e26c2fff2fff274006040423d029be84c600f00840206c1804f")
            data = begin_cell().store_uint(0, 32).store_uint(698983191, 32).store_bytes(self.public_key).store_uint(0, 1).end_cell()
            state_init = StateInit(code=code, data=data)
            
            self.address = Address((0, state_init.serialize().hash))
            address_str = self.address.to_str(is_bounceable=False)
            
            await self.update_seqno()
            balance = await self.get_balance()
            
            return True
            
        except Exception as e:
            raise
    
    async def update_seqno(self):
        try:
            address_str = self.address.to_str(is_bounceable=False)
            url = f"https://tonapi.io/v2/blockchain/accounts/{address_str}/methods/seqno"
            headers = {"Authorization": f"Bearer {TONAPI_KEY}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.seqno = int(data.get('decoded', {}).get('state', 0))
                    else:
                        self.seqno = 0
        except Exception as e:
            self.seqno = 0
    
    async def get_balance(self) -> float:
        try:
            address_str = self.address.to_str(is_bounceable=False)
            url = f"https://tonapi.io/v2/accounts/{address_str}"
            headers = {"Authorization": f"Bearer {TONAPI_KEY}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return int(data.get("balance", 0)) / 1e9
            return 0.0
        except Exception as e:
            return 0.0
    
    async def send_transaction(self, destination: str, amount: float, comment: str = "") -> Dict[str, Any]:
        result = {"address": destination, "amount": amount, "success": False, "tx_hash": None, "error": None}
        
        try:
            await self.update_seqno()
            
            dest_address = Address(destination)
            body = begin_cell().store_uint(0, 32).store_string(comment).end_cell()
            
            wallet_msg = WalletMessage(
                dest=dest_address,
                value=int(amount * 1e9),
                body=body,
                mode=3
            )
            
            wallet_data = WalletV4Data(
                seqno=self.seqno,
                wallet_id=698983191,
                messages=[wallet_msg],
                op_code=0
            )
            
            to_sign = wallet_data.serialize()
            signature = sign_message(to_sign.hash, self.private_key)
            
            final_body = begin_cell().store_bytes(signature).store_cell(to_sign).end_cell()
            
            from pytoniq_core import ExternalMsgInfo, MessageAny
            
            external_msg = MessageAny(
                info=ExternalMsgInfo(
                    src=Address((0, b'\x00' * 32)),
                    dest=self.address
                ),
                init=None,
                body=final_body
            )
            
            boc = external_msg.serialize().to_boc()
            
            import base64
            boc_b64 = base64.b64encode(boc).decode()
            
            url = "https://tonapi.io/v2/blockchain/message"
            headers = {
                "Authorization": f"Bearer {TONAPI_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {"boc": boc_b64}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        tx_hash = data.get('hash', '')
                        result.update({"success": True, "tx_hash": tx_hash})
                        self.seqno += 1
                    else:
                        result["error"] = "Failed to send BOC"
                        
        except Exception as e:
            result["error"] = str(e)
            
        return result
    
    async def verify_transaction(self, tx_hash: str, expected_address: str, expected_amount: float) -> Dict[str, Any]:
        url = f"https://tonapi.io/v2/blockchain/transactions/{tx_hash}"
        headers = {"Authorization": f"Bearer {TONAPI_KEY}"}
        
        for attempt in range(1, 7):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            out_msgs = data.get("out_msgs", [])
                            
                            for msg in out_msgs:
                                dest = msg.get("destination", {}).get("address", "")
                                value = int(msg.get("value", 0)) / 1e9
                                
                                dest_normalized = dest.replace('EQ', 'UQ').replace('UQ', '')
                                exp_normalized = expected_address.replace('EQ', 'UQ').replace('UQ', '')
                                
                                if dest_normalized == exp_normalized and abs(value - expected_amount) < 0.001:
                                    return {"confirmed": True, "tx_hash": tx_hash}
                        
                        elif resp.status == 404:
                            pass
                
            except Exception as e:
                pass
            
            if attempt < 6:
                await asyncio.sleep(5 + (attempt * 2))
        
        return {"confirmed": False, "error": "Not confirmed", "tx_hash": tx_hash}
    
    async def close(self):
        pass

async def get_wallet_info() -> Dict[str, Any]:
    wm = PytoniqWalletManager()
    await wm.init_wallet()
    
    balance = await wm.get_balance()
    address = wm.address.to_str(is_bounceable=False)
    
    return {
        "address": address,
        "balance": balance,
        "balance_usd": balance * 6.0
    }
