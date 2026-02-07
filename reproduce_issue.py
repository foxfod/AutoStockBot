
import sys
import os
import logging
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mocking kis_api before importing trade_manager
sys.modules['app.core.kis_api'] = MagicMock()
from app.core.kis_api import kis

from app.core.trade_manager import TradeManager

# Setup basic logging
logging.basicConfig(level=logging.INFO)

def test_liquidate_crash():
    tm = TradeManager()
    
    # Mock KIS responses
    kis.get_my_stock_balance.return_value = []
    kis.get_overseas_outstanding_orders.return_value = []
    
    # Simulate a US holding response MISSING 'ovrs_now_pric2'
    # This mirrors the user's reported error scenario
    kis.get_overseas_balance.return_value = {
        'summary': {},
        'holdings': [
            {
                'ovrs_pdno': 'AAPL',
                'ovrs_item_name': 'Apple',
                'ovrs_excg_cd': 'NAS',
                'ovrs_ord_psbl_qty': '10',
                # 'ovrs_now_pric2': '150.00'  <-- MISSING KEY
            }
        ]
    }

    print(">>> Running liquidation (Expecting Crash)...")
    try:
        tm.liquidate_all_positions(market_filter="US")
        print(">>> Liquidation finished without error (Unexpected if bug exists)")
    except KeyError as e:
        print(f">>> CAUGHT EXPECTED CRASH: KeyError: {e}")
    except Exception as e:
        print(f">>> CAUGHT UNEXPECTED ERROR: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_liquidate_crash()
