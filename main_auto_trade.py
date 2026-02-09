import asyncio
import time
import logging
from datetime import datetime, timedelta, time as dtime
from dotenv import load_dotenv

# Load Env
load_dotenv()

from app.core.selector import selector
from app.core.trade_manager import trade_manager
from app.core.telegram_bot import bot
from app.core.kis_api import kis
from app.core.kis_websocket import kis_ws
from app.core.logger_handler import AsyncQueueHandler
from app.web.main import app as web_app, server_context
import uvicorn

# Configure Logging
import sys

# Force UTF-8 for console output to handle emojis on Windows
sys.stdout.reconfigure(encoding='utf-8')

# Create Log Queue for Web Dashboard
log_queue = asyncio.Queue(maxsize=1000)

logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("daily_trade.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
        AsyncQueueHandler(log_queue) # Add Web Handler
    ]
)
# Silence OpenAI/HTTPX logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING) # Reduce Web Access Logs

logger = logging.getLogger("AutoTrade")

# === Constants ===
# KR Market
KR_START = dtime(8, 30)
KR_SCAN_START = dtime(8, 40)
KR_TRADE_START = dtime(9, 0)
KR_LIQUIDATION = dtime(15, 15)
KR_CLOSE = dtime(15, 30)

# US Market (Approximate for 24h cycle)
# Adjust for Summer Time manually or add logic later. 
# Winter: Open 23:30. Close 06:00.
# Summer: Open 22:30. Close 05:00.
# We set wide window 22:00 ~ 06:00.
US_START = dtime(22, 0) 
US_SCAN_START = dtime(22, 10)
US_TRADE_START = dtime(22, 30) # Pre-market / Early
US_LIQUIDATION = dtime(5, 40)  # 05:40 AM KST (Before US Close 06:00)
US_CLOSE = dtime(6, 0)

SCAN_INTERVAL = 10 # 10 Minutes
MAX_TRADES = 3
VERSION = "20260209_010-12"

state = {
    "kr_liquidation_done": False,
    "kr_report_sent": False,
    "us_liquidation_done": False,
    "us_report_sent": False,
    "last_scan_time": datetime.min,
    "last_risk_check_time": datetime.min,
    "kr_market_closed": False, # Circuit Breaker for KR
    "us_market_closed": False  # Circuit Breaker for US
}
server_context["log_queue"] = log_queue
server_context["bot_state"] = state
server_context["trade_manager"] = trade_manager
server_context["version"] = VERSION

def is_time_in_range(start, end, current):
    """Check if current time is between start and end (handles midnight wrap)"""
    if start <= end:
        return start <= current <= end
    else: # Crosses midnight
        return start <= current or current <= end

def check_market_open(market_type="KR"):
    """
    Check if the market is open based on:
    1. Weekend (Sat/Sun) -> Closed
    2. Circuit Breaker Flag -> Closed (If API noted holiday previously)
    """
    now = datetime.now()
    
    # 1. Check Weekend (0=Mon, 5=Sat, 6=Sun)
    if now.weekday() >= 5:
        return False, "Weekend (Sat/Sun)"
        
    # 2. Check Circuit Breaker
    if market_type == "KR" and state.get("kr_market_closed"):
        return False, "KR Market Closed Flag Active"
    if market_type == "US" and state.get("us_market_closed"):
        return False, "US Market Closed Flag Active"
        
    return True, "Open"

