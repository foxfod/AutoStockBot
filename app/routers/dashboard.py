from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.core.selector import selector
import logging

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

# Verify this in-memory storage for MVP, later use DB
latest_selection = []
is_running = False

@router.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stocks": latest_selection
    })

@router.get("/status")
async def get_status():
    global is_running
    return {"running": is_running, "count": len(latest_selection)}

@router.post("/run-selection")
async def trigger_selection(background_tasks: BackgroundTasks):
    global is_running
    if is_running:
        return {"message": "Selection already in progress"}
    
    is_running = True
    background_tasks.add_task(run_selection_task)
    return {"message": "Selection started in background"}

async def run_selection_task():
    global latest_selection, is_running
    logger.info("Running manual selection...")
    try:
        # Now awaiting the async selector
        latest_selection = await selector.select_stocks()
        logger.info("Manual selection complete.")
    except Exception as e:
        logger.error(f"Selection failed: {e}")
    finally:
        is_running = False
