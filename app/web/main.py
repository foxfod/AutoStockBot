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


@app.get("/api/state")
async def get_state(user=Depends(login_required)):
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
    
    def safe_float(v):
        try: return float(v)
        except: return 0.0

    if tm.active_trades:
        for symbol, trade in tm.active_trades.items():
            trade_data = trade.copy()
            market_type = trade.get('market_type', 'KR')
            price_info = kis.get_realtime_price(symbol, market_type)
            current_price = 0
            if price_info:
                current_price = safe_float(price_info.get('price', 0))
            if current_price == 0:
                 current_price = trade.get('buy_price', 0)

            trade_data['current_price'] = current_price
            
            qty = int(trade.get('qty', 0))
            trade_data['quantity'] = qty
            trade_data['value'] = current_price * qty

            buy_price = safe_float(trade.get('buy_price', 0))
            if buy_price > 0:
                trade_data['profit_rate'] = ((current_price - buy_price) / buy_price) * 100
                trade_data['profit_amount'] = (current_price - buy_price) * qty
            else:
                trade_data['profit_rate'] = 0.0
                trade_data['profit_amount'] = 0.0
                
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
    # WebSocket Auth Check (Optional but recommended)
    # Cookies are available in handshake
    token = websocket.cookies.get(COOKIE_NAME)
    if not token or token != "authenticated":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

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
