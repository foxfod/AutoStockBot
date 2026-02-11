from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Form, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import logging
import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from app.core.market_data import market_data_manager
from app.core.selector import selector

app = FastAPI(title="Scalping Bot Dashboard")

# Setup Paths
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Ensure directories exist
TEMPLATES_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# Mount Static
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Global Shared State
server_context = {
    "log_queue": None,
    "bot_state": None,
    "trade_manager": None,
    "is_paused": False
}

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# --- Authentication ---
WEB_PASSWORD = os.getenv("WEB_PASSWORD", "admin") # Default password
COOKIE_NAME = "access_token"

async def get_current_user(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token or token != "authenticated":
        return None
    return "user"

async def login_required(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": "/login"})
    return user

# --- Routes ---

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, password: str = Form(...)):
    if password == WEB_PASSWORD:
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key=COOKIE_NAME, value="authenticated", httponly=True)
        return response
    else:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid Password"})

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(COOKIE_NAME)
    return response

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request, user=Depends(login_required)):
    # If login_required fails, it raises HTTPException with 307 Redirect to /login
    # But Depends(login_required) doesn't catch the exception inside dependencies typically for redirects in this manner 
    # unless using an exception handler or specific logic.
    # Actually, for simple redirects in dependency, raising HTTPException with 307 works well in browsers.
    return templates.TemplateResponse("dashboard.html", {"request": request})

# Exception Handler for Redirect
from fastapi.responses import RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    if exc.status_code == 307:
        return RedirectResponse(url=exc.headers["Location"])
    return HTMLResponse(content=str(exc.detail), status_code=exc.status_code)


# Pydantic Models for Requests
class SlotConfig(BaseModel):
    market: str
    count: int

class TradeUpdate(BaseModel):
    target_price: Optional[float] = None
    stop_loss_price: Optional[float] = None

@app.post("/api/config/slots")
async def update_slots(config: SlotConfig, user=Depends(login_required)):
    if not server_context["trade_manager"]:
        raise HTTPException(status_code=503, detail="TradeManager not ready")
    
    server_context["trade_manager"].set_manual_slots(config.market, config.count)
    return {"status": "success", "message": f"Updated {config.market} slots to {config.count}"}

@app.post("/api/trade/{symbol}/sell")
async def sell_trade(symbol: str, market_type: str = "KR", user=Depends(login_required)):
    tm = server_context["trade_manager"]
    if not tm:
         raise HTTPException(status_code=503, detail="TradeManager not ready")
    
    result = tm.sell_position(symbol, market_type)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/api/trade/{symbol}/update")
async def update_trade(symbol: str, update: TradeUpdate, user=Depends(login_required)):
    tm = server_context["trade_manager"]
    if not tm:
         raise HTTPException(status_code=503, detail="TradeManager not ready")
    
    success = tm.update_trade_settings(symbol, update.target_price, update.stop_loss_price)
    if not success:
        raise HTTPException(status_code=404, detail="Trade not found")
    return {"status": "success", "message": "Trade settings updated"}

