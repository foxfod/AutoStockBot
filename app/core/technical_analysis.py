import pandas as pd
import logging

logger = logging.getLogger(__name__)

class TechnicalAnalyzer:
    def __init__(self):
        pass

    def analyze(self, daily_data: list, target_date: str = None) -> dict:
        """
        Calculate technical indicators from daily data.
        Expected daily_data key format: 
        stck_bsop_date (Date), stck_clpr (Close), stck_oprc (Open), stck_hgpr (High), stck_lwpr (Low), acml_vol (Vol)
        
        target_date (YYYYMMDD): If provided, filter data to keep only records strictly BEFORE this date.
        """
        if not daily_data or len(daily_data) < 20:
            return {"status": "Not enough data"}

        if target_date:
            # Filter logic: Keep data strictly before target_date to simulate pre-market analysis
            filtered_data = [d for d in daily_data if d['stck_bsop_date'] < target_date]
            if not filtered_data or len(filtered_data) < 20:
                print(f"Not enough data before {target_date}. Count: {len(filtered_data)}")
                return {"status": "Not enough data"}
            daily_data = filtered_data

        try:
            df = pd.DataFrame(daily_data)
            # Rename columns for convenience
            # stck_clpr: Close, stck_oprc: Open, stck_hgpr: High, stck_lwpr: Low, acml_vol: Volume
            df = df.rename(columns={
                'stck_bsop_date': 'date',
                'stck_clpr': 'close',
                'stck_oprc': 'open',
                'stck_hgpr': 'high',
                'stck_lwpr': 'low',
                'acml_vol': 'volume'
            })
            
            # Convert types
            cols = ['close', 'open', 'high', 'low', 'volume']
            for col in cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
            # Sort by date ascending
            df = df.sort_values('date')
            
            # Calculate Indicators
            # SMA
            df['sma_5'] = df['close'].rolling(window=5).mean()
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_60'] = df['close'].rolling(window=60).mean()
            
            # RSI (14)
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi_14'] = 100 - (100 / (1 + rs))
            
            # Get latest values (last row)
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            result = {
                "close": latest['close'],
                "sma_5": latest['sma_5'],
                "sma_20": latest['sma_20'],
                "rsi": round(latest['rsi_14'], 2),
                "trend": "UP" if latest['close'] > latest['sma_20'] else "DOWN",
                "volatility": (latest['high'] - latest['low']) / latest['close'] * 100 # Simple daily volatility %
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Technical Analysis Error: {e}")
            return {"status": "Error"}

technical = TechnicalAnalyzer()
