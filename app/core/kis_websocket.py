import asyncio
import json
import logging
import time
import websocket
from threading import Thread
from typing import Dict, Optional, Callable
from app.core.config import settings
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode
import requests

logger = logging.getLogger(__name__)


class KisWebSocket:
    """
    KIS API WebSocket Client for Real-time Stock Price Streaming.
    Supports both Korean and US stock markets.
    """
    
    def __init__(self):
        self.base_url = settings.KIS_BASE_URL
        self.app_key = settings.KIS_APP_KEY
        self.app_secret = settings.KIS_APP_SECRET
        self.approval_key = None
        self.ws = None
        self.is_connected = False
        self.subscribed_stocks = {}  # {symbol: {market_type, tr_id}}
        self.latest_prices = {}  # {symbol: {price, volume, time}}
        self.ws_thread = None
        self.running = False
        
        # WebSocket URLs
        is_virtual = "openapivts" in self.base_url
        self.ws_url = "ws://ops.koreainvestment.com:31000" if is_virtual else "ws://ops.koreainvestment.com:21000"
        
        # Encryption key (IV is always 16 bytes of 0x00)
        self.aes_key = None
        self.aes_iv = bytes(16)
        
    def get_approval_key(self) -> Optional[str]:
        """
        Get WebSocket approval key from KIS API.
        This is different from the access token used for REST API.
        """
        url = f"{self.base_url}/oauth2/Approval"
        
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "secretkey": self.app_secret
        }
        
        headers = {
            "content-type": "application/json"
        }
        
        try:
            res = requests.post(url, json=body, headers=headers, timeout=10)
            data = res.json()
            
            if res.status_code == 200 and 'approval_key' in data:
                self.approval_key = data['approval_key']
                logger.info("✅ WebSocket Approval Key obtained")
                return self.approval_key
            else:
                logger.error(f"Failed to get approval key: {data}")
                return None
        except Exception as e:
            logger.error(f"Error getting approval key: {e}")
            return None
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            # KIS WebSocket data format: "header|body" or encrypted format
            if isinstance(message, str):
                parts = message.split('|')
                
                if len(parts) >= 2:
                    header = parts[0]
                    body = parts[1]
                    
                    # Parse header (contains TR_ID, encryption flag, etc.)
                    # Format: TR_ID^encryption_flag^...
                    header_parts = header.split('^')
                    
                    if len(header_parts) >= 3:
                        tr_id = header_parts[0]
                        is_encrypted = header_parts[1] == '1'
                        
                        # Decrypt if encrypted
                        if is_encrypted and self.aes_key:
                            try:
                                cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_iv)
                                decrypted = unpad(cipher.decrypt(b64decode(body)), AES.block_size)
                                body = decrypted.decode('utf-8')
                            except Exception as e:
                                logger.warning(f"Decryption failed: {e}")
                                return
                        
                        # Parse body data
                        self._parse_price_data(tr_id, body)
                        
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
    
    def _parse_price_data(self, tr_id: str, data: str):
        """Parse real-time price data from WebSocket message"""
        try:
            # Data is separated by '^'
            fields = data.split('^')
            
            # Different TR_IDs have different field structures
            if tr_id == "H0STCNT0":  # Korean stock real-time price
                # Field structure for H0STCNT0 (체결가)
                # 0: 종목코드, 1: 체결시간, 2: 현재가, 3: 전일대비, 4: 등락률
                # 5: 거래량, 6: 거래대금, ...
                if len(fields) >= 6:
                    symbol = fields[0]
                    current_price = float(fields[2]) if fields[2] else 0
                    volume = int(fields[5]) if fields[5] else 0
                    
                    self.latest_prices[symbol] = {
                        'price': current_price,
                        'volume': volume,
                        'time': time.time(),
                        'market_type': 'KR'
                    }
                    
                    logger.debug(f"📊 KR Price Update: {symbol} = {current_price:,.0f} KRW")
                    
            elif tr_id == "HDFSCNT0":  # US stock real-time price
                # Field structure for HDFSCNT0
                if len(fields) >= 3:
                    symbol = fields[0]
                    current_price = float(fields[2]) if fields[2] else 0
                    
                    self.latest_prices[symbol] = {
                        'price': current_price,
                        'volume': 0,
                        'time': time.time(),
                        'market_type': 'US'
                    }
                    
                    logger.debug(f"📊 US Price Update: {symbol} = ${current_price:.2f}")
                    
        except Exception as e:
            logger.error(f"Error parsing price data: {e}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        logger.error(f"WebSocket Error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        self.is_connected = False
        logger.warning(f"WebSocket Closed: {close_status_code} - {close_msg}")
        
        # Auto-reconnect if still running
        if self.running:
            logger.info("Attempting to reconnect in 5 seconds...")
            time.sleep(5)
            self.connect()
    
    def _on_open(self, ws):
        """Handle WebSocket connection open"""
        self.is_connected = True
        logger.info("✅ WebSocket Connected")
        
        # Re-subscribe to all previously subscribed stocks
        for symbol, info in list(self.subscribed_stocks.items()):
            self._send_subscribe(symbol, info['market_type'], info['tr_id'])
    
    def connect(self):
        """Establish WebSocket connection"""
        if self.is_connected:
            logger.info("WebSocket already connected")
            return True
            
        if self.ws_thread and self.ws_thread.is_alive():
             logger.warning("WebSocket thread is already active. Skipping new connection.")
             return True

        # Clean up old socket if needed
        if self.ws:
             try: self.ws.close()
             except: pass

        if not self.approval_key:
            if not self.get_approval_key():
                logger.error("Cannot connect: No approval key")
                return False
        
        try:
            # Create WebSocket connection
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            
            # Start WebSocket in a separate thread
            self.running = True
            
            # Use ping_interval and ping_timeout to keep connection alive
            def run_ws():
                # Avoid "Connection is already closed" error
                try:
                    self.ws.run_forever(ping_interval=60, ping_timeout=10)
                except Exception as e:
                    logger.error(f"WS Run Loop Error: {e}")
            
            self.ws_thread = Thread(target=run_ws, daemon=True)
            self.ws_thread.start()
            
            # Wait for connection
            timeout = 10
            start_time = time.time()
            while not self.is_connected and time.time() - start_time < timeout:
                time.sleep(0.1)
            
            if self.is_connected:
                logger.info("WebSocket connection established")
                return True
            else:
                logger.error("WebSocket connection timeout")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting WebSocket: {e}")
            return False
    
    def _send_subscribe(self, symbol: str, market_type: str, tr_id: str):
        """Send subscription request to WebSocket"""
        if not self.is_connected:
            logger.warning("Cannot subscribe: WebSocket not connected")
            return False
        
        try:
            # Build subscription message
            header = {
                "approval_key": self.approval_key,
                "custtype": "P",  # P: Personal, B: Business
                "tr_type": "1",   # 1: Register, 2: Unregister
                "content-type": "utf-8"
            }
            
            body = {
                "tr_id": tr_id,
                "tr_key": symbol
            }
            
            # Combine header and body
            message = json.dumps({"header": header, "body": body})
            
            self.ws.send(message)
            logger.info(f"📡 Subscribed: {symbol} ({market_type})")
            return True
            
        except Exception as e:
            logger.error(f"Error subscribing to {symbol}: {e}")
            return False
    
    def subscribe_stock(self, symbol: str, market_type: str = "KR"):
        """
        Subscribe to real-time price updates for a stock.
        
        Args:
            symbol: Stock symbol (e.g., "005930" for Samsung)
            market_type: "KR" or "US"
        """
        # Determine TR_ID based on market type
        if market_type == "KR":
            tr_id = "H0STCNT0"  # 국내주식 실시간 체결가
        else:
            tr_id = "HDFSCNT0"  # 해외주식 실시간 체결
        
        # Store subscription info
        self.subscribed_stocks[symbol] = {
            'market_type': market_type,
            'tr_id': tr_id
        }
        
        # Send subscription if connected
        if self.is_connected:
            return self._send_subscribe(symbol, market_type, tr_id)
        else:
            logger.warning(f"WebSocket not connected. {symbol} will be subscribed when connected.")
            return False
    
    def unsubscribe_stock(self, symbol: str):
        """Unsubscribe from real-time price updates"""
        if symbol not in self.subscribed_stocks:
            return False
        
        info = self.subscribed_stocks[symbol]
        
        try:
            header = {
                "approval_key": self.approval_key,
                "custtype": "P",
                "tr_type": "2",  # 2: Unregister
                "content-type": "utf-8"
            }
            
            body = {
                "tr_id": info['tr_id'],
                "tr_key": symbol
            }
            
            message = json.dumps({"header": header, "body": body})
            
            if self.is_connected:
                self.ws.send(message)
            
            # Remove from subscribed list
            del self.subscribed_stocks[symbol]
            
            # Remove from price cache
            if symbol in self.latest_prices:
                del self.latest_prices[symbol]
            
            logger.info(f"📡 Unsubscribed: {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error unsubscribing from {symbol}: {e}")
            return False
    
    def get_latest_price(self, symbol: str) -> Optional[Dict]:
        """
        Get the latest price for a subscribed stock.
        
        Returns:
            Dict with 'price', 'volume', 'time', 'market_type' or None if not available
        """
        return self.latest_prices.get(symbol)
    
    def disconnect(self):
        """Close WebSocket connection"""
        self.running = False
        
        if self.ws:
            self.ws.close()
        
        self.is_connected = False
        logger.info("WebSocket disconnected")
    
    def __del__(self):
        """Cleanup on object destruction"""
        self.disconnect()


# Global WebSocket instance
kis_ws = KisWebSocket()
