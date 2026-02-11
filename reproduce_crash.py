
import asyncio
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

async def test_selector():
    print("Importing Selector...")
    try:
        from app.core.selector import selector
        print("Selector imported.")
        
        print("Calling select_pre_market_picks('US')...")
        # We mock bot.send_message to avoid actual telegram messages if possible, 
        # but importing selector likely imports bot. 
        # Let's just run it. If it fails, we see the error.
        
        # We need to mock kis_api calls if we don't want real API calls, 
        # but for a crash test, let's try to run it as is (assuming read-only or safe).
        # select_pre_market_picks writes to a file and sends messages.
        
        await selector.select_pre_market_picks("US")
        print("select_pre_market_picks('US') completed.")
        
        print("Calling select_us_stocks(budget=1000)...")
        await selector.select_us_stocks(budget=1000)
        print("select_us_stocks completed.")

    except Exception as e:
        print(f"RUNTIME ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_selector())
