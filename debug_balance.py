from app.core.kis_api import kis
import logging
import json

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test NAS
print("--- Querying NAS ---")
bal_nas = kis.get_overseas_balance() 
if bal_nas and 'holdings' in bal_nas and len(bal_nas['holdings']) > 0:
    first_holding = bal_nas['holdings'][0]
    print(json.dumps(first_holding, indent=2, ensure_ascii=False))
else:
    print("NAS: No holdings or Error")
