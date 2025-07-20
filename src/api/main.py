# src/api/main.py

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import uvicorn
import logging
from decimal import Decimal, getcontext # Import Decimal as well
from json import JSONEncoder # NEW: For custom JSON encoding

from src.api.v1.router import router as v1_router
from src.core.config.settings import settings

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(settings.APP_NAME)

# Set global Decimal precision at application startup
getcontext().prec = settings.DECIMAL_PRECISION

# NEW: Custom JSON encoder to handle Decimal objects
# This ensures Decimal objects are serialized as strings in FastAPI's responses.
# Pydantic (on the receiving end of the test) will then deserialize these strings back to Decimal.
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return json.JSONEncoder.default(self, obj)

# Create FastAPI app instance
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG_MODE,
    description="API for processing and calculating costs of financial transactions using FIFO method."
)

# Apply custom JSON encoder to FastAPI
# This requires overriding FastAPI's default json_encoder
app.json_encoder = DecimalEncoder # NEW: Apply custom Decimal encoder

# Include API routers
app.include_router(v1_router, prefix=settings.API_V1_STR)

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