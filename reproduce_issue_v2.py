
import asyncio

async def reproduce():
    print("Starting reproduction...")
    
    # Simulate the data structure causing the error
    # The AI analyzer might return a dict where values are strings instead of dicts
    results = {
        "005930": "Analysis: Good stock",  # This should be a dict
        "000660": {"score": 80, "reason": "Good"}
    }
    
    job = {"symbol": "005930"}
    
    try:
        res = results.get(job['symbol'])
        # The vulnerable code in selector.py
        if res and res.get('score', 0) >= 60:
            print("Stock selected")
    except AttributeError as e:
        print(f"Caught expected error: {e}")
        if "'str' object has no attribute 'get'" in str(e):
            print("SUCCESS: Reproduction confirmed.")
        else:
            print("FAILED: Wrong error message.")
    except Exception as e:
        print(f"FAILED: Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(reproduce())
