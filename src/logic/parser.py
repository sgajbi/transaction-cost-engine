# src/logic/parser.py

import logging
from typing import Any, Tuple
from pydantic import ValidationError, TypeAdapter

from src.core.models.transaction import Transaction
from src.core.models.response import ErroredTransaction
from src.core.enums.transaction_type import TransactionType
from src.logic.error_reporter import ErrorReporter # NEW: Import ErrorReporter

logger = logging.getLogger(__name__)

class TransactionParser:
    """
    Parses raw transaction dictionaries into validated Transaction objects.
    Handles data type conversions and initial validation using Pydantic.
    """
    def __init__(self, error_reporter: ErrorReporter): # MODIFIED: Add error_reporter parameter
        self._single_transaction_adapter = TypeAdapter(Transaction)
        self._error_reporter = error_reporter # NEW: Store error reporter

    def parse_transactions(
        self, raw_transactions_data: list[dict[str, Any]]
    ) -> Tuple[list[Transaction], list[ErroredTransaction]]:
        """
        Parses a list of raw transaction dictionaries into validated Transaction objects
        and identifies any that fail validation.
        """
        logger.info(f"TransactionParser: Type of raw_transactions_data received: {type(raw_transactions_data)}")
        if raw_transactions_data:
            logger.info(f"TransactionParser: Type of first item in raw_transactions_data (before loop): {type(raw_transactions_data[0])}")
        else:
            logger.info("TransactionParser: raw_transactions_data is empty or None.")

        parsed_transactions: list[Transaction] = []
        errored_transactions: list[ErroredTransaction] = []

        for raw_txn_data in raw_transactions_data:
            logger.info(f"TransactionParser: Type of raw_txn_data in loop (before .get()): {type(raw_txn_data)}")

            transaction_id = raw_txn_data.get("transaction_id", "UNKNOWN_ID_BEFORE_PARSE")

            try:
                validated_txn = self._single_transaction_adapter.validate_python(raw_txn_data)
                parsed_transactions.append(validated_txn)
            except ValidationError as e:
                error_messages = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
                errored_transactions.append(
                    ErroredTransaction(
                        transaction_id=transaction_id,
                        error_reason=f"Validation error: {error_messages}"
                    )
                )
            except Exception as e:
                errored_transactions.append(
                    ErroredTransaction(
                        transaction_id=transaction_id,
                        error_reason=f"Unexpected parsing error: {type(e).__name__}: {str(e)}"
                    )
                )
        return parsed_transactions, errored_transactions