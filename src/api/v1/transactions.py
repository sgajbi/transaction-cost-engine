# src/api/v1/transactions.py

from fastapi import APIRouter, Depends, HTTPException, status
from src.core.models.request import TransactionProcessingRequest
from src.core.models.response import TransactionProcessingResponse
from src.services.transaction_processor import TransactionProcessor
from src.logic.parser import TransactionParser
from src.logic.sorter import TransactionSorter
from src.logic.disposition_engine import DispositionEngine
from src.logic.cost_calculator import CostCalculator
from src.logic.error_reporter import ErrorReporter
from src.core.config.settings import Settings as AppSettingsClass # NEW: Import the Settings class
from src.core.enums.cost_method import CostMethod
from src.logic.cost_basis_strategies import FIFOBasisStrategy, AverageCostBasisStrategy, CostBasisStrategy
from decimal import Decimal # Ensure Decimal is imported for type checks

import logging # NEW: Import logging for local logger
logger = logging.getLogger(__name__) # NEW: Initialize local logger

router = APIRouter()

# Dependency for TransactionProcessor and its components
def get_transaction_processor() -> TransactionProcessor:
    """
    Provides a new instance of TransactionProcessor with its dependencies,
    configured with the selected cost basis method.
    """
    # NEW: Create a fresh settings instance to ensure env vars are re-read for each test run
    local_settings = AppSettingsClass() 
    logger.debug(f"API Dependency: Using COST_BASIS_METHOD: {local_settings.COST_BASIS_METHOD}") # NEW LOG

    error_reporter = ErrorReporter()

    # Determine which cost basis strategy to use based on configuration
    chosen_cost_basis_strategy: CostBasisStrategy
    if local_settings.COST_BASIS_METHOD == CostMethod.FIFO:
        chosen_cost_basis_strategy = FIFOBasisStrategy()
    elif local_settings.COST_BASIS_METHOD == CostMethod.AVERAGE_COST:
        chosen_cost_basis_strategy = AverageCostBasisStrategy()
    else:
        raise ValueError(f"Unknown COST_BASIS_METHOD: {local_settings.COST_BASIS_METHOD}")

    disposition_engine = DispositionEngine(cost_basis_strategy=chosen_cost_basis_strategy)

    cost_calculator = CostCalculator(
        disposition_engine=disposition_engine,
        error_reporter=error_reporter
    )
    
    return TransactionProcessor(
        parser=TransactionParser(error_reporter=error_reporter),
        sorter=TransactionSorter(),
        disposition_engine=disposition_engine,
        cost_calculator=cost_calculator,
        error_reporter=error_reporter
    )

@router.post(
    "/process",
    response_model=TransactionProcessingResponse,
    summary="Process financial transactions and calculate costs",
    description="Accepts new and existing transactions, merges, sorts, "
                "calculates net cost, gross cost, and realized gain/loss "
                "using the configured cost basis method (FIFO or Average Cost), "
                "and returns processed and errored transactions."
)
async def process_transactions_endpoint(
    request: TransactionProcessingRequest,
    processor: TransactionProcessor = Depends(get_transaction_processor)
) -> TransactionProcessingResponse:
    logger.debug(f"API: Received request: {request.model_dump_json(indent=2)}")
    processed, errored = processor.process_transactions(
        existing_transactions_raw=request.existing_transactions,
        new_transactions_raw=request.new_transactions
    )
    response_obj = TransactionProcessingResponse(processed_transactions=processed, errored_transactions=errored)
    logger.debug(f"API: Response object before serialization: {response_obj.model_dump_json(indent=2)}")
    return response_obj