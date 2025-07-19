# src/logic/parser.py

import logging # Added
from typing import Any, Tuple
from pydantic import ValidationError, TypeAdapter # Keep TypeAdapter for individual validation

from src.core.models.transaction import Transaction # This is needed
from src.core.models.response import ErroredTransaction # This is needed
from src.core.enums.transaction_type import TransactionType # This is needed

logger = logging.getLogger(__name__) # Added

class TransactionParser:
    """
    Parses raw transaction dictionaries into validated Transaction objects.
    Handles data type conversions and initial validation using Pydantic.
    """
    def __init__(self):
        # Initialize TypeAdapter for a SINGLE Transaction object, not a list of them.
        # This adapter will be used to validate each dictionary individually.
        self._single_transaction_adapter = TypeAdapter(Transaction)

    def parse_transactions(
        self, raw_transactions_data: list[dict[str, Any]] # Renamed parameter for clarity: expecting list of dictionaries
    ) -> Tuple[list[Transaction], list[ErroredTransaction]]:
        """
        Parses a list of raw transaction dictionaries into validated Transaction objects
        and identifies any that fail validation.
        """
        logger.info(f"TransactionParser: Type of raw_transactions_data received: {type(raw_transactions_data)}") # Added
        if raw_transactions_data: # Added
            logger.info(f"TransactionParser: Type of first item in raw_transactions_data (before loop): {type(raw_transactions_data[0])}") # Added
        else: # Added
            logger.info("TransactionParser: raw_transactions_data is empty or None.") # Added

        parsed_transactions: list[Transaction] = []
        errored_transactions: list[ErroredTransaction] = []

        for raw_txn_data in raw_transactions_data: # Iterate over each raw dictionary
            # THIS IS THE CRITICAL LOG THAT WILL TELL US THE TYPE IN THE LOOP:
            logger.info(f"TransactionParser: Type of raw_txn_data in loop (before .get()): {type(raw_txn_data)}") # Added

            # Get transaction_id for error reporting BEFORE attempting validation
            # We expect raw_txn_data to be a dictionary here, so .get() is appropriate.
            transaction_id = raw_txn_data.get("transaction_id", "UNKNOWN_ID_BEFORE_PARSE")

            try:
                # Use the _single_transaction_adapter to validate the current raw dictionary
                validated_txn = self._single_transaction_adapter.validate_python(raw_txn_data)
                parsed_transactions.append(validated_txn)
            except ValidationError as e:
                # Collect detailed error messages from Pydantic
                error_messages = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
                errored_transactions.append(
                    ErroredTransaction(
                        transaction_id=transaction_id,
                        error_reason=f"Validation error: {error_messages}"
                    )
                )
            except Exception as e:
                # Catch any other unexpected errors during parsing
                errored_transactions.append(
                    ErroredTransaction(
                        transaction_id=transaction_id,
                        error_reason=f"Unexpected parsing error: {type(e).__name__}: {str(e)}"
                    )
                )
        return parsed_transactions, errored_transactions