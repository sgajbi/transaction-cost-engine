# src/api/main.py

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import uvicorn
import logging

from src.api.v1 import transactions # Import our API router
from src.core.config.settings import settings # Corrected import path

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(settings.APP_NAME)

# Create FastAPI app instance
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG_MODE,
    description="API for processing and calculating costs of financial transactions using FIFO method." [cite: 57]
)

# Include API routers
app.include_router(transactions.router, prefix=settings.API_V1_STR, tags=["Transactions"])

@app.get("/", include_in_schema=False)
async def root():
    """Redirects to the API documentation."""
    return RedirectResponse(url="/docs")

# Entry point for running with Uvicorn directly (for development)
if __name__ == "__main__":
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} in {'DEBUG' if settings.DEBUG_MODE else 'PRODUCTION'} mode...")
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG_MODE, # Reloads on code changes if DEBUG_MODE is True [cite: 58]
        log_level=settings.LOG_LEVEL.lower()
    )