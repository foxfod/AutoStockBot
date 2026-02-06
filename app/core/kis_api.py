import requests
import json
import time
from datetime import datetime, timedelta
from app.core.config import settings
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class KisApi:
    def __init__(self):
        self.base_url = settings.KIS_BASE_URL
        self.app_key = settings.KIS_APP_KEY
        self.app_secret = settings.KIS_APP_SECRET
        self.account_no = settings.KIS_ACCOUNT_NO
        self.access_token = None
        self.token_expired = 0
        self.websocket = None  # Will be initialized when needed

    def _get_headers(self, tr_id=None):
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        if tr_id:
            headers["tr_id"] = tr_id
        return headers

    def get_access_token(self):
        """Get or refresh access token (with File Persistence)"""
        TOKEN_FILE = "kis_token_v2.json"
        
        # 1. Try to load from file
        try:
            with open(TOKEN_FILE, "r") as f:
                data = json.load(f)
                saved_token = data.get("access_token")
                saved_expiry = data.get("token_expired", 0)
                
                if saved_token and time.time() < saved_expiry:
                    self.access_token = saved_token
                    self.token_expired = saved_expiry
                    # logger.info("KIS Access Token Loaded from File (Valid)")
                    return self.access_token
        except (FileNotFoundError, json.JSONDecodeError):
            pass # File doesn't exist or corrupt, fetch new
            
        # 2. If memory token is valid, use it
        if self.access_token and time.time() < self.token_expired:
            return self.access_token

        # 3. Request New Token
        url = f"{self.base_url}/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        
        try:
            res = requests.post(url, json=body, timeout=20)
            data = res.json()
            if res.status_code == 200:
                self.access_token = data['access_token']
                # Expires in usually 86400s (24h). Safety buffer 60s
                self.token_expired = time.time() + float(data['expires_in']) - 60 
                
                # 4. Save to File
                try:
                    with open(TOKEN_FILE, "w") as f:
                        json.dump({
                            "access_token": self.access_token,
                            "token_expired": self.token_expired
                        }, f)
                    logger.info("KIS Access Token Refreshed & Saved")
                except Exception as e:
                    logger.warning(f"Failed to save token file: {e}")
                    
                return self.access_token
            else:
                logger.error(f"Failed to get token: {data}")
                if "EGW00133" in str(data):
                    logger.critical("⚠️ KIS Token Rate Limit (1/min). Please wait 1 minute.")
                raise Exception(f"KIS Token Error: {data}")
        except Exception as e:
            logger.error(f"Error getting token: {str(e)}")
            raise

    def get_realtime_price(self, symbol: str, market_type: str = "KR") -> Optional[Dict]:
        """
        Get real-time price from WebSocket if available, otherwise fallback to REST API.
        
        Args:
            symbol: Stock symbol
            market_type: "KR" or "US"
            
        Returns:
            Dict with price information or None
        """
        # Try WebSocket first
        if self.websocket and self.websocket.is_connected:
            ws_data = self.websocket.get_latest_price(symbol)
            if ws_data and (time.time() - ws_data['time']) < 5:  # Data less than 5 seconds old
                return ws_data
        
        # Fallback to REST API
        if market_type == "KR":
            data = self.get_current_price(symbol)
            if data:
                return {
                    'price': float(data.get('stck_prpr', 0)),
                    'volume': int(data.get('acml_vol', 0)),
                    'time': time.time(),
                    'market_type': 'KR'
                }
            return None
        else:
            # For US stocks, extract exchange code from subscribed stocks or default to NAS
            excg_cd = "NAS"
            if self.websocket and symbol in self.websocket.subscribed_stocks:
                # Try to get exchange from subscription info if available
                pass
            price_data = self.get_overseas_price(symbol, excg_cd)
            if price_data:
                return {
                    'price': float(price_data.get('last', 0)),
                    'volume': 0,
                    'time': time.time(),
                    'market_type': 'US'
                }
        return None
    
    def get_current_price(self, symbol: str):
        """Get current price for a stock"""
        self.get_access_token()
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        headers = self._get_headers(tr_id="FHKST01010100") 
        
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": symbol
        }
        
        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code == 200:
                return res.json()['output']
            logger.error(f"Get Price Failed: {res.status_code} {res.text}")
        except Exception as e:
            logger.error(f"Get Price Connection Error: {e}")
        return None

    def get_volume_rank(self):
        """Get top volume stocks"""
        self.get_access_token()
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/volume-rank"
        headers = self._get_headers(tr_id="FHPST01710000")
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_SCR_DIV_CODE": "20171",
            "FID_INPUT_ISCD": "0000",
            "FID_DIV_CLS_CODE": "0",
            "FID_BLNG_CLS_CODE": "0",
            "FID_TRGT_CLS_CODE": "111111111",
            "FID_TRGT_EXLS_CLS_CODE": "000000",
            "FID_INPUT_PRICE_1": "0",
            "FID_INPUT_PRICE_2": "0",
            "FID_VOL_CNT": "0",
            "FID_INPUT_DATE_1": "0"
        }
        
        res = requests.get(url, headers=headers, params=params, timeout=20)
        if res.status_code == 200:
            return res.json()['output']
        logger.error(f"Failed to get volume rank: {res.text}")
        return []

    def get_news_titles(self, symbol: str, search_date: str = None):
        """Get news titles for a stock"""
        self.get_access_token()
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/news-title"
        headers = self._get_headers(tr_id="FHKST01011800")
        
        target_date = search_date if search_date else time.strftime("%Y%m%d")
        
        params = {
            "FID_NEWS_OFER_ENTP_CODE": "", # News Provider Code
            "FID_COND_MRKT_CLS_CODE": "",  # Market Class Code
            "FID_INPUT_ISCD": symbol,      # Stock Code
            "FID_TITL_CNTT": "",           # Title Content
            "FID_INPUT_DATE_1": target_date, # Date
            "FID_INPUT_HOUR_1": "000000",  # Time
            "FID_RANK_SORT_CLS_CODE": "",  # Rank Sort
            "FID_INPUT_SRNO": ""           # Serial No
        }
        
        res = requests.get(url, headers=headers, params=params, timeout=20)
        data = res.json()
        if res.status_code == 200 and 'output' in data:
            return data['output']
        elif data.get('msg_cd') == 'OPSQ0002':
            # This specific error usually means the stock/ETF is not supported by the News API
            # Common for ETFs (e.g., KODEX Inverse). Treat as "No News".
            logger.info(f"News API not supported for {symbol} (OPSQ0002). Skipping.")
            return []
        else:
            logger.warning(f"No news or error for {symbol}: {data}")
            return []

    def get_overseas_news_titles(self, symbol: str, search_date: str = None):
        """Get Overseas News Titles (Breaking News)"""
        self.get_access_token()
        url = f"{self.base_url}/uapi/overseas-price/v1/quotations/brknews-title"
        headers = self._get_headers(tr_id="FHKST01011801")
        
        target_date = search_date if search_date else datetime.now().strftime("%Y%m%d")
        
        # Using same params structure as domestic news (FHKST01011800)
        params = {
            "FID_NEWS_OFER_ENTP_CODE": "", 
            "FID_COND_MRKT_CLS_CODE": "",
            "FID_INPUT_ISCD": symbol,
            "FID_TITL_CNTT": "",
            "FID_INPUT_DATE_1": target_date,
            "FID_INPUT_HOUR_1": "000000",
            "FID_RANK_SORT_CLS_CODE": "",
            "FID_INPUT_SRNO": ""
        }
        
        try:
            res = requests.get(url, headers=headers, params=params, timeout=5)
            data = res.json()
            if res.status_code == 200 and 'output' in data:
                return data['output']
            
            # logger.warning(f"No US news for {symbol}: {data.get('msg1')}")
            return []
        except Exception as e:
            logger.error(f"Failed to get US news for {symbol}: {e}")
            return []

    def get_daily_price(self, symbol: str, days: int = 100):
        """Get daily OHLCV data for technical analysis"""
        self.get_access_token()
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        headers = self._get_headers(tr_id="FHKST03010100")
        
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "1" # Adjusted Price
        }
        
        res = requests.get(url, headers=headers, params=params, timeout=20)
        data = res.json()
        
        if res.status_code == 200 and 'output2' in data:
            return data['output2'] # List of daily records
        
        logger.warning(f"Failed to get daily price for {symbol}: {data.get('msg1')}")
        return []

    def get_balance(self):
        """Check account balance"""
        self.get_access_token()
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
        headers = self._get_headers(tr_id="TTTC8434R") # Verify TR_ID for real/virtual
        # Virtual: VTTC8434R, Real: TTTC8434R (Check documentation or try)
        # However, usually the endpoint URLs differ too.
        # Let's handle TR_ID based on URL or settings. Common is TTTC8434R for Real.
        
        # NOTE: KIS TR_ID differs for Real vs Virtual.
        # Real: TTTC8434R (Balance), TTTC0802U (Buy), TTTC0801U (Sell)
        # Virtual: VTTC8434R (Balance), VTTC0802U (Buy), VTTC0801U (Sell)
        
        is_virtual = "openapivts" in self.base_url
        tr_id = "VTTC8434R" if is_virtual else "TTTC8434R"
        headers["tr_id"] = tr_id

        params = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": "01",
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "N",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }
        
        res = requests.get(url, headers=headers, params=params, timeout=20)
        data = res.json()
        if res.status_code == 200 and 'output2' in data:
            return data['output2'][0] # Contains 'dnca_tot_amt' (Deposit), 'tot_evlu_mony' (Total Eval)
        logger.error(f"Failed to get balance: {data}")
        return None

    def get_my_stock_balance(self):
        """Check current holdings"""
        self.get_access_token()
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
        # Same endpoint as balance, but output1 has the list of stocks
        
        is_virtual = "openapivts" in self.base_url
        tr_id = "VTTC8434R" if is_virtual else "TTTC8434R"
        headers = self._get_headers(tr_id=tr_id)

        params = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": "01",
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "N",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }
        
        res = requests.get(url, headers=headers, params=params, timeout=20)
        data = res.json()
        if res.status_code == 200 and 'output1' in data:
            return data['output1'] # List of holdings
    def get_orderable_cash(self):
        """Get exact orderable cash from KIS"""
        self.get_access_token()
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-psbl-order"
        
        is_virtual = "openapivts" in self.base_url
        tr_id = "VTTC8908R" if is_virtual else "TTTC8908R"
        headers = self._get_headers(tr_id=tr_id)
        
        params = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": "01",
            "PDNO": "005930", # Dummy symbol (Samsung)
            "ORD_UNPR": "0",
            "ORD_DVSN": "01", # Market
            "CMA_EVLU_AMT_ICLD_YN": "Y",
            "OVRS_ICLD_YN": "Y"
        }
        
        res = requests.get(url, headers=headers, params=params, timeout=20)
        data = res.json()
        if res.status_code == 200 and 'output' in data:
            return int(data['output']['ord_psbl_cash'])
        
        logger.warning(f"Failed to get orderable cash: {data}")
        return None

    def _place_order(self, symbol, qty, price, order_type):
        """
        Internal order placement.
        order_type: "00" (Limit), "01" (Market)
        """
        self.get_access_token()
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        
        is_virtual = "openapivts" in self.base_url
        # Buy/Sell TR_ID logic handled in wrapper methods or passed in?
        # Actually it's better to strictly separate Buy/Sell logic for TR_ID.
        pass

    def buy_order(self, symbol: str, qty: int, price: int = 0):
        """
        Buy Order.
        If price is 0, assumes Market Price ("01"), else Limit Price ("00").
        """
        self.get_access_token()
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        
        is_virtual = "openapivts" in self.base_url
        tr_id = "VTTC0802U" if is_virtual else "TTTC0802U" # Buy
        
        headers = self._get_headers(tr_id=tr_id)
        
        order_div = "01" if price == 0 else "00" # 01: Market, 00: Limit
        
        body = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": "01",
            "PDNO": symbol,
            "ORD_DVSN": order_div,
            "ORD_QTY": str(qty),
            "ORD_UNPR": str(int(price)) if price > 0 else "0", 
        }
        
        res = requests.post(url, headers=headers, json=body, timeout=20)
        data = res.json()
        
        if res.status_code == 200 and data['rt_cd'] == '0':
            return data['output'] # Contains 'KRX_FWDG_ORD_ORGNO' (Order ID)
        
        logger.error(f"Buy Order Failed: {data}")
        return {"error": data.get('msg1')}

    def sell_order(self, symbol: str, qty: int, price: int = 0):
        """
        Sell Order.
        If price is 0, assumes Market Price ("01"), else Limit Price ("00").
        """
        self.get_access_token()
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        
        is_virtual = "openapivts" in self.base_url
        tr_id = "VTTC0801U" if is_virtual else "TTTC0801U" # Sell
        
        headers = self._get_headers(tr_id=tr_id)
        
        order_div = "01" if price == 0 else "00"
        
        body = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": "01",
            "PDNO": symbol,
            "ORD_DVSN": order_div,
            "ORD_QTY": str(qty),
            "ORD_UNPR": str(int(price)) if price > 0 else "0", 
        }
        
        res = requests.post(url, headers=headers, json=body, timeout=20)
        data = res.json()
        
        if res.status_code == 200 and data['rt_cd'] == '0':
            return data['output']
        
        logger.error(f"Sell Order Failed: {data}")
        return {"error": data.get('msg1')}

    def get_orders(self):
        """Get list of orders (filled/unfilled)"""
        # Monitoring open orders to cancel if needed
        self.get_access_token()
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
        
        is_virtual = "openapivts" in self.base_url
        tr_id = "VTTC8001R" if is_virtual else "TTTC8001R" 
        
        headers = self._get_headers(tr_id=tr_id)
        
        params = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": "01",
            "INQR_STRT_DT": datetime.now().strftime("%Y%m%d"),
            "INQR_END_DT": datetime.now().strftime("%Y%m%d"),
            "SLL_BUY_DVSN_CD": "00", # All
            "INQR_DVSN": "00", # Descending
            "PDNO": "",
            "CCLD_DVSN": "00", # All (00), Executed (01), Unexecuted (02)
            "ORD_GNO_BRNO": "",
            "ODNO": "",
            "INQR_DVSN_3": "00",
            "INQR_DVSN_1": "",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }

        res = requests.get(url, headers=headers, params=params, timeout=20)
        data = res.json()
        if res.status_code == 200 and 'output1' in data:
            return data['output1']
        return []

    def cancel_order(self, order_no, order_branch="01", qty=0, is_buy=True):
        """
        Cancel an existing order.
        qty: 0 means cancel all.
        """
        self.get_access_token()
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-rvsecncl"
        
        is_virtual = "openapivts" in self.base_url
        # Buy Cancel: VTTC0803U / Sell Cancel: VTTC0801U? -> No, Cancel is separate TR.
        # Real: TTTC0803U (Cancel)
        # Virtual: VTTC0803U (Cancel)
        
        tr_id = "VTTC0803U" if is_virtual else "TTTC0803U"
        headers = self._get_headers(tr_id=tr_id)
        
        body = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": "01",
            "KRX_FWDG_ORD_ORGNO": order_no, # Original Order No
            "ORGN_ODNO": order_no,
            "ORD_DVSN": "00", # 00: Limit, 01: Market. For cancel, usually 00 works for residual.
            "RVSE_CNCL_DVSN_CD": "02", # 01: Modify, 02: Cancel
            "ORD_QTY": str(qty), # 0 for all
            "ORD_UNPR": "0", 
            "QTY_ALL_ORD_YN": "Y" if qty == 0 else "N"
        }
        
        res = requests.post(url, headers=headers, json=body, timeout=20)
        data = res.json()
        
        if res.status_code == 200 and data['rt_cd'] == '0':
            return data['output']
        
        logger.error(f"Cancel Order Failed: {data}")
        return {"error": data.get('msg1')}

    # === US Stock API Support ===

    def get_overseas_price(self, symbol: str, excg_cd: str = "NAS"):
        """
        Get current price for US Stock (with Auto-Retry).
        excg_cd: NAS (Nasdaq), NYS (NYSE), AMS (Amex)
        """
        self.get_access_token()
        url = f"{self.base_url}/uapi/overseas-price/v1/quotations/price"
        headers = self._get_headers(tr_id="HHDFS00000300") 
        
        # Priority: Requested -> NAS -> NASD -> NYS -> AMS
        # Priority: Mapped 3-char (Best for Data) -> Original -> Fallbacks
        mapped_3char = excg_cd
        if excg_cd == "NASD": mapped_3char = "NAS"
        elif excg_cd == "NYSE": mapped_3char = "NYS"
        elif excg_cd == "AMEX": mapped_3char = "AMS"
        
        codes = [mapped_3char, excg_cd, 'NAS', 'NYS', 'AMS', 'NASD', 'NYSE', 'AMEX']
        unique_codes = []
        for c in codes:
            if c not in unique_codes: unique_codes.append(c)
            
        for code in unique_codes:
            params = {
                "AUTH": "",
                "EXCD": code,
                "SYMB": symbol
            }
            
            try:
                res = requests.get(url, headers=headers, params=params, timeout=5)
                data = res.json()
                if res.status_code == 200 and 'output' in data:
                    val = data['output']
                    # Check if 'last' (price) is present and not empty/zero
                    if val.get('last') and val['last'].strip():
                         return val
                # logger.debug(f"Price fetch failed for {symbol} on {code}")
            except Exception as e:
                logger.error(f"Get US Price Connection Error ({code}): {e}")
                
        logger.warning(f"Failed to get US Price for {symbol} after retries.")
        return None

    def get_overseas_daily_price(self, symbol: str, excg_cd: str = "NAS"):
        """
        Get Daily OHLCV for US Stock.
        """
        self.get_access_token()
        url = f"{self.base_url}/uapi/overseas-price/v1/quotations/dailyprice"
        headers = self._get_headers(tr_id="HHDFS76240000")
        
        # Get data for last 100 days?
        # KIS Overseas Daily Price usually returns pagination or fixed count.
        # Params:
        # SYMB, EXCD, GUBN(0:Daily, 1:Weekly..), RYMD (Reference Date), MODP (0:No Adjust, 1:Adjust)
        
        today_str = datetime.now().strftime("%Y%m%d")
        
        # Data API Compatibility: Maps 4-digit (Ordering) to 3-digit (Data)
        api_excg = excg_cd
        if excg_cd == "NASD": api_excg = "NAS"
        elif excg_cd == "NYSE": api_excg = "NYS"
        elif excg_cd == "AMEX": api_excg = "AMS"
        
        params = {
            "AUTH": "",
            "EXCD": api_excg,
            "SYMB": symbol,
            "GUBN": "0", # Daily
            "BYMD": today_str,
            "MODP": "1" # Adjusted Price
        }
        
        res = requests.get(url, headers=headers, params=params, timeout=20)
        data = res.json()
        
        if res.status_code == 200 and 'output2' in data:
            return data['output2'] # List of daily records
        
        logger.warning(f"Failed to get US daily price for {symbol}: {data.get('msg1')}")
        return []

    def get_overseas_balance(self):
        """
        Check US Account Balance & Holdings.
        Queries ALL US exchanges (NASD, NYSE, AMEX) to get complete holdings.
        """
        self.get_access_token()
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/inquire-balance"
        
        is_virtual = "openapivts" in self.base_url
        tr_id = "VTTS3012R" if is_virtual else "TTTS3012R"
        
        headers = self._get_headers(tr_id=tr_id)
        
        # Query all US exchanges
        exchanges = ["NASD", "NYSE", "AMEX"]  # NASD=NASDAQ, NYSE=NYSE, AMEX=AMEX
        all_holdings = []
        summary = None
        
        for excg in exchanges:
            params = {
                "CANO": self.account_no,
                "ACNT_PRDT_CD": "01",
                "OVRS_EXCG_CD": excg,
                "TR_CRCY_CD": "USD",
                "CTX_AREA_FK200": "",
                "CTX_AREA_NK200": ""
            }
            
            res = requests.get(url, headers=headers, params=params, timeout=20)
            data = res.json()
            
            if res.status_code == 200 and 'output2' in data:
                # Merge holdings from all exchanges
                if data['output1']:
                    all_holdings.extend(data['output1'])
                
                # Use summary from first successful response
                if summary is None:
                    summary = data['output2']
                    
                logger.debug(f"📡 {excg}: Found {len(data['output1'])} holdings")
            else:
                logger.warning(f"⚠️ Failed to query {excg}: {data.get('msg1', 'Unknown error')}")
        
        if summary:
            logger.info(f"✅ Total US holdings across all exchanges: {len(all_holdings)}")
            return {
                "summary": summary,
                "holdings": all_holdings
            }
        
        logger.error(f"❌ Failed to get overseas balance from any exchange")
        return None

    def buy_overseas_order(self, symbol: str, qty: int, price: float = 0, excg_cd: str = "NAS"):
        """
        Buy US Stock.
        price: 0 for Market Order (if supported, else provide limit).
        NOTE: KIS US Market order availability depends on account type. Limit order is safer.
        """
        self.get_access_token()
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/order"
        
        is_virtual = "openapivts" in self.base_url
        # Buy: VTTT1002U (Virtual) / TTTT1002U (Real)
        tr_id = "VTTT1002U" if is_virtual else "TTTT1002U"
        
        logger.info(f"DEBUG: Buying {symbol} on {'Virtual' if is_virtual else 'REAL'} Server. TR_ID: {tr_id}")
        
        headers = self._get_headers(tr_id=tr_id)
        
        # Order Type: 00 (Limit), 32 (Market? Check Docs. KIS US Market order is often restricted)
        # Safer to use Limit High if Market not available, but let's try '00' with price.
        # If price=0, we might need '34' (LOO) or similar? 
        # For simplicity in this bot, we assume Limit Order at Current Price or "00" with price specified.
        # User requested Scalping, so we need fast execution.
        # Let's assume price is provided by caller (Current Price * Buffer).
        
        ord_div = "00" # Limit
        
        logger.info(f"Sending US Buy Order: {symbol} ({excg_cd}) {qty}sh @ {price}")

        body = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": "01",
            "OVRS_EXCG_CD": excg_cd,
            "PDNO": symbol,
            "ORD_QTY": str(qty),
            "OVRS_ORD_UNPR": f"{price:.2f}",
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": ord_div 
        }
        
        logger.info(f"US Order Body: {body}")
        
        res = requests.post(url, headers=headers, json=body, timeout=20)
        data = res.json()
        
        if res.status_code == 200 and data['rt_cd'] == '0':
            return data['output']
        
        logger.error(f"US Buy Order Failed: {data}")
        return data

    def sell_overseas_order(self, symbol: str, qty: int, price: float = 0, excg_cd: str = "NAS"):
        """
        Sell US Stock.
        """
        self.get_access_token()
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/order"
        
        is_virtual = "openapivts" in self.base_url
        # Sell: VTTT1006U (Virtual) / TTTT1006U (Real)
        tr_id = "VTTT1006U" if is_virtual else "TTTT1006U"
        
        headers = self._get_headers(tr_id=tr_id)
        
        ord_div = "00" # Limit
        
        body = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": "01",
            "OVRS_EXCG_CD": excg_cd,
            "PDNO": symbol,
            "ORD_QTY": str(qty),
            "OVRS_ORD_UNPR": f"{price:.2f}",
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": ord_div 
        }
        
        res = requests.post(url, headers=headers, json=body, timeout=20)
        data = res.json()
        
        if res.status_code == 200 and data['rt_cd'] == '0':
            return data['output']
        
        logger.error(f"US Sell Order Failed: {data}")
        return {"error": data.get('msg1')}

    def get_overseas_outstanding_orders(self):
        """Get US Unexecuted Orders (NCCS)"""
        self.get_access_token()
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/inquire-nccs"
        
        is_virtual = "openapivts" in self.base_url
        # TR_ID: VTTS3018R (Virtual) / TTTS3018R (Real)
        tr_id = "VTTS3018R" if is_virtual else "TTTS3018R"
        
        headers = self._get_headers(tr_id=tr_id)
        
        params = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": "01",
            "OVRS_EXCG_CD": "NASD", # Checking NASD usually covers others? Or need loop?
            "SORT_SQN": "DS", # Descending
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": ""
        }
        
        all_orders = []
        # Check all major exchanges
        for excg in ["NASD", "NYSE", "AMEX"]:
            params["OVRS_EXCG_CD"] = excg
            try:
                res = requests.get(url, headers=headers, params=params, timeout=20)
                data = res.json()
                if res.status_code == 200 and 'output' in data:
                     orders = data['output']
                     if orders:
                         # Filter only non-executed
                         for o in orders:
                             # nccs_qty seems to be the key for unexecuted qty
                             if int(float(o.get('nccs_qty', 0))) > 0:
                                 all_orders.append(o)
            except Exception as e:
                logger.error(f"Failed to get US NCCS for {excg}: {e}")
                
        return all_orders

    def cancel_overseas_order(self, order_no, symbol, excg_cd, qty=0):
        """
        Cancel US Order.
        """
        self.get_access_token()
        url = f"{self.base_url}/uapi/overseas-stock/v1/trading/order-rvsecncl"
        
        is_virtual = "openapivts" in self.base_url
        # Cancel: VTTT1004U (Virtual) / TTTT1004U (Real)
        tr_id = "VTTT1004U" if is_virtual else "TTTT1004U"
        
        headers = self._get_headers(tr_id=tr_id)
        
        body = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": "01",
            "OVRS_EXCG_CD": excg_cd,
            "PDNO": symbol,
            "ORGN_ODNO": order_no,
            "RVSE_CNCL_DVSN_CD": "02", # 02: Cancel
            "ORD_QTY": str(qty) if qty > 0 else "0", # 0: Cancel All
            "OVRS_ORD_UNPR": "0", # Price 0
            "ORD_SVR_DVSN_CD": "0" 
        }
        
        res = requests.post(url, headers=headers, json=body, timeout=20)
        data = res.json()
        
        if res.status_code == 200 and data['rt_cd'] == '0':
            return data['output']
        
        logger.error(f"US Cancel Failed: {data}")
        return {"error": data.get('msg1')}

    def get_today_trades(self):
        """Get list of executed trades for today (KR)"""
        self.get_access_token()
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
        
        is_virtual = "openapivts" in self.base_url
        tr_id = "VTTC8001R" if is_virtual else "TTTC8001R"
        headers = self._get_headers(tr_id=tr_id)
        
        from datetime import datetime
        today_str = datetime.now().strftime("%Y%m%d")
        
        params = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": "01",
            "INQR_STRT_DT": today_str,
            "INQR_END_DT": today_str,
            "SLL_BUY_DVSN_CD": "00", # All (Buy/Sell)
            "PDNO": "",
            "CCLD_DVSN": "00",
            "ORD_GNO_BRNO": "",
            "ODNO": "",
            "INQR_DVSN": "00",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }
        
        res = requests.get(url, headers=headers, params=params, timeout=20)
        data = res.json()
        
        if res.status_code == 200 and 'output1' in data:
            return data['output1']
        
        logger.error(f"Failed to get today trades: {data}")
        return []

    # === Market Index Support (Top-Down Analysis) ===

    def get_current_index(self, market_code="0001"):
        """
        Get Domestic Index (KOSPI/KOSDAQ). 
        market_code: "0001" (Kospi), "1001" (Kosdaq)
        """
        self.get_access_token()
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        headers = self._get_headers(tr_id="FHKUP03500100") 
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "U", # U: Upjong (Index)
            "FID_INPUT_ISCD": market_code
        }
        
        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            data = res.json()
            if res.status_code == 200 and 'output' in data:
                return data['output'] # bstp_nmiv (Current), prdy_vrss (Change)
        except Exception as e:
            logger.error(f"Failed to get KR Index {market_code}: {e}")
        return None

    def get_overseas_index(self, symbol="COMP", excg="NAS"):
        """
        Get Overseas Index.
        symbol: COMP (Nasdaq Composite), SPX (S&P500), DJI (Dow Jones)
        excg: NAS/NYS
        """
        self.get_access_token()
        # Use price endpoint but usually specific ticker for index
        return self.get_overseas_price(symbol, excg)

kis = KisApi()
