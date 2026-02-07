
import yfinance as yf
import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MarketDataManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MarketDataManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return
        self.initialized = True
        self.cache = {}
        self.last_update = None
        self.update_interval = timedelta(minutes=5)
        self.is_updating = False
        
        # Tickers map
        self.tickers = {
            # Indices
            "kospi": "^KS11", 
            "kosdaq": "^KQ11",
            "nasdaq": "^IXIC", 
            "dji": "^DJI", 
            "sp500": "^GSPC",
            
            # Commodities (Futures)
            "gold": "GC=F", 
            "silver": "SI=F", 
            "oil": "CL=F",
            
            # Exchange Rates (Yahoo Finance)
            "usd_krw": "KRW=X",
            "eur_krw": "EURKRW=X",
            "jpy_krw": "JPYKRW=X"
        }

    async def get_market_data(self):
        """
        Returns cached market data. Triggers update if stale.
        Structure:
        {
            "kospi": {"price": 2500.0, "change": 10.5, "rate": 0.42},
            ...
            "last_updated": "2024-01-01 12:00:00"
        }
        """
        now = datetime.now()
        
        # Check if update needed
        if self.last_update is None or (now - self.last_update) > self.update_interval:
            if not self.is_updating:
                asyncio.create_task(self._update_data())
        
        return self.cache

    async def _update_data(self):
        self.is_updating = True
        try:
            logger.info("🌍 Updating Market Data (yfinance)...")
            # Fetch all tickers at once (space separated)
            ticker_str = " ".join(self.tickers.values())
            data = await asyncio.to_thread(yf.download, ticker_str, period="2d", interval="1d", progress=False, threads=True)
            
            # yfinance returns MultiIndex DataFrame.
            # Close price: data['Close'][ticker]
            # We need Today's Close (or current price) and Yesterday's Close for change.
            
            # Note: yfinance structure varies by version. 
            # If period='2d', we get up to 2 rows. 
            # Row -1 is latest, Row -2 is previous close.
            
            new_cache = {}
            valid_data = False
            
            if not data.empty:
                # 'Close' column might be at top level or second level depending on how many tickers
                # If multiple tickers, columns are (PriceType, Ticker)
                
                # Check if 'Close' is in columns first level
                closes = data.get('Close')
                
                if closes is not None and not closes.empty:
                    for key, symbol in self.tickers.items():
                        try:
                            if symbol in closes.columns:
                                series = closes[symbol].dropna()
                                if len(series) >= 2:
                                    prev_close = series.iloc[-2]
                                    curr_price = series.iloc[-1]
                                    
                                    change = curr_price - prev_close
                                    rate = (change / prev_close) * 100
                                    
                                    new_cache[key] = {
                                        "price": float(curr_price),
                                        "change": float(change),
                                        "rate": float(rate)
                                    }
                                elif len(series) == 1:
                                     # Only one data point (maybe first day of listing or data gap)
                                     curr_price = series.iloc[-1]
                                     new_cache[key] = {
                                        "price": float(curr_price),
                                        "change": 0.0,
                                        "rate": 0.0
                                    }
                        except Exception as e:
                            logger.error(f"Error parsing {key} ({symbol}): {e}")
                            
                    valid_data = True

            if valid_data:
                new_cache["last_updated"] = datetime.now().strftime("%H:%M:%S")
                self.cache = new_cache
                self.last_update = datetime.now()
                logger.info(f"✅ Market Data Updated: {len(new_cache)-1} items")
            else:
                logger.warning("⚠️ Market Data Update Failed: No valid data")

        except Exception as e:
            logger.error(f"❌ Market Data Update Error: {e}")
        finally:
            self.is_updating = False

# Singleton
market_data_manager = MarketDataManager()
