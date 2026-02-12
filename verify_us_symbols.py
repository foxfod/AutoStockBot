import sys
import os
import asyncio
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.getcwd())

# Load Env
load_dotenv()

from app.core.kis_api import kis

async def verify():
    # List of failing stocks from user report
    targets = [
        {"symbol": "MU", "excg": "NASD"},  # Micron
        {"symbol": "QCOM", "excg": "NASD"}, # Qualcomm
        {"symbol": "NVDA", "excg": "NASD"}, # NVIDIA
        {"symbol": "CRWD", "excg": "NASD"}, # CrowdStrike
        {"symbol": "MSFT", "excg": "NASD"}, # Microsoft
        {"symbol": "GOOGL", "excg": "NASD"}, # Alphabet
        {"symbol": "AMAT", "excg": "NASD"}, # Applied Materials
        {"symbol": "LRCX", "excg": "NASD"}, # Lam Research
    ]

    print("--- Verifying US Stock Symbols ---")
    
    for t in targets:
        symbol = t['symbol']
        excg = t['excg']
        
        # Test 1: Price Check (Should accept NASD if verification script uses kis_api mapping logic?)
        # Wait, get_overseas_price also has mapping logic in kis_api.py?
        # Yes, I saw it: if excg_cd == "NASD": mapped_3char = "NAS"
        
        print(f"\nChecking {symbol} ({excg})...")
        price = kis.get_overseas_price(symbol, excg)
        
        if price:
            print(f"OK Price Fetch: SUCCESS ({price.get('last')}) - Exchange: {excg} -> Mapped internally")
        else:
            print(f"FAIL Price Fetch: FAILED")
            
            # Try manual NAS
            print(f"   Retrying with 'NAS'...")
            price_nas = kis.get_overseas_price(symbol, "NAS")
            if price_nas:
                print(f"   OK 'NAS' WORKED! ({price_nas.get('last')})")
            else:
                print(f"   FAIL 'NAS' FAILED too.")

if __name__ == "__main__":
    asyncio.run(verify())
