import logging
import asyncio
from datetime import datetime

class AsyncQueueHandler(logging.Handler):
    """
    Validation logger handler that puts logs into an asyncio.Queue
    to be consumed by WebSocket broadcasting.
    """
    def __init__(self, queue: asyncio.Queue):
        super().__init__()
        self.queue = queue
        
    def emit(self, record):
        try:
            log_entry = self.format(record)
            # Use loop.call_soon_threadsafe if we might be calling from different threads,
            # but since everything is main loop for now, we can try put_nowait 
            # or better, just check loop running.
            
            # Simple struct for JSON
            log_data = {
                "timestamp": datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S'),
                "level": record.levelname,
                "message": record.getMessage(),
                "logger": record.name
            }
            
            try:
                self.queue.put_nowait(log_data)
            except asyncio.QueueFull:
                pass # Drop logs if queue is full or error
        except Exception:
            self.handleError(record)
