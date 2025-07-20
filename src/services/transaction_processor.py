# src/services/transaction_processor.py

import logging
from typing import Tuple, List, Any
from src.core.models.transaction import Transaction
from src.core.models.response import ErroredTransaction
from src.logic.parser import TransactionParser
from src.logic.sorter import TransactionSorter
from src.logic.disposition_engine import DispositionEngine
from src.logic.cost_calculator import CostCalculator
from src.logic.error_reporter import ErrorReporter
from src.core.enums.transaction_type import TransactionType
from decimal import Decimal # NEW: Import Decimal

logger = logging.getLogger(__name__)

class TransactionProcessor:
    """
    Orchestrates the end-to-end processing of financial transactions.
    It combines parsing, sorting, cost calculation, and error reporting.
    """
    def __init__(
        self,
        parser: TransactionParser,
        sorter: TransactionSorter,
        disposition_engine: DispositionEngine,
        cost_calculator: CostCalculator,
        error_reporter: ErrorReporter
    ):
        self._parser = parser
        self._sorter = sorter
        self._disposition_engine = disposition_engine
        self._cost_calculator = cost_calculator
        self._error_reporter = error_reporter

    def process_transactions(
        self,
        existing_transactions_raw: list[dict[str, Any]],
        new_transactions_raw: list[dict[str, Any]]
    ) -> Tuple[list[Transaction], list[ErroredTransaction]]:
        """
        Main method to process both existing and new financial transactions,
        merging, sorting, calculating costs, and reporting errors.
        """
        logger.info(f"Starting transaction processing. Existing: {len(existing_transactions_raw)}, New: {len(new_transactions_raw)}")

        self._error_reporter.clear() 

        # 1. Parse existing transactions
        parsed_existing_transactions = self._parser.parse_transactions(existing_transactions_raw)
        logger.debug(f"Parsed {len(parsed_existing_transactions)} existing transactions. Errors reported to central reporter.")

        # 2. Parse new transactions
        parsed_new_transactions = self._parser.parse_transactions(new_transactions_raw)
        logger.debug(f"Parsed {len(parsed_new_transactions)} new transactions. Errors reported to central reporter.")

        # Identify which transaction_ids belong to the new set for final filtering
        new_transaction_ids = {txn.transaction_id for txn in parsed_new_transactions}
        existing_transaction_ids = {txn.transaction_id for txn in parsed_existing_transactions}

        # Filter out transactions that already have a parsing error before sorting and processing
        sortable_existing_transactions = [txn for txn in parsed_existing_transactions if not txn.error_reason]
        sortable_new_transactions = [txn for txn in parsed_new_transactions if not txn.error_reason]

        # 3. Sort all transactions chronologically (merging and sorting all into a single sequence)
        sorted_transactions = self._sorter.sort_transactions(
            existing_transactions=sortable_existing_transactions,
            new_transactions=sortable_new_transactions
        )
        logger.debug(f"Sorted {len(sorted_transactions)} transactions (combined existing and new).")

        # 4. Initialize disposition engine with existing, successfully parsed BUY transactions
        # This extracts only the existing BUYs from the globally sorted list.
        initial_buy_lots_for_disposition_engine = [
            txn for txn in sorted_transactions 
            if txn.transaction_id in existing_transaction_ids 
            and txn.transaction_type == TransactionType.BUY 
            and txn.quantity > Decimal(0) 
        ]
        self._disposition_engine.set_initial_lots(initial_buy_lots_for_disposition_engine)
        logger.debug(f"Disposition engine initialized with existing BUY lots: {[txn.transaction_id for txn in initial_buy_lots_for_disposition_engine]}.")

        processed_transactions: list[Transaction] = [] 
        
        # 5. Process all sorted transactions
        for transaction in sorted_transactions:
            if transaction.error_reason:
                continue 

            # Only calculate costs for NEW transactions.
            # Existing BUYs are handled by initial_lots. Other existing types (SELL, DIVIDEND) are assumed pre-processed.
            if transaction.transaction_id in new_transaction_ids:
                try:
                    self._cost_calculator.calculate_transaction_costs(transaction)

                    if self._error_reporter.has_errors_for(transaction.transaction_id):
                        pass 
                    else:
                        processed_transactions.append(transaction)
                except Exception as e:
                    logger.error(f"Unexpected error during cost calculation for transaction {transaction.transaction_id}: {e}")
                    transaction.error_reason = f"Unexpected processing error: {type(e).__name__}: {str(e)}"
                    self._error_reporter.add_error(transaction.transaction_id, transaction.error_reason) 

        final_errored_transactions = self._error_reporter.get_errors()

        final_processed_new_transactions = [
            txn for txn in processed_transactions
            if txn.transaction_id in new_transaction_ids and not self._error_reporter.has_errors_for(txn.transaction_id)
        ]
        logger.info(f"Finished processing. Successfully processed {len(final_processed_new_transactions)} new transactions, {len(final_errored_transactions)} total errors reported.")

        return final_processed_new_transactions, final_errored_transactions