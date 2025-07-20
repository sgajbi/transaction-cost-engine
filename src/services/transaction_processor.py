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
        parser: TransactionParser,
        sorter: TransactionSorter,
        disposition_engine: DispositionEngine,
        cost_calculator: CostCalculator,
        error_reporter: ErrorReporter
    ):
        # Dependency Injection: All core logic components are injected
        # MODIFIED: Pass error_reporter to TransactionParser
        self._parser = TransactionParser(error_reporter=error_reporter) # Pass the error reporter
        self._sorter = sorter
        self._disposition_engine = disposition_engine
        self._cost_calculator = cost_calculator
        self._error_reporter = error_reporter # Keep storing it here for overall orchestration

    def process_transactions(
        self,
        existing_transactions_raw: list[dict[str, Any]],
        new_transactions_raw: list[dict[str, Any]]
    ) -> Tuple[list[Transaction], list[ErroredTransaction]]:
        """
        Main method to process both existing and new financial transactions,
        merging, sorting, calculating costs, and reporting errors.
        """
        all_errored_transactions: list[ErroredTransaction] = []
        
        logger.info(f"Starting transaction processing. Existing: {len(existing_transactions_raw)}, New: {len(new_transactions_raw)}")

        # 1. Parse existing transactions
        # MODIFIED: Pass error_reporter to parser (already done in __init__ for the instance)
        parsed_existing_transactions, existing_parsing_errors = self._parser.parse_transactions(existing_transactions_raw)
        all_errored_transactions.extend(existing_parsing_errors)
        logger.debug(f"Parsed {len(parsed_existing_transactions)} existing transactions with {len(existing_parsing_errors)} errors.")

        # 2. Parse new transactions
        # MODIFIED: Pass error_reporter to parser (already done in __init__ for the instance)
        parsed_new_transactions, new_parsing_errors = self._parser.parse_transactions(new_transactions_raw)
        all_errored_transactions.extend(new_parsing_errors)
        logger.debug(f"Parsed {len(parsed_new_transactions)} new transactions with {len(new_parsing_errors)} errors.")

        # Identify which transaction_ids belong to the new set for final filtering
        new_transaction_ids = {txn.transaction_id for txn in parsed_new_transactions}

        # Filter out transactions that already have a parsing error before sorting and processing
        # This currently relies on txn.error_reason being set by the parser. This will need adjustment in the next step.
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
            # If a transaction already has an error (e.g., from initial parsing), ensure it's reported and skip.
            # This check will need refinement once parser always uses ErrorReporter.
            if transaction.error_reason:
                self._error_reporter.add_error(transaction.transaction_id, transaction.error_reason)
                continue

            # CRITICAL FIX: Only calculate costs for NEW transactions.
            # Existing transactions are only used to initialize the disposition engine's state.
            if transaction.transaction_id in new_transaction_ids:
                try:
                    # The CostCalculator determines the strategy and updates the transaction object in-place.
                    self._cost_calculator.calculate_transaction_costs(transaction)

                    # After cost calculation, check if any new error was added to the transaction
                    # This also needs to be refined, potentially checking error_reporter directly.
                    if transaction.error_reason: # This check relies on error_reason being set elsewhere (e.g., by parser)
                        self._error_reporter.add_error(transaction.transaction_id, transaction.error_reason)
                    else:
                        processed_transactions.append(transaction)
                except Exception as e:
                    logger.error(f"Unexpected error during cost calculation for transaction {transaction.transaction_id}: {e}")
                    # Mark the transaction with an error and add it to the reporter
                    transaction.error_reason = f"Unexpected processing error: {type(e).__name__}: {str(e)}"
                    self._error_reporter.add_error(transaction.transaction_id, transaction.error_reason)
            else:
                pass


        # 6. Collect all errors reported during parsing and processing
        final_errored_transactions = self._error_reporter.get_errors()

        # 7. Filter processed transactions to return only those corresponding to the *new* input transactions
        final_processed_new_transactions = [
            txn for txn in processed_transactions
            if txn.transaction_id in new_transaction_ids
        ]
        logger.info(f"Finished processing. Successfully processed {len(final_processed_new_transactions)} new transactions, {len(final_errored_transactions)} total errors reported.")

        return final_processed_new_transactions, final_errored_transactions