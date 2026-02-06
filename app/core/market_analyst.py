import logging
from app.core.kis_api import kis

logger = logging.getLogger(__name__)

class MarketAnalyst:
    def __init__(self):
        pass

    def get_market_status(self, market_type="KR"):
        """
        Analyze current market status (Bull/Bear/Neutral).
        Returns: { "trend": "BULL", "description": "..." }
        """
        try:
            if market_type == "KR":
                # Check KOSPI (0001) and KOSDAQ (1001)
                kospi = kis.get_current_index("0001") # KOSPI
                kosdaq = kis.get_current_index("1001") # KOSDAQ
                
                trend = "NEUTRAL"
                desc = "Flat market"
                
                if kospi:
                    rate = float(kospi.get('prdy_ctrt', 0)) # Change Rate
                    if rate > 0.5: trend = "BULL"
                    elif rate < -0.5: trend = "BEAR"
                    desc = f"KOSPI {'▲' if rate > 0 else '▼'}{rate}%"
                    
                return {"trend": trend, "description": desc, "data": kospi}
                
            else: # US
                # Check NASDAQ (COMP)
                # Note: KIS might return COMP or .IXIC depending on symbol mapping
                nasdaq = kis.get_overseas_index("COMP", "NAS") # Nasdaq Composite
                
                trend = "NEUTRAL"
                desc = "Flat market"
                
                if nasdaq:
                    rate = float(nasdaq.get('rate', 0).replace('%',''))
                    if rate > 0.5: trend = "BULL"
                    elif rate < -0.5: trend = "BEAR"
                    desc = f"NASDAQ {'▲' if rate > 0 else '▼'}{rate}%"
                    
                return {"trend": trend, "description": desc, "data": nasdaq}
                
        except Exception as e:
            logger.error(f"Market Analysis Failed: {e}")
            return {"trend": "NEUTRAL", "description": "Error fetching data"}

    def get_market_context_for_ai(self, market_type="KR"):
        """
        Generate a natural language summary of the market for AI prompt.
        """
        status = self.get_market_status(market_type)
        trend = status['trend']
        desc = status['description']
        
        # TODO: Add Sector Analysis (Using News or Rank) behavior here later.
        # For now, base it on Index.
        
        context = f"Current Market Trend is {trend} ({desc}). "
        
        if trend == "BEAR":
            context += "Market is under pressure. Prefer defensive stocks or strict stop-losses."
        elif trend == "BULL":
            context += "Market is strong. Look for momentum plays but watch for overbought conditions."
            
        return context

market_analyst = MarketAnalyst()
