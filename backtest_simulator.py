import os
import sys
import logging
import time
import asyncio
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load Env
load_dotenv()

# Setup paths to import app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.technical_analysis import technical
from app.core.ai_analyzer import ai_analyzer
from app.core.kis_api import kis

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("Backtest")

async def run_backtest():
    print("=== Stock Selection Logic Backtest (Jan 2026) ===")
    
    # 1. Define Date Range (Trading Days in Jan 2026)
    # Using KRX calendar via FDR or manual list
    # Let's iterate business days
    start_date = "2026-01-02"
    end_date = "2026-01-31"
    
    dates = pd.date_range(start=start_date, end=end_date, freq='B') # Business days
    
    results = []
    
    for current_date_ts in dates:
        current_date_str = current_date_ts.strftime("%Y%m%d")
        print(f"\n[Processing Date: {current_date_str}]")
        
        # 1. Candidate Selection (Mocking 'Volume Rank')
        # We pick top 5 active stocks from Previous Day to simulate "Stocks with attention"
        prev_date_ts = current_date_ts - timedelta(days=1)
        while prev_date_ts.weekday() > 4: # Skip weekends
           prev_date_ts -= timedelta(days=1)
        prev_date_str = prev_date_ts.strftime("%Y%m%d")
        
        try:
            # FDR: Get KRX market data for PREVIOUS day
            # Note: fdr.StockListing('KRX') gives current info. 
            # fdr.DataReader('KRX', date) is not quite right for "Ranking" of that day easily without fetching all.
            # Optimization: Use a few fixed volatile stocks or just Fetch Top Gainers using a loop is too slow.
            # Alternative: Random pick from a known list of "Active Stocks" in Jan OR
            # Use a few manual big movers of Jan for validation. 
            # BETTER: Use fdr.DataReader('005930', ...) to just test Logic on Samsung Elec + Top Volatile.
            # Let's pick 3 target stocks for test: 
            # 1. Samsung Elec (005930) - Stable
            # 2. SK Hynix (000660) - Stable
            # 3. Jeju Semiconductor (080220) - Volatile (Example)
             
            # Actually, let's try to get "Top Gainers" proxy if possible.
            # Since fetching ALL stocks for ranking is slow, we will test on a fixed set of ~5 stocks 
            # + 2 random ones to see if AI Filters them correctly.
            
            test_candidates = [
                {"symbol": "005930", "name": "삼성전자"}, # Samsung
                {"symbol": "000660", "name": "SK하이닉스"}, # SK Hynix
                {"symbol": "001510", "name": "SK증권"}, # User's Interest
                {"symbol": "000270", "name": "기아"}, # Kia
                {"symbol": "042700", "name": "한미반도체"} # Volatile AI stock
            ]
            
            day_results = []
            
            for stock in test_candidates:
                symbol = stock['symbol']
                name = stock['name']
                
                # A. Get OHLCV Data (Using KIS for consistency with App, passing logic)
                # But KIS returns 100 days from TODAY. 
                # technical.analyze now supports filtering.
                # Use daily_data from KIS (Real) -> Filtered by target_date
                
                # Note: If rate limit is an issue, add sleep
                time.sleep(0.1) 
                
                daily_data = kis.get_daily_price(symbol, days=150) # Request enough days
                
                # B. Technical Analysis (Time Travel)
                tech_summary = technical.analyze(daily_data, target_date=current_date_str)
                
                if tech_summary.get("status") in ["Error", "Not enough data"]:
                    print(f"  - {name}: Not enough data before {current_date_str}")
                    continue
                
                # Filter Logic (Duplicate of Selector.py)
                # 1. Trend Filter
                if tech_summary['sma_5'] <= tech_summary['sma_20']:
                    print(f"  - {name}: Skipped (SMA5 {tech_summary['sma_5']:.0f} <= SMA20 {tech_summary['sma_20']:.0f})")
                    continue
                    
                # 2. RSI Filter
                if tech_summary['rsi'] >= 70:
                    print(f"  - {name}: Skipped (RSI {tech_summary['rsi']} >= 70)")
                    continue
                    
                # 3. Down Trend
                if tech_summary['trend'] == "DOWN":
                     print(f"  - {name}: Skipped (Trend DOWN)")
                     continue
                    
                # C. Get News (Try to fetch news)
                time.sleep(0.1)
                news_items = kis.get_news_titles(symbol, search_date=current_date_str)
                news_titles = [n['hts_pbnt_titl_cntt'] for n in news_items[:3]] if news_items else [] 
                
                # D. AI Score
                # Calling AI Analyzer (Sync wrapper)
                # We need to pass valid data.
                
                # Mock AI call to avoid OPENAI Cost? 
                # User wants "Accuracy". We MUST use real AI.
                # Warning: 20 days * 5 stocks = 100 AI calls. Might be expensive/slow.
                # Let's limit to 3 days for initial test? Or user asked for "Jan Simulation".
                # Let's do it.
                
                ai_result = ai_analyzer.analyze_stock(name, news_titles, tech_summary)
                
                score = ai_result.get('score', 0)
                action = "BUY" if score >= 70 else "WAIT"
                
                # E. Verification (Did it rise?)
                # Get actual OHLCV for current_date using FDR
                df_verify = fdr.DataReader(symbol, current_date_str, current_date_str)
                
                actual_outcome = "N/A"
                profit_potential = 0.0
                
                if not df_verify.empty:
                    open_price = df_verify.iloc[0]['Open']
                    high_price = df_verify.iloc[0]['High']
                    close_price = df_verify.iloc[0]['Close']
                    
                    if open_price > 0:
                        profit_potential = ((high_price - open_price) / open_price) * 100
                        day_change = ((close_price - open_price) / open_price) * 100
                        
                        actual_outcome = f"Max: {profit_potential:.2f}%, End: {day_change:.2f}%"
                        
                        # Check "Hit"
                        is_win = (action == "BUY" and profit_potential > 2.0) # Assume 2% scalping target
                        
                        day_results.append({
                            "Date": current_date_str,
                            "Name": name,
                            "Score": score,
                            "AI_Action": action,
                            "Actual": actual_outcome,
                            "Win": is_win if action == "BUY" else None
                        })
                        print(f"  - {name}: Score {score} ({action}) -> Actual: {actual_outcome}")
            
            results.extend(day_results)
            
        except Exception as e:
            print(f"Error processing {current_date_str}: {e}")
            
    # Summary
    print("\n=== Backtest Summary ===")
    df_res = pd.DataFrame(results)
    if not df_res.empty:
        buys = df_res[df_res['AI_Action'] == 'BUY']
        print(f"Total Trading Days: {len(dates)}")
        print(f"Total AI Buys: {len(buys)}")
        if not buys.empty:
            wins = buys[buys['Win'] == True]
            win_rate = (len(wins) / len(buys)) * 100
            print(f"Win Rate (Target 2%): {win_rate:.2f}% ({len(wins)}/{len(buys)})")
            
            # Save to CSV
            df_res.to_csv("backtest_jan_2026.csv", index=False)
            print("Detailed results saved to backtest_jan_2026.csv")
    else:
        print("No results generated.")

if __name__ == "__main__":
    asyncio.run(run_backtest())
