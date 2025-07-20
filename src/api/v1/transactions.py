# src/api/v1/transactions.py

from fastapi import APIRouter, Depends, HTTPException, status
from src.core.models.request import TransactionProcessingRequest
from src.core.models.response import TransactionProcessingResponse
from src.services.transaction_processor import TransactionProcessor
from src.logic.parser import TransactionParser # Keep this import
from src.logic.sorter import TransactionSorter
from src.logic.disposition_engine import DispositionEngine
from src.logic.cost_calculator import CostCalculator
from src.logic.error_reporter import ErrorReporter # Keep this import
# NEW IMPORTS for configurable cost method
from src.core.config.settings import settings
from src.core.enums.cost_method import CostMethod
from src.logic.cost_basis_strategies import FIFOBasisStrategy, AverageCostBasisStrategy, CostBasisStrategy

router = APIRouter()

# Dependency for TransactionProcessor and its components
def get_transaction_processor() -> TransactionProcessor:
    """
    Provides a new instance of TransactionProcessor with its dependencies,
    configured with the selected cost basis method.
    """
    error_reporter = ErrorReporter() # Create the error reporter here

    # Determine which cost basis strategy to use based on configuration
    chosen_cost_basis_strategy: CostBasisStrategy
    if settings.COST_BASIS_METHOD == CostMethod.FIFO:
        chosen_cost_basis_strategy = FIFOBasisStrategy()
    elif settings.COST_BASIS_METHOD == CostMethod.AVERAGE_COST:
        chosen_cost_basis_strategy = AverageCostBasisStrategy()
    else:
        # This case should ideally not be reached if CostMethod enum is exhaustive
        raise ValueError(f"Unknown COST_BASIS_METHOD: {settings.COST_BASIS_METHOD}")

    # Initialize DispositionEngine with the chosen strategy
    disposition_engine = DispositionEngine(cost_basis_strategy=chosen_cost_basis_strategy)

    cost_calculator = CostCalculator(
        disposition_engine=disposition_engine,
        error_reporter=error_reporter
    )
    
    # MODIFIED: Pass the error_reporter instance to the TransactionProcessor constructor
    # The TransactionProcessor then passes it down to the TransactionParser it creates internally.
    return TransactionProcessor(
        parser=TransactionParser(error_reporter=error_reporter), # FIX: Pass error_reporter here
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