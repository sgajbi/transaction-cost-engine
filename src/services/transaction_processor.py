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

logger = logging.getLogger(__name__)

class TransactionProcessor:
    """
    Orchestrates the end-to-end processing of financial transactions.
    It combines parsing, sorting, cost calculation, and error reporting.
    """
    def __init__(
        self,
        parser: TransactionParser, # This parser is now created outside and passed in
        sorter: TransactionSorter,
        disposition_engine: DispositionEngine,
        cost_calculator: CostCalculator,
        error_reporter: ErrorReporter
    ):
        # Dependency Injection: All core logic components are injected
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

        # NEW: Clear the error reporter at the very beginning of processing for a new request
        self._error_reporter.clear() 

        # 1. Parse existing transactions
        # Parser now reports errors directly to self._error_reporter and marks Transaction.error_reason
        parsed_existing_transactions = self._parser.parse_transactions(existing_transactions_raw)
        # REMOVED: all_errored_transactions.extend(existing_parsing_errors) - no longer needed here
        logger.debug(f"Parsed {len(parsed_existing_transactions)} existing transactions. Errors reported to central reporter.")

        # 2. Parse new transactions
        parsed_new_transactions = self._parser.parse_transactions(new_transactions_raw)
        # REMOVED: all_errored_transactions.extend(new_parsing_errors) - no longer needed here
        logger.debug(f"Parsed {len(parsed_new_transactions)} new transactions. Errors reported to central reporter.")

        # Identify which transaction_ids belong to the new set for final filtering
        new_transaction_ids = {txn.transaction_id for txn in parsed_new_transactions}

        # Filter out transactions that already have a parsing error before sorting and processing
        # This relies on TransactionParser setting transaction.error_reason for parsing failures.
        sortable_existing_transactions = [txn for txn in parsed_existing_transactions if not txn.error_reason]
        sortable_new_transactions = [txn for txn in parsed_new_transactions if not txn.error_reason]

        # 3. Sort all transactions chronologically (delegating merging and sorting to sorter)
        sorted_transactions = self._sorter.sort_transactions(
            existing_transactions=sortable_existing_transactions,
            new_transactions=sortable_new_transactions
        )
        logger.debug(f"Sorted {len(sorted_transactions)} transactions (combined existing and new).")

        # 4. Initialize disposition engine with existing, successfully parsed BUY transactions
        self._disposition_engine.set_initial_lots(sortable_existing_transactions)
        logger.debug(f"Disposition engine initialized with existing BUY lots.")

        processed_transactions: list[Transaction] = [] # To store successfully processed transactions
        
        # 5. Process all sorted transactions
        for transaction in sorted_transactions:
            # If a transaction already has an error (e.g., from initial parsing), skip processing it.
            # The error is already in the central reporter from the parser.
            if transaction.error_reason: # This check relies on parser setting transaction.error_reason for internal filtering
                continue 

            # CRITICAL FIX: Only calculate costs for NEW transactions.
            # Existing transactions are only used to initialize the disposition engine's state.
            if transaction.transaction_id in new_transaction_ids:
                try:
                    # The CostCalculator determines the strategy and updates the transaction object in-place.
                    # CostCalculator uses self._error_reporter for its errors.
                    self._cost_calculator.calculate_transaction_costs(transaction)

                    # After cost calculation, check if an error was reported for this transaction.
                    # If an error was reported, this transaction will NOT be appended to processed_transactions,
                    # and will instead be picked up by final_errored_transactions.
                    if self._error_reporter.has_errors_for(transaction.transaction_id):
                        pass # Error is in reporter, will be picked up later
                    else:
                        processed_transactions.append(transaction)
                except Exception as e:
                    logger.error(f"Unexpected error during cost calculation for transaction {transaction.transaction_id}: {e}")
                    # For unexpected runtime errors during cost calculation, ensure the transaction is marked 
                    # and the error is reported to the central reporter.
                    transaction.error_reason = f"Unexpected processing error: {type(e).__name__}: {str(e)}"
                    self._error_reporter.add_error(transaction.transaction_id, transaction.error_reason) 
            # ELSE: If it's an existing transaction (not a new one) AND not errored from parsing,
            # it has already been handled by disposition_engine.set_initial_lots.
            # No need to add to processed_transactions output as per problem statement for new transactions.


        # 6. Collect all errors reported during parsing AND processing (now all from _error_reporter)
        final_errored_transactions = self._error_reporter.get_errors()

        # 7. Filter processed transactions to return only those corresponding to the *new* input transactions.
        # This also ensures transactions that *were* processed but then had a subsequent error (e.g., from cost calculator)
        # are not included in the 'processed_transactions' output.
        final_processed_new_transactions = [
            txn for txn in processed_transactions
            if txn.transaction_id in new_transaction_ids and not self._error_reporter.has_errors_for(txn.transaction_id)
        ]
        logger.info(f"Finished processing. Successfully processed {len(final_processed_new_transactions)} new transactions, {len(final_errored_transactions)} total errors reported.")

        return final_processed_new_transactions, final_errored_transactions