
import sys
import os
import logging
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock modules
sys.modules['app.core.kis_api'] = MagicMock()
sys.modules['app.core.telegram_bot'] = MagicMock()
sys.modules['app.core.kis_websocket'] = MagicMock()
sys.modules['app.web.main'] = MagicMock()

# Import the function to test
from main_auto_trade import check_market_open, state

def test_weekend_block():
    print(">>> Testing Weekend Block...")
    # Mock Saturday (e.g., 2026-02-07 is Saturday)
    with patch('main_auto_trade.datetime') as mock_date:
        mock_date.now.return_value = datetime(2026, 2, 7, 10, 0, 0)
        mock_date.weekday.return_value = 5 # Saturday
        
        is_open, msg = check_market_open("KR")
        if not is_open and "Weekend" in msg:
            print("✅ Weekend Blocked Successfully (Saturday)")
        else:
            print(f"❌ Failed Weekend Block: {is_open}, {msg}")

def test_circuit_breaker():
    print(">>> Testing Circuit Breaker...")
    # Mock Weekday (e.g., 2026-02-06 is Friday)
    with patch('main_auto_trade.datetime') as mock_date:
        mock_date.now.return_value = datetime(2026, 2, 6, 10, 0, 0)
        mock_date.weekday.return_value = 4 # Friday
        
        # 1. Normal State
        state['kr_market_closed'] = False
        is_open, _ = check_market_open("KR")
        if is_open:
            print("✅ Normal Day Open")
        else:
            print("❌ Failed Normal Day Open")

        # 2. Trigger Circuit Breaker
        state['kr_market_closed'] = True
        is_open, msg = check_market_open("KR")
        if not is_open and "Closed Flag" in msg:
            print("✅ Circuit Breaker Active")
        else:
            print(f"❌ Failed Circuit Breaker: {is_open}, {msg}")

if __name__ == "__main__":
    test_weekend_block()
    test_circuit_breaker()