@app.post("/api/analyze/{symbol}")
async def analyze_trade(symbol: str, user=Depends(login_required)):
    tm = server_context["trade_manager"]
    if not tm or symbol not in tm.active_trades:
         raise HTTPException(status_code=404, detail="Trade not found")
    
    trade = tm.active_trades[symbol]
    market_type = trade.get('market_type', 'KR')
    excg = trade.get('excg', 'NAS')
    
    
    # 1. Fetch Real-time Data for Analysis
    from app.core.technical_analysis import technical
    from app.core.kis_api import kis
    from app.core.ai_analyzer import ai_analyzer
    
    # 1. Fetch Real-time Data
    step = "Init"
    tech_summary = {}
    news_list = []
    
    try:
        # Step 1: Price Data
        step = "Price Data"
        if market_type == 'US':
             raw_data = kis.get_overseas_daily_price(symbol, excg_cd=excg)
             daily_candles = []
             if raw_data:
                 for d in raw_data:
                     daily_candles.append({
                         "stck_bsop_date": d['xymd'],
                         "stck_clpr": d['clos'],
                         "stck_oprc": d['open'],
                         "stck_hgpr": d['high'],
                         "stck_lwpr": d['low'],
                         "acml_vol": d['tvol']
                     })
        else:
             daily_candles = kis.get_daily_price(symbol)

        if not daily_candles:
             return {"result": f"❌ 데이터 부족 ({step}) - KIS API 응답 없음"}
             
        # Step 2: Technical Analysis
        step = "Technical Analysis"
        tech_summary = technical.analyze(daily_candles)
        if "status" in tech_summary and tech_summary["status"] != "Success": 
            # If technical analysis returned error status, but check if it returned a dict at all
             if "close" not in tech_summary:
                return {"result": f"❌ 기술적 분석 실패: {tech_summary.get('status')}"}
        
        # Step 3: News
        step = "News Fetching"
        if market_type == 'US':
            raw_news = kis.get_overseas_news_titles(symbol)
            if raw_news:
                for n in raw_news:
                    if isinstance(n, dict):
                        news_list.append(n.get('title', n.get('hts_pbnt_titl_cntt', '')))
                    elif isinstance(n, str):
                        news_list.append(n)
                news_list = news_list[:3]
        else:
            raw_news = kis.get_news_titles(symbol)
            if raw_news:
                for n in raw_news:
                    news_list.append(n.get('hts_pbnt_titl_cntt', ''))
                news_list = news_list[:3]
        
        # Step 4: Construct Report
        step = "Report Generation"
        report = f"### 🔍 {symbol} ({market_type})\n"
        report += f"- 분석 시각: {time.strftime('%H:%M:%S')}\n\n"
        
        report += "#### 📈 기술적 지표\n"
        report += f"- 현재가: {tech_summary.get('close', 'N/A')}\n"
        report += f"- 추세: {tech_summary.get('trend', 'N/A')}\n"
        report += f"- RSI: {tech_summary.get('rsi', 'N/A')}\n\n"
        
        report += "#### 📰 관련 뉴스\n"
        if news_list:
            for n in news_list:
                report += f"- {n}\n"
        else:
            report += "- 관련 뉴스 없음\n"
        report += "\n"
        
        report += "#### 🤖 AI 종합 의견\n"
        
        # Step 5: AI Analysis
        step = "AI Analysis"
        # Check if we have enough data for AI
        if not tech_summary.get('close'):
            report += "- ⚠️ 기술적 데이터 부족으로 AI 분석 스킵.\n"
        else:
            ai_result = await ai_analyzer.analyze_stock(symbol, news_list, tech_summary)
            
            score = ai_result.get('score', 0)
            reason = ai_result.get('reason', '분석 불가')
            action = ai_result.get('action', 'N/A')
            
            report += f"- **점수**: {score}점 ({action})\n"
            report += f"- **판단**: {reason}\n"
            
            strategy = ai_result.get('strategy', {})
            if strategy:
                report += f"- **전략**: 목표 {strategy.get('target_price')}% / 손절 {strategy.get('stop_loss')}%\n"
            
        return {"result": report}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"result": f"❌ 시스템 오류 발생 ({step})\n- {str(e)}"}

# --- Top 10 Picks API ---
class TopPicksRequest(BaseModel):
    market: str = "KR"

@app.get("/api/top-picks")
async def get_top_picks(market: str = "KR", user=Depends(login_required)):
    """
    Get the persisted Top 10 picks.
    Optionally filter by market (check if the file matches the requested market).
    """
    try:
        file_path = "app/data/top_picks.json"
        if not os.path.exists(file_path):
            return {}
            
        with open(file_path, "r", encoding='utf-8') as f:
            data = json.load(f)
            
        # Check market match?
        # The user might want to see whatever is there, but strictly speaking 
        # if they ask for KR and we have US data, it's misleading.
        # Let's return what's in the file, but maybe frontend checks the 'market' field.
        # Actually, let's just return the file content and let frontend decide.
        
        return data
    except Exception as e:
        logging.error(f"Error reading top picks: {e}")
        return {}

