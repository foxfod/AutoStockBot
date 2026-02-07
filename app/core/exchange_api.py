
import requests
import json
import time
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

class ExchangeApi:
    def __init__(self):
        self.api_key = "f9zozqmszIywIaQu2O63NsEFjK9cWJ0t"
        self.base_url = "https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON"
        self.cache_file = "exchange_rate.json"
        
    def get_exchange_rate(self) -> float:
        """
        Get USD/KRW exchange rate.
        Strategy:
        1. Check local cache (exchange_rate.json). If today's data exists, use it.
        2. If not, call API.
        3. If API fails or returns null (holiday/before 11am), use last saved rate or default 1450.
        """
        today_str = datetime.now().strftime("%Y%m%d")
        
        # 1. Load from Cache
        cached_data = self._load_cache()
        if cached_data:
            if cached_data.get("date") == today_str and cached_data.get("rate"):
                return cached_data["rate"]
            
            # If cache exists but is old, we keep it as backup
            last_rate = cached_data.get("rate", 1450.0)
        else:
            last_rate = 1450.0 # Extreme fallback

        # 2. Call API
        logger.info(f"💱 Fetching Exchange Rate for {today_str}...")
        try:
            params = {
                "authkey": self.api_key,
                "searchdate": today_str,
                "data": "AP01"
            }
            # verify=False might be needed if SSL cert issues occur, but try standard first
            res = requests.get(self.base_url, params=params, timeout=10)
            data = res.json()
            
            if not data:
                # Likely holiday or before 11am
                logger.warning("⚠️ Exchange API returned empty data (Holiday or too early). Using last rate.")
                return last_rate
                
            # 3. Parse USD
            usd_rate = None
            for item in data:
                if item.get("cur_unit") == "USD":
                    # deal_bas_r is string like "1,450.50"
                    raw_rate = item.get("deal_bas_r", "").replace(",", "")
                    usd_rate = float(raw_rate)
                    break
            
            if usd_rate:
                logger.info(f"✅ Updated Exchange Rate: 1 USD = {usd_rate} KRW")
                self._save_cache(today_str, usd_rate)
                return usd_rate
            else:
                logger.warning("⚠️ USD not found in API response. Using last rate.")
                return last_rate

        except Exception as e:
            logger.error(f"❌ Failed to fetch exchange rate: {e}")
            return last_rate

    def _load_cache(self):
        if not os.path.exists(self.cache_file):
            return None
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _save_cache(self, date_str, rate):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump({"date": date_str, "rate": rate}, f)
        except Exception as e:
            logger.error(f"Failed to save exchange rate cache: {e}")

# Singleton instance
exchange_api = ExchangeApi()
