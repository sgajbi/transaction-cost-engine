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
        Main method to process both existing and new financial transactions.

        Args:
            existing_transactions_raw: List of previously processed transactions (raw dicts).
            new_transactions_raw: List of new transactions to process (raw dicts).

        Returns:
            A tuple containing:
            - List of successfully processed Transaction objects with calculated costs.
            - List of ErroredTransaction objects for any failures.
        """
        logger.info(f"TransactionProcessor: Type of existing_transactions_raw received: {type(existing_transactions_raw)}")
        if existing_transactions_raw:
            logger.info(f"TransactionProcessor: Type of first item in existing_transactions_raw: {type(existing_transactions_raw[0])}")
        else:
            logger.info("TransactionProcessor: existing_transactions_raw list is empty or None.")

        logger.info(f"TransactionProcessor: Type of new_transactions_raw received: {type(new_transactions_raw)}")
        if new_transactions_raw:
            logger.info(f"TransactionProcessor: Type of first item in new_transactions_raw: {type(new_transactions_raw[0])}")
        else:
            logger.info("TransactionProcessor: new_transactions_raw list is empty or None.")


        # Step 1: Parse all raw transactions (existing and new)
        # We need to parse existing transactions first to initialize the disposition engine.
        # It's important that these are valid if they are truly 'existing_transactions'
        # with already computed costs, so they should generally not produce errors here.
        parsed_existing, errored_existing = self._parser.parse_transactions(existing_transactions_raw)
        # FIX START: Correctly iterate and add each errored transaction
        for errored_txn in errored_existing:
            self._error_reporter.add_errored_transaction(errored_txn)
        # FIX END

        parsed_new, errored_new = self._parser.parse_transactions(new_transactions_raw)
        # FIX START: Correctly iterate and add each errored transaction
        for errored_txn in errored_new:
            self._error_reporter.add_errored_transaction(errored_txn)
        # FIX END

        # Combine successfully parsed transactions for further processing
        all_parsed_transactions = parsed_existing + parsed_new
        successfully_parsed_new_transactions = parsed_new # Keep track of only the new ones that passed initial parsing

        # Step 2: Initialize DispositionEngine with existing (processed) lots
        # This is crucial so new SELLs can match against historical BUYs.
        self._disposition_engine.set_initial_lots(parsed_existing)

        # Step 3: Sort all transactions (existing and newly parsed)
        # The sorting must happen after parsing, as we need date and quantity.
        # The cost calculation order relies on this sorted list.
        sorted_transactions = self._sorter.sort_transactions(
            existing_transactions=parsed_existing,
            new_transactions=successfully_parsed_new_transactions
        )

        processed_transactions: List[Transaction] = []

        # Step 4: Iterate through sorted transactions and calculate costs
        for transaction in sorted_transactions:
            # We only process transactions that are not already marked as errored
            # (e.g., from initial parsing).
            if transaction.error_reason:
                # If transaction already has an error, add it to reporter and skip.
                # This ensures we don't try to calculate costs for invalid transactions.
                self._error_reporter.add_error(transaction.transaction_id, transaction.error_reason)
                continue

            # This is where the magic happens: the CostCalculator determines the strategy
            # and updates the transaction object in-place with calculated costs.
            self._cost_calculator.calculate_transaction_costs(transaction)

            # If the cost calculation (or disposition engine) added an error,
            # we move it to the errored list.
            if transaction.error_reason:
                self._error_reporter.add_error(transaction.transaction_id, transaction.error_reason)
            else:
                processed_transactions.append(transaction)

        # Ensure that processed_transactions only contains new_transactions that were successfully processed
        final_processed_new_transactions = [
            txn for txn in processed_transactions
            if txn.transaction_id in {t.transaction_id for t in successfully_parsed_new_transactions}
        ]

        return final_processed_new_transactions, self._error_reporter.get_errors()