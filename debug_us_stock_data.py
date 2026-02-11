import asyncio
import logging
from app.core.kis_api import kis
from app.core.technical_analysis import technical
from app.core.selector import selector
from app.core.ai_analyzer import ai_analyzer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_us_data():
    logger.info("Starting US Data Test...")
    
    # 1. Test Token
    token = kis.get_access_token()
    logger.info(f"Token: {token[:10]}...")
    
    # 2. Test List (The 12 items from selector.py)
    candidates = [
        {"symbol": "NVDA", "excg": "NASD", "name": "NVIDIA"},
        {"symbol": "TSLA", "excg": "NASD", "name": "Tesla"},
        {"symbol": "AAPL", "excg": "NASD", "name": "Apple"},
        {"symbol": "MSFT", "excg": "NASD", "name": "Microsoft"},
        {"symbol": "AMD", "excg": "NASD", "name": "AMD"},
        {"symbol": "PLTR", "excg": "NYSE", "name": "Palantir"},
        {"symbol": "COIN", "excg": "NASD", "name": "Coinbase"},
        {"symbol": "MARA", "excg": "NASD", "name": "Marathon Digital"},
        {"symbol": "NET", "excg": "NYSE", "name": "Cloudflare"},
        {"symbol": "IONQ", "excg": "NYSE", "name": "IonQ"},
        {"symbol": "SOXL", "excg": "NYSE", "name": "Direxion Daily Semi Bull 3X"},
        {"symbol": "TQQQ", "excg": "NASD", "name": "ProShares UltraPro QQQ"}
    ]
    
    for stock in candidates:
        symbol = stock['symbol']
        excg = stock['excg']
        name = stock['name']
        
        logger.info(f"--- Checking {name} ({symbol}) ---")
        
        # A. Fetch Daily Price
        daily_data = kis.get_overseas_daily_price(symbol, excg)
        if not daily_data:
            logger.error(f"❌ No Daily Data for {symbol}")
            continue
            
        logger.info(f"✅ Data Fetched: {len(daily_data)} days")
        logger.info(f"   Latest: {daily_data[0]}")
        
        # B. Map Data for Tech Analysis
        mapped_data = []
        for d in daily_data:
            mapped_data.append({
                "stck_bsop_date": d['xymd'],
                "stck_clpr": d['clos'],
                "stck_oprc": d['open'],
                "stck_hgpr": d['high'],
                "stck_lwpr": d['low'],
                "acml_vol": d['tvol']
            })
            
        # C. Run Tech Analysis
        tech = technical.analyze(mapped_data)
        
        if tech.get("status") in ["Error", "Not enough data"]:
             logger.error(f"❌ Tech Analysis Failed: {tech.get('status')}")
             continue

        logger.info(f"   RSI: {tech['rsi']:.2f}")
        logger.info(f"   Trend: {tech['trend']}")
        logger.info(f"   SMA5: {tech['sma_5']:.2f}, SMA20: {tech['sma_20']:.2f}")
        
        # Check Filters (Matching selector.py)
        passed = True
        # Relaxed SMA5 < SMA20 filter to allow breakouts
        # if tech['sma_5'] <= tech['sma_20']:
        #     logger.warning(f"   🚫 Filter Fail: Weak Trend (SMA5 < SMA20)")
        #     passed = False
        if tech['rsi'] >= 75: # Matches selector.py (US relaxed RSI)
            logger.warning(f"   🚫 Filter Fail: High RSI ({tech['rsi']:.1f})")
            passed = False
        if tech['trend'] == "DOWN": 
            logger.warning(f"   🚫 Filter Fail: Down Trend")
            passed = False

        # Calc Daily Change
        daily_change = 0.0
        try:
            curr = float(daily_data[0]['clos'])
            prev = float(daily_data[1]['clos'])
            if prev > 0:
                daily_change = ((curr - prev) / prev) * 100
            logger.info(f"   Daily Change: {daily_change:.2f}%")
            
            if daily_change >= 20.0:
                 logger.warning(f"   🚫 Filter Fail: Too Volatile (+{daily_change:.1f}%)")
                 passed = False
        except:
            pass
            
        if passed:
            logger.info(f"   ✨ Passed Technical Filters! (Ready for AI)")
        else:
            logger.info(f"   ❌ Failed Technical Filters")


if __name__ == "__main__":
    asyncio.run(test_us_data())
