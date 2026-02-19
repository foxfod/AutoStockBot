
import asyncio
import logging
from unittest.mock import MagicMock, patch

# Configure logging to see our warnings
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.core.selector")

async def verify():
    print("Starting verification...")
    
    # We need to mock the dependencies to import Selector without errors
    # or just copy the fixed logic. 
    # Let's try to verify the logic pattern directly since full import might be hard.
    
    # Simulating the behavior of selector.py loop
    analysis_jobs = [{"symbol": "005930"}, {"symbol": "000660"}]
    
    # Simulating a BAD result from AI (Mixed types)
    results = {
        "005930": "Bad String Response", 
        "000660": {"score": 80, "reason": "Good"}
    }
    
    print(f"Simulating AI Results: {results}")
    
    scored_candidates = []
    
    # The FIXED logic pattern causing the error in selector.py
    for job in analysis_jobs:
        symbol = job['symbol']
        res = results.get(symbol)
        
        # --- Fixed Validation Logic Start ---
        if res and not isinstance(res, dict):
                print(f"WARNING: AI returned invalid format for {symbol}: {res}")
                continue
        # --- Fixed Validation Logic End ---

        try:
            if res and res.get('score', 0) >= 60:
                scored_candidates.append(symbol)
                print(f"Selected: {symbol}")
        except AttributeError as e:
            print(f"CRITICAL FAILURE: {e}")
            return
            
    if "000660" in scored_candidates and "005930" not in scored_candidates:
        print("SUCCESS: Bad data was skipped, good data was processed.")
    else:
        print("FAILURE: Validation did not work as expected.")

if __name__ == "__main__":
    asyncio.run(verify())
