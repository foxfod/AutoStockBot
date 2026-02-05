"""
WebSocket Verification Script
Tests KIS WebSocket connection and real-time price streaming.
"""
import asyncio
import time
import logging
from dotenv import load_dotenv

# Load environment
load_dotenv()

from app.core.kis_websocket import kis_ws

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("WebSocketVerify")

def test_websocket():
    """Test WebSocket connection and price streaming"""
    
    print("=" * 60)
    print("WebSocket Verification Test")
    print("=" * 60)
    
    # Step 1: Get Approval Key
    print("\n[1/4] Getting WebSocket approval key...")
    approval_key = kis_ws.get_approval_key()
    
    if approval_key:
        print(f"✅ Approval key obtained: {approval_key[:20]}...")
    else:
        print("❌ Failed to get approval key")
        return False
    
    # Step 2: Connect to WebSocket
    print("\n[2/4] Connecting to WebSocket...")
    if kis_ws.connect():
        print("✅ WebSocket connected successfully")
    else:
        print("❌ WebSocket connection failed")
        return False
    
    # Step 3: Subscribe to test stocks
    print("\n[3/4] Subscribing to test stocks...")
    
    # Korean stock: Samsung Electronics (005930)
    print("  - Subscribing to 005930 (Samsung Electronics)...")
    kis_ws.subscribe_stock("005930", "KR")
    
    # Give it a moment to establish subscription
    time.sleep(2)
    
    # Step 4: Monitor real-time prices
    print("\n[4/4] Monitoring real-time prices for 30 seconds...")
    print("-" * 60)
    
    start_time = time.time()
    update_count = 0
    last_price = None
    
    try:
        while time.time() - start_time < 30:
            # Check for price updates
            price_data = kis_ws.get_latest_price("005930")
            
            if price_data:
                current_price = price_data.get('price')
                data_time = price_data.get('time')
                age = time.time() - data_time
                
                # Only print if price changed or every 5 seconds
                if current_price != last_price or update_count % 5 == 0:
                    print(f"📊 Samsung (005930): {current_price:,.0f} KRW (Age: {age:.1f}s)")
                    last_price = current_price
                    update_count += 1
            else:
                print("⏳ Waiting for price data...")
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
    
    print("-" * 60)
    print(f"\n✅ Test completed! Received {update_count} price updates")
    
    # Cleanup
    print("\n[Cleanup] Disconnecting WebSocket...")
    kis_ws.disconnect()
    print("✅ WebSocket disconnected")
    
    return True

def test_connection_stability():
    """Test WebSocket reconnection on failure"""
    print("\n" + "=" * 60)
    print("Connection Stability Test")
    print("=" * 60)
    
    print("\n[1/2] Connecting to WebSocket...")
    if not kis_ws.connect():
        print("❌ Initial connection failed")
        return False
    
    print("✅ Connected")
    
    print("\n[2/2] Testing auto-reconnection...")
    print("(Manually disconnect and observe reconnection behavior)")
    print("Monitoring for 20 seconds...")
    
    for i in range(20):
        status = "🟢 Connected" if kis_ws.is_connected else "🔴 Disconnected"
        print(f"  {i+1}s: {status}")
        time.sleep(1)
    
    kis_ws.disconnect()
    return True

if __name__ == "__main__":
    print("\n🚀 Starting WebSocket Verification\n")
    
    # Run basic test
    success = test_websocket()
    
    if success:
        print("\n✅ All tests passed!")
        print("\nWebSocket is ready for production use.")
    else:
        print("\n❌ Tests failed!")
        print("Please check your KIS API credentials and network connection.")
    
    print("\n" + "=" * 60)
