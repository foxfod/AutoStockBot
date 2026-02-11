import logging
import requests
from bs4 import BeautifulSoup
from app.core.kis_api import kis

logger = logging.getLogger(__name__)

class MarketAnalyst:
    def __init__(self):
        pass

    def scrape_market_news(self, market_type="KR"):
        """
        Scrapes market news headlines from a financial news source.
        """
        try:
            if market_type == "KR":
                url = "https://finance.naver.com/news/mainnews.naver"
                headers = {"User-Agent": "Mozilla/5.0"}
                res = requests.get(url, headers=headers, timeout=10)
                soup = BeautifulSoup(res.text, "html.parser")
                
                # Naver Finance Main News uses 'articleSubject' class
                titles = []
                for item in soup.select(".articleSubject a"):
                    titles.append(item.text.strip())
                    
                # Also check "Most Viewed" if main news is sparse?
                # For now, Main News is good for Market Trend.
                
                return titles[:10] # Top 10 Headlines
                
            elif market_type == "US":
                # US scraping is harder (anti-bot). Use valid RSS or limited scraping.
                # Yahoo Finance RSS: https://finance.yahoo.com/news/rssindex
                url = "https://finance.yahoo.com/news/rssindex"
                res = requests.get(url, timeout=10)
                soup = BeautifulSoup(res.content, "xml")
                
                titles = []
                for item in soup.find_all("item"):
                    titles.append(item.title.text)
                    
                return titles[:10]
                
        except Exception as e:
            logger.error(f"News Scraping Failed: {e}")
            return []
            
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

    async def get_trend_candidates(self, market_type="KR"):
        """
        Scrape news -> AI Analysis -> Extract Trend Candidates.
        Returns list of dicts: [{'name': 'Samsung', 'code': '005930', 'reason': '...'}, ...]
        Cache Results for 60 minutes to save AI Cost.
        """
        import time
        
        # Initialize cache if not exists
        if not hasattr(self, 'trend_cache'):
            self.trend_cache = {} # { 'KR': {'time': ts, 'data': []} }
            
        # Check Cache
        cached = self.trend_cache.get(market_type)
        if cached:
            # Valid for 60 minutes
            if (time.time() - cached['time']) < 3600:
                logger.info(f"Using Cached Trend Candidates for {market_type} (Age: {int((time.time() - cached['time'])/60)}m)")
                return cached['data']
        
        from app.core.ai_analyzer import ai_analyzer
        
        # 1. Scrape News
        news_titles = self.scrape_market_news(market_type)
        if not news_titles:
            logger.warning("No news scraped for trend analysis.")
            return []
            
        logger.info(f"Scraped {len(news_titles)} headlines for {market_type} Trend Analysis.")
        
        # 2. AI Analysis (Extract Candidates)
        trend_stocks = await ai_analyzer.recommend_trend_stocks(news_titles, market_type)
        
        # Update Cache
        self.trend_cache[market_type] = {
            'time': time.time(),
            'data': trend_stocks
        }
        
        return trend_stocks


market_analyst = MarketAnalyst()
