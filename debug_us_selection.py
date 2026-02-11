import asyncio
import logging
import sys
from app.core.selector import selector
from app.core.kis_api import kis

# Configure logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
logger = logging.getLogger("DebugUS")

async def test_us_selection():
    print("\n=== Testing US Stock Selection Logic ===")
    
    # 1. Test Price Fetch for a known stock
    print("\n1. Testing Price Fetch (NVDA)...")
    try:
        price = kis.get_overseas_price("NVDA", "NASD")
        print(f"NVDA Price: {price}")
    except Exception as e:
        print(f"Price Fetch Failed: {e}")

    # 2. Test Selection
    print("\n2. Running select_us_stocks(budget=1000)...")
    try:
        # Pass a budget high enough to include most stocks
        results = await selector.select_us_stocks(budget=1000)
        print(f"\nFinal Results: {len(results)} stocks selected.")
        
        if not results:
            print("No stocks selected. Checking logs for filter reasons...")
            
        for stock in results:
            print(f" [SELECTED] {stock['name']} ({stock['symbol']}) - Score: {stock['score']}")
            
    except Exception as e:
        print(f"Selection Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_us_selection())
