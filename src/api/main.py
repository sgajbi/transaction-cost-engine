# src/api/main.py

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import uvicorn
import logging

# NEW: Import the consolidated v1 router
from src.api.v1.router import router as v1_router # Corrected import for v1 router
from src.core.config.settings import settings # Import our application settings

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(settings.APP_NAME)

# Create FastAPI app instance
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG_MODE,
    description="API for processing and calculating costs of financial transactions using FIFO method."
)

# Include API routers
# OLD: app.include_router(transactions.router, prefix=settings.API_V1_STR, tags=["Transactions"])
app.include_router(v1_router, prefix=settings.API_V1_STR) # NEW: Include the consolidated v1 router without redundant tags

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
        reload=settings.DEBUG_MODE,
        log_level=settings.LOG_LEVEL.lower()
    )