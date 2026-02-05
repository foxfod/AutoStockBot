from fastapi import FastAPI
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
import uvicorn
import logging
from app.core.config import settings
from app.routers import dashboard

# Setup Logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Scheduler Setup
scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up Scalping Stock Selector...")
    
    # Schedule Job: Run selection at 08:30 AM KST (UTC+9) every weekday
    # Note: Server time depends on system time. Ensure system is KST.
    scheduler.add_job(
        dashboard.run_selection_task, 
        'cron', 
        hour=8, 
        minute=30, 
        day_of_week='mon-fri',
        id='daily_selection'
    )
    
    scheduler.start()
    yield
    # Shutdown
    logger.info("Shutting down...")
    scheduler.shutdown()

app = FastAPI(title="Scalping Stock Selector", lifespan=lifespan)
app.include_router(dashboard.router)

@app.get("/health")
def health_check():
    return {"status": "active"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
