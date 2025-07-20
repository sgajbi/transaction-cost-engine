# src/api/v1/router.py

from fastapi import APIRouter
from src.api.v1.transactions import router as transactions_router

# Create a main router for API version 1
router = APIRouter()

# Include individual routers for v1 endpoints, applying tags here for clarity
router.include_router(transactions_router, tags=["Transactions"])