
import asyncio
import sys
import os
import logging

# Add current directory to path
sys.path.append(os.getcwd())

# Configure logging
logging.basicConfig(level=logging.INFO)

async def test_market_data():
    from app.core.market_data import market_data_manager
    
    print("Triggering update...")
    # First call returns empty, triggers background task
    data = await market_data_manager.get_market_data()
    print(f"First call data: {data}")
    
    print("Waiting for background update...")
    # Directly call update to await it
    await market_data_manager._update_data()
    
    print("Result after update:")
    print(market_data_manager.cache)
    
    if not market_data_manager.cache:
        print("FAIL: Cache is empty.")
    else:
        print("SUCCESS: Cache populated.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_market_data())
