
import asyncio
import sys
import os
import logging

# Add current directory to path
sys.path.append(os.getcwd())

# Configure logging
logging.basicConfig(level=logging.INFO)

# Force UTF-8 for console output
sys.stdout.reconfigure(encoding='utf-8')

async def test_top10_us():
    from app.core.selector import selector
    
    print("🚀 Triggering US Top 10 Selection...")
    try:
        picks = await selector.select_pre_market_picks("US")
        print(f"✅ Result ({len(picks)} items):")
        for p in picks:
            print(f"- {p['name']} ({p['symbol']}): {p['score']}")
            
        if not picks:
            print("⚠️ WARNING: Result is empty. Filters might be too strict or candidate list too small.")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_top10_us())
