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

router = APIRouter()

# Dependency for TransactionProcessor and its components
# This function will be called by FastAPI's dependency injection system
# for each request, ensuring a fresh instance for stateless processing.
def get_transaction_processor() -> TransactionProcessor:
    """
    Provides a new instance of TransactionProcessor with its dependencies.
    """
    error_reporter = ErrorReporter()
    disposition_engine = DispositionEngine()
    cost_calculator = CostCalculator(
        disposition_engine=disposition_engine,
        error_reporter=error_reporter
    )
    return TransactionProcessor(
        parser=TransactionParser(),
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
                "using FIFO, and returns processed and errored transactions."
)
async def process_transactions_endpoint(
    request: TransactionProcessingRequest,
    processor: TransactionProcessor = Depends(get_transaction_processor)
) -> TransactionProcessingResponse:
    """
    API endpoint to process financial transactions.
    """
    processed, errored = processor.process_transactions(
        existing_transactions_raw=request.existing_transactions,
        new_transactions_raw=request.new_transactions
    )
    return TransactionProcessingResponse(
        processed_transactions=processed,
        errored_transactions=errored
    )