from app.core.selector import selector
from app.core.kis_api import kis
from app.core.ai_analyzer import ai_analyzer
import logging
import sys

# Configure logging to show everything
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

print("=== Starting Debug Selection ===")

print("1. Testing KIS Token...")
try:
    token = kis.get_access_token()
    print(f"Token received. Length: {len(token)}")
except Exception as e:
    print(f"Token Failed: {e}")
    sys.exit(1)

print("\n2. Testing Volume Rank...")
try:
    candidates = kis.get_volume_rank()
    print(f"Candidates received: {len(candidates) if candidates else 'None'}")
    if candidates:
        print(f"First candidate: {candidates[0]}")
except Exception as e:
    print(f"Volume Rank Failed: {e}")

print("\n3. Testing Full Selection Logic...")
try:
    # Run the actual selector
    results = selector.select_stocks()
    print(f"\nFinal Results: {len(results)} stocks selected.")
    for stock in results:
        print(f" - {stock['name']} ({stock['score']}): {stock['reason']}")
except Exception as e:
    print(f"Selection Logic Failed: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Debug Complete ===")
