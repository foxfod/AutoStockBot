import asyncio
import sys
import os

# Add path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.telegram_bot import bot
from app.core.kis_api import kis
from app.core.trade_manager import trade_manager

async def test_system():
    print("=== System Verification ===")
    
    # 1. Telegram Test
    print("\n[1] Testing Telegram...")
    try:
        bot.send_message("🔔 Verification: System Check Init.")
        print("  - Message sent check your Telegram.")
    except Exception as e:
        print(f"  - Telegram Failed: {e}")

    # 2. KIS API Balance
    print("\n[2] Testing KIS Balance...")
    try:
        balance = kis.get_balance()
        if balance:
            print(f"  - Deposit: {balance.get('dnca_tot_amt')} KRW")
        else:
            print("  - Failed to get balance (Check API Keys or Maintenance Hours).")
    except Exception as e:
        print(f"  - Balance Error: {e}")

    # 3. KIS Holdings
    print("\n[3] Testing KIS Holdings...")
    try:
        holdings = kis.get_my_stock_balance()
        print(f"  - Holdings Count: {len(holdings)}")
        for h in holdings:
            print(f"    - {h['prdt_name']}: {h['hldg_qty']} sh")
    except Exception as e:
        print(f"  - Holdings Error: {e}")

    # 4. Trigger Selector? (Optional, might be slow or return empty at night)
    print("\n[4] Skipping Selector Test (Night Time).")
    
    print("\n=== Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(test_system())