async def trading_loop():
    """Original Main Loop extracted to a function"""
    bot.send_message(f"🤖 Global Auto Trading System Started (Ver: {VERSION})")
    logger.info(f"System Started - Trading Loop Active (Ver: {VERSION})")
    
    # Initialize WebSocket
    logger.info("Initializing WebSocket connection...")
    kis.websocket = kis_ws  # Link WebSocket to KIS API
    
    if kis_ws.connect():
        bot.send_message("✅ WebSocket Connected - Real-time streaming enabled")
    else:
        bot.send_message("⚠️ WebSocket connection failed - Using REST API fallback")
    
    # Sync Holdings & Send Startup Report
    trade_manager.sync_portfolio()
    startup_msg = trade_manager.get_account_status_str()
    bot.send_message(f"🚀 System Startup Ready\n{startup_msg}")
    
    while True:
        try:
            # Check Pause State
            if server_context.get("is_paused", False):
                # logger.info("Trading Paused...") # Optional: log periodically or just silent
                await asyncio.sleep(1)
                continue

            now = datetime.now()
            t = now.time()
            
            # === KR Mode (08:30 ~ 15:40) ===
            if is_time_in_range(KR_START, dtime(15, 40), t):
                # Reset US flags if entering KR day (e.g. at 08:30)
                if state['us_report_sent']:
                    state['us_liquidation_done'] = False
                    state['us_report_sent'] = False
                    state['us_market_closed'] = False # Reset US Breaker
                
                # Check Market Open (Weekend/Holiday)
                is_open, reason = check_market_open("KR")
                if not is_open:
                    if now.minute == 0 and now.second < 5: # Log once per hour
                        logger.info(f"KR Market Check: Closed ({reason}). Sleeping...")
                    await asyncio.sleep(1)
                    continue

                # 1. Scanning
                time_since = (now - state['last_scan_time']).total_seconds() / 60
                
                is_scan_time = (
                    is_time_in_range(KR_SCAN_START, dtime(14, 30), t) and
                    time_since >= SCAN_INTERVAL
                )
                
                if is_scan_time:
                    open_slots = MAX_TRADES - len([k for k,v in trade_manager.active_trades.items() if v.get('market_type')!='US'])
                    if open_slots > 0:
                        # Check Budget
                        budget = trade_manager.get_available_budget("KR")
                        if budget < 5000:
                            logger.info(f"Skip Scanning: Insufficient KRW ({budget:,.0f})")
                        else:
                            bot.send_message(f"🇰🇷 한국장 스캔 중... ({open_slots} 슬롯, 예산: {budget:,.0f} KRW)")
                            # KR Selection
                            # Ask for more candidates than slots to handle skips (e.g. Add-on skipped)
                            target_count = open_slots + 2 
                            candidates = await selector.select_stocks(budget, target_count=target_count)
                            state['last_scan_time'] = now
                            if candidates:
                                trade_manager.process_signals(candidates) # Filters internally

                # 2. Monitoring
                if is_time_in_range(KR_TRADE_START, KR_LIQUIDATION, t):
                    trade_manager.monitor_active_trades("KR")
                    if now.second % 30 == 0: trade_manager.clean_pending_orders()
                    
                    # AI Risk Check (Every 10 mins) - KR Stocks
                    risk_time_since = (now - state['last_risk_check_time']).total_seconds() / 60
                    if risk_time_since >= 10:
                         trade_manager.monitor_risks("KR")
                         state['last_risk_check_time'] = now

                # 3. Liquidation (Retry Logic)
                # Tried at 15:15. If failing, retry every 2 mins until 15:30.
                if t >= KR_LIQUIDATION:
                    if not state['kr_liquidation_done']:
                        # Check Retry Interval (2 mins)
                        last_try = state.get('last_kr_liquidation_try_time', datetime.min)
                        time_since_try = (now - last_try).total_seconds()
                        
                        if time_since_try >= 120:
                            bot.send_message("⏰ 한국장 마감 임박. 보유 종목 전량 청산 시도...")
                            rem = trade_manager.liquidate_all_positions("KR")
                            state['last_kr_liquidation_try_time'] = now
                            
                            if rem == 0:
                                state['kr_liquidation_done'] = True
                                bot.send_message("✅ 한국장 청산 완료.")
                            else:
                                bot.send_message(f"⚠️ 청산 미완료 ({rem} 종목 남음). 2분 뒤 재시도합니다.")
                
                # 4. Report (One-time)
                if t >= KR_CLOSE and not state['kr_report_sent']:
                    # Send Daily Report
                    report = trade_manager.get_daily_report("KR")
                    bot.send_message(report)
                    
                    # Run Auto-Optimization
                    from app.core.optimizer import optimizer
                    bot.send_message("🧠 AI 최적화 모듈 실행 중 (오늘 성과 기반)...")
                    res = optimizer.run_optimization("KR")
                    
                    if res:
                        reason = res.get('reason', 'N/A')
                        new_target = res.get('target_profit_rate')
                        new_stop = res.get('stop_loss_rate')
                        bot.send_message(f"🔧 내일 전략 최적화 완료:\n목표가: {new_target}%\n손절가: {new_stop}%\n이유: {reason}")
                    
                    state['kr_report_sent'] = True
                    logger.info("KR Session Ended & Strategy Optimized.")

            # === US Mode (22:00 ~ 06:00) ===
            elif is_time_in_range(US_START, dtime(6, 0), t):
                # Reset KR flags
                if state['kr_report_sent']:
                    state['kr_liquidation_done'] = False
                    state['kr_report_sent'] = False
                    state['kr_market_closed'] = False # Reset KR Breaker

                # Check Market Open (Weekend/Holiday)
                is_open, reason = check_market_open("US")
                if not is_open:
                     if now.minute == 0 and now.second < 5:
                         logger.info(f"US Market Check: Closed ({reason}). Sleeping...")
                     await asyncio.sleep(1)
                     continue

                # 1. Scanning
                time_since = (now - state['last_scan_time']).total_seconds() / 60
                is_scan_time = (
                    is_time_in_range(US_SCAN_START, dtime(4, 0), t) and
                    time_since >= SCAN_INTERVAL
                )
                
                if is_scan_time:
                    open_slots = MAX_TRADES - len([k for k,v in trade_manager.active_trades.items() if v.get('market_type')=='US'])
                    if open_slots > 0:
                        # Check Budget (Target Slot Budget)
                        budget = trade_manager.get_target_slot_budget_us()
                        if budget < 20:
                             logger.info(f"Skip Scanning: Insufficient USD for Next Slot ({budget:.2f})")
                        else:
                            bot.send_message(f"🇺🇸 미국장 스캔 중... ({open_slots} 슬롯, 목표 예산: ${budget:.2f})")
                            # US Selection
                            candidates = await selector.select_us_stocks(budget)
                            state['last_scan_time'] = now
                            if candidates:
                                trade_manager.process_signals(candidates)

                # 2. Monitoring
                if is_time_in_range(US_TRADE_START, US_LIQUIDATION, t):
                    trade_manager.monitor_active_trades("US")
                    
                    # AI Risk Check (Every 10 mins)
                    risk_time_since = (now - state['last_risk_check_time']).total_seconds() / 60
                    if risk_time_since >= 10:
                         trade_manager.monitor_risks("US")
                         state['last_risk_check_time'] = now
                
                # 3. Liquidation (Retry Logic)
                # Tried at 05:40. If failing, retry every 2 mins until 06:00.
                if is_time_in_range(US_LIQUIDATION, US_CLOSE, t):
                    if not state['us_liquidation_done']:
                        # Check Retry Interval (2 mins)
                        last_try = state.get('last_liquidation_try_time', datetime.min)
                        time_since_try = (now - last_try).total_seconds()
                        
                        if time_since_try >= 120:
                            bot.send_message("⏰ 미국장 마감 임박. 보유 종목 전량 청산 시도...")
                            rem = trade_manager.liquidate_all_positions("US")
                            state['last_liquidation_try_time'] = now
                            
                            if rem == 0:
                                state['us_liquidation_done'] = True
                                bot.send_message("✅ 미국장 청산 완료.")
                            else:
                                bot.send_message(f"⚠️ 청산 미완료 ({rem} 종목 남음). 2분 뒤 재시도합니다.")

                # 4. Report
                # Send report just before session close (05:50 ~ 06:00)
                if is_time_in_range(dtime(5, 50), US_CLOSE, t) and not state['us_report_sent']:
                    report = trade_manager.get_daily_report("US")
                    bot.send_message(report)
                    
                    # Run Auto-Optimization
                    from app.core.optimizer import optimizer
                    bot.send_message("🧠 AI 최적화 모듈 실행 중 (미국장 성과 기반)...")
                    res = optimizer.run_optimization("US")
                    
                    if res:
                        reason = res.get('reason', 'N/A')
                        new_target = res.get('target_profit_rate')
                        new_stop = res.get('stop_loss_rate')
                        bot.send_message(f"🔧 내일 미장 전략 최적화 완료:\n목표가: {new_target}%\n손절가: {new_stop}%\n이유: {reason}")
                    
                    state['us_report_sent'] = True
                    logger.info("US Session Ended & Strategy Optimized.")
            
            else:
                # Sleep Period
                pass
            
            await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Stopped by user.")
            break
        except Exception as e:
            # Circuit Breaker Logic
            err_msg = str(e)
            if "장운영" in err_msg or "휴장" in err_msg or "Closed" in err_msg or "market is closed" in err_msg:
                now = datetime.now()
                t = now.time()
                # Determine which market we are in
                if is_time_in_range(KR_START, dtime(15, 40), t):
                    state['kr_market_closed'] = True
                    bot.send_message(f"⛔ 국장 휴일/장운영 종료 감지: {err_msg}. 오늘은 매매를 중단합니다.")
                elif is_time_in_range(US_START, dtime(6, 0), t):
                    state['us_market_closed'] = True
                    bot.send_message(f"⛔ 미장 휴일/장운영 종료 감지: {err_msg}. 오늘은 매매를 중단합니다.")
            
            logger.error(f"Error in Main Loop: {e}", exc_info=True)
            try:
                bot.send_message(f"🚨 System Error (Auto-Recovering): {e}")
            except: 
                pass
            await asyncio.sleep(60)

async def main():
    # Setup Web Server
    config = uvicorn.Config(web_app, host="0.0.0.0", port=8000, log_level="warning")
    server = uvicorn.Server(config)

    # Run both Trading Loop and Web Server concurrently
    await asyncio.gather(
        server.serve(),
        trading_loop()
    )

if __name__ == "__main__":
    asyncio.run(main())
