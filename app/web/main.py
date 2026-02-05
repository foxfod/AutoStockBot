from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import logging
import asyncio
import json
from pathlib import Path

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

# Global Shared State (will be injected from main_auto_trade.py)
# This includes the Log Queue and Bot State
server_context = {
    "log_queue": None, # asyncio.Queue
    "bot_state": None, # dict
    "trade_manager": None # TradeManager Instance
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

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/api/state")
async def get_state():
    """Returns the current bot state and active trades"""
    if not server_context["bot_state"] or not server_context["trade_manager"]:
        return {"status": "loading"}
    
    tm = server_context["trade_manager"]
    
    # Safely get budget
    kr_budget = tm.get_available_budget("KR")
    us_budget = tm.get_target_slot_budget_us() # Approximate
    
    # Enrich active trades with real-time data
    from app.core.kis_api import kis
    enriched_trades = {}
    
    # Helper for safe float
    def safe_float(v):
        try: return float(v)
        except: return 0.0

    if tm.active_trades:
        for symbol, trade in tm.active_trades.items():
            trade_data = trade.copy() # Shallow copy to avoid mutating original state logic if not needed
            
            market_type = trade.get('market_type', 'KR')
            
            # Fetch Price
            # This uses WebSocket cache if available, so it's fast
            price_info = kis.get_realtime_price(symbol, market_type)
            
            current_price = 0
            if price_info:
                current_price = safe_float(price_info.get('price', 0))
            
            # Fallback if price is 0 (maybe market closed or no data)
            if current_price == 0:
                 # Use buy_price as fallback to avoid division by zero or scary -100%
                 current_price = trade.get('buy_price', 0)

            trade_data['current_price'] = current_price
            
            buy_price = safe_float(trade.get('buy_price', 0))
            if buy_price > 0:
                trade_data['profit_rate'] = ((current_price - buy_price) / buy_price) * 100
            else:
                trade_data['profit_rate'] = 0.0
                
            enriched_trades[symbol] = trade_data
    
    return {
        "bot_state": server_context["bot_state"],
        "is_paused": server_context.get("is_paused", False),
        "kr_budget": kr_budget,
        "us_budget": us_budget,
        "active_trades": enriched_trades,
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# === Control Endpoints ===
import os
import sys

@app.post("/api/control/pause")
async def pause_bot():
    server_context["is_paused"] = True
    return {"status": "paused", "message": "Trading logic paused"}

@app.post("/api/control/resume")
async def resume_bot():
    server_context["is_paused"] = False
    return {"status": "running", "message": "Trading logic resumed"}

@app.post("/api/control/restart")
async def restart_bot():
    """Restarts the entire python process"""
    # This might be abrupt, but effective.
    # We should probably run this in a background task to allow response to return.
    asyncio.create_task(do_restart())
    return {"status": "restarting", "message": "Server is restarting..."}

@app.post("/api/control/shutdown")
async def shutdown_bot():
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
    await manager.connect(websocket)
    try:
        while True:
            # Check queue for new logs
            if server_context["log_queue"]:
                while not server_context["log_queue"].empty():
                    log_data = await server_context["log_queue"].get()
                    await websocket.send_json({"type": "log", "data": log_data})
            
            # Send periodic state update?
            # Or client polls state? Let's just do logs here mostly for now.
            # But we can also push state updates if we want real-time.
            
            # Simple heartbeat or wait
            await asyncio.sleep(0.1) 
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WS Error: {e}")
        manager.disconnect(websocket)

from datetime import datetime
