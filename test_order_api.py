import asyncio
import sys
import os

# Add path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.kis_api import kis

def test_order_connectivity():
    print("=== Testing Buying/Selling API Connectivity ===")
    
    # Target: KODEX 200 (069500), Price: 10,000 (Low enough), Qty: 1
    # Note: Market is likely closed, so we expect a specific error message.
    # If the API call itself is wrong (404/500), we know implementation is wrong.
    # If we get "Market Closed" or "Insufficient Cash", the API works.
    
    print("\n[1] Sending Test Buy Order (Limit 10,000 KRW)...")
    try:
        # Using Limit order ("00") to be safe, though buy_order defaults to Market if price=0.
        # We explicitly pass price=10000 to use limit.
        res = kis.buy_order("069500", qty=1, price=10000)
        
        if "error" in res:
            print(f"  -> Result: Failed as expected.")
            print(f"  -> Server Message: {res['error']}")
            print("  -> (This confirms the API Endpoint is correct and reachable)")
        else:
            print(f"  -> Result: Success?? Order ID: {res['KRX_FWDG_ORD_ORGNO']}")
            print("  -> (Order placed. Check KIS app)")

    except Exception as e:
        print(f"  -> Critical Error: {e}")

    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_order_connectivity()
