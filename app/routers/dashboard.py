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
async def trigger_selection(background_tasks: BackgroundTasks, market: str = "KR", type: str = "scan"):
    global is_running
    if is_running:
        return {"message": "Selection already in progress"}
    
    is_running = True
    background_tasks.add_task(run_selection_task, market, type)
    return {"message": f"{market} {type} started in background"}

async def run_selection_task(market: str, task_type: str):
    global latest_selection, is_running
    try:
        if task_type == "top10":
            logger.info(f"Running Top 10 selection for {market}...")
            # This returns list, but we might want to store it somewhere or just run it?
            # select_pre_market_picks saves to json.
            await selector.select_pre_market_picks(market, force=True)
        else:
            logger.info(f"Running manual scan for {market}...")
            if market == "US":
                # Budget check needed? Default to something safe or 0
                await selector.select_us_stocks() 
            else:
                await selector.select_stocks()
                
        logger.info(f"{market} {task_type} complete.")
    except Exception as e:
        logger.error(f"Selection failed: {e}")
    finally:
        is_running = False