@app.post("/api/top-picks/refresh")
async def refresh_top_picks(req: TopPicksRequest, user=Depends(login_required)):
    """
    Trigger a fresh analysis for Top 10.
    """
    try:
        # Prevent concurrent runs? selector.select_pre_market_picks might handle it or we assume user is careful.
        # It takes time, so we should probably run it and return, or wait?
        # User wants to see the result, so we await.
        
        picks = await selector.select_pre_market_picks(req.market, force=True)
        
        # Read the file again to return full structure or just return picks
        # select_pre_market_picks returns the list of dicts.
        
        # We construct the response to match file format
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "market": req.market,
            "picks": picks
        }
    except Exception as e:
        logging.error(f"Error refreshing top picks: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/state")
async def get_state(user=Depends(login_required)):
    """Returns the current bot state and active trades"""
    try:
        if not server_context["bot_state"] or not server_context["trade_manager"]:
            return {"status": "loading"}
        
        tm = server_context["trade_manager"]
        print(f"DEBUG: active_trades type: {type(tm.active_trades)}")
        if tm.active_trades:
             print(f"DEBUG: active_trades sample keys: {list(tm.active_trades.keys())}")
             first_val = next(iter(tm.active_trades.values()))
             print(f"DEBUG: active_trades first val type: {type(first_val)}")
             print(f"DEBUG: active_trades first val: {first_val}")

        # Safely get budget
        kr_budget = tm.get_available_budget("KR")
        us_budget = tm.get_target_slot_budget_us() # Approximate
        
    # Market Data
        market_info = await market_data_manager.get_market_data()
        if market_info is None: market_info = {}
        
        # Enrich active trades with real-time data
        from app.core.kis_api import kis
        enriched_trades = {}
        
        import math
        def safe_float(v):
            try: 
                val = float(v)
                if math.isnan(val) or math.isinf(val):
                    return 0.0
                return val
            except: return 0.0

        # Sanitize Market Info (Safe Copy)
        safe_market_info = {}
        for k, v in market_info.items():
            if isinstance(v, dict):
                safe_market_info[k] = {
                    sk: safe_float(sv) if isinstance(sv, (int, float, str)) else sv 
                    for sk, sv in v.items()
                }
            else:
                safe_market_info[k] = v
        market_info = safe_market_info

        if tm.active_trades:
            for symbol, trade in tm.active_trades.items():
                try:
                    trade_data = trade.copy()
                    market_type = trade.get('market_type', 'KR')
                    
                    try:
                        price_info = kis.get_realtime_price(symbol, market_type)
                    except Exception as e:
                        print(f"Error fetching price for {symbol}: {e}")
                        price_info = None

                    current_price = 0
                    if price_info:
                        current_price = safe_float(price_info.get('price', 0))
                    if current_price == 0:
                         current_price = safe_float(trade.get('buy_price', 0))

                    trade_data['current_price'] = current_price
                    
                    # Calculate Daily Change
                    prev_close = 0
                    if price_info:
                        prev_close = safe_float(price_info.get('prev_close', 0))
                    
                    if prev_close > 0:
                        trade_data['daily_change'] = ((current_price - prev_close) / prev_close) * 100
                    else:
                        trade_data['daily_change'] = 0.0

                    qty = int(trade.get('qty', 0))
                    trade_data['quantity'] = qty
                    trade_data['value'] = current_price * qty

                    buy_price = safe_float(trade.get('buy_price', 0))
                    
                    # --- KRW Conversion for US Stocks ---
                    if market_type == 'US':
                        # Fix: Get Exchange Rate from Market Info (Default 1450)
                        rate_info = market_info.get('usd_krw', {})
                        rate = float(rate_info.get('price', 1450.0))
                        
                        trade_data['current_price_krw'] = current_price * rate
                        trade_data['value_krw'] = (current_price * qty) * rate
                        trade_data['buy_price_krw'] = buy_price * rate
                    else:
                        trade_data['current_price_krw'] = current_price # Same for KR
                        trade_data['value_krw'] = current_price * qty
                        trade_data['buy_price_krw'] = buy_price

                    if buy_price > 0:
                        trade_data['profit_rate'] = ((current_price - buy_price) / buy_price) * 100
                        trade_data['profit_amount'] = (current_price - buy_price) * qty
                        
                        if market_type == 'US':
                            # Use the rate we fetched above
                            rate_info = market_info.get('usd_krw', {})
                            rate = float(rate_info.get('price', 1450.0))
                            trade_data['profit_amount_krw'] = trade_data['profit_amount'] * rate
                        else:
                            trade_data['profit_amount_krw'] = trade_data['profit_amount']
                    else:
                        trade_data['profit_rate'] = 0.0
                        trade_data['profit_amount'] = 0.0
                        trade_data['profit_amount_krw'] = 0.0
                        
                    enriched_trades[symbol] = trade_data
                except Exception as e:
                    print(f"Error processing trade {symbol}: {e}")
                    # Keep original data if processing failed
                    enriched_trades[symbol] = trade
        
        return {
            "status": "ok",
            "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": server_context.get("version", "Unknown"),
            "bot_state": server_context["bot_state"],
            "is_paused": server_context.get("is_paused", False),
            "kr_budget": safe_float(kr_budget),
            "us_budget": safe_float(us_budget),
            "active_trades": enriched_trades,
            "market_info": market_info,
            "manual_slots": tm.manual_slots,
            "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        # print(f"ERROR in get_state: {error_msg}") # Print to stdout for user to see
        logging.error(f"ERROR in get_state: {error_msg}")
        raise HTTPException(status_code=500, detail=str(e))

# === Control Endpoints ===

@app.post("/api/control/pause")
async def pause_bot(user=Depends(login_required)):
    server_context["is_paused"] = True
    return {"status": "paused", "message": "Trading logic paused"}

@app.post("/api/control/resume")
async def resume_bot(user=Depends(login_required)):
    server_context["is_paused"] = False
    return {"status": "running", "message": "Trading logic resumed"}

@app.post("/api/control/restart")
async def restart_bot(user=Depends(login_required)):
    """Restarts the entire python process"""
    asyncio.create_task(do_restart())
    return {"status": "restarting", "message": "Server is restarting..."}

@app.post("/api/control/shutdown")
async def shutdown_bot(user=Depends(login_required)):
    """Shuts down the python process"""
    asyncio.create_task(do_shutdown())
    return {"status": "shutting_down", "message": "Server is shutting down..."}

async def do_restart():
    await asyncio.sleep(1)
    os.execv(sys.executable, [sys.executable] + sys.argv)

async def do_shutdown():
    await asyncio.sleep(1)
    os._exit(0)

@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    # WebSocket Auth Check (Relaxed for debugging)
    # token = websocket.cookies.get(COOKIE_NAME)
    # print(f"DEBUG: WS Cookies: {websocket.cookies}")
    # if not token or token != "authenticated":
    #     print("DEBUG: WS Auth Failed")
    #     await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    #     return

    await manager.connect(websocket)
    import time
    last_heartbeat = time.time()
    
    try:
        while True:
            # Check queue for new logs
            if server_context["log_queue"]:
                while not server_context["log_queue"].empty():
                    log_data = await server_context["log_queue"].get()
                    await websocket.send_json({"type": "log", "data": log_data})
            
            # Heartbeat (Ping)
            now = time.time()
            if now - last_heartbeat > 30:
                try:
                    await websocket.send_json({"type": "ping"})
                    last_heartbeat = now
                except Exception:
                    break
            
            await asyncio.sleep(0.1) 
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WS Error: {e}")
        manager.disconnect(websocket)

from datetime import datetime
