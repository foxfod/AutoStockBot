import asyncio
import time
from app.core.selector import selector
from app.core.technical_analysis import technical
from app.core.ai_analyzer import ai_analyzer
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_async_speed():
    print("🚀 Starting Async Top 10 Speed Test...")
    start_time = time.time()
    
    # Run US Selection (Mock Mode or Real?)
    # Since we don't have real market data in mock, it might fail or return empty,
    # but we want to see if it Runs Parallel without blocking.
    
    # We can patch kis_api to simulate delay
    from app.core.kis_api import kis
    
    # Mocking KIS API for speed test (optional, or use real if token valid)
    # Let's try real first if token exists. If not, mock.
    
    try:
        # Run Scanner
        picks = await selector.select_pre_market_picks("US")
        print(f"✅ Result Count: {len(picks)}")
    except Exception as e:
        print(f"❌ Error: {e}")
        
    elapsed = time.time() - start_time
    print(f"⏱️ Total Time: {elapsed:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(test_async_speed())
