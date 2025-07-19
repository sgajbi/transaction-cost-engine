# src/logic/parser.py

from typing import Dict, Any, Tuple
from pydantic import ValidationError, TypeAdapter
from src.core.models.transaction import Transaction
from src.core.models.response import ErroredTransaction
from src.core.enums.transaction_type import TransactionType

class TransactionParser:
    """
    Responsible for parsing raw transaction data (dictionaries) into Pydantic Transaction models
    and performing initial validations. It identifies and separates successfully parsed
    transactions from those with parsing or basic validation errors.
    """

    def __init__(self):
        # TypeAdapter is a Pydantic v2 feature for validating lists of models efficiently
        self._transaction_list_adapter = TypeAdapter(List[Transaction])

    def parse_transactions(
         self, raw_transactions: list[dict[str, Any]]
    ) -> Tuple[list[Transaction], list[ErroredTransaction]]:
      
        """
        Parses a list of raw transaction dictionaries into Transaction Pydantic models.
        Separates valid transactions from errored ones.

        Args:
            raw_transactions: A list of dictionaries, each representing a raw transaction.

        Returns:
            A tuple containing:
            - A list of successfully parsed Transaction objects.
            - A list of ErroredTransaction objects for transactions that failed parsing.
        """
        parsed_transactions: list[Transaction] = []
        errored_transactions: list[ErroredTransaction] = []

        for raw_txn in raw_transactions:
            transaction_id = raw_txn.get("transaction_id", "UNKNOWN_ID")
            try:
                # Attempt to parse the raw dictionary into a Transaction model
                # Pydantic handles type coercion and basic validation (e.g., date format, positive numbers)
                parsed_txn = self._transaction_list_adapter.validate_python([raw_txn])[0]

                # Additional business logic validation: Check if transaction_type is valid
                if not TransactionType.is_valid(parsed_txn.transaction_type):
                    errored_transactions.append(
                        ErroredTransaction(
                            transaction_id=transaction_id,
                            error_reason=f"Invalid transaction_type: '{parsed_txn.transaction_type}'. "
                                         f"Must be one of {TransactionType.list()}."
                        )
                    )
                    continue # Skip to the next transaction if type is invalid

                parsed_transactions.append(parsed_txn)

            except ValidationError as e:
                # Pydantic ValidationError captures detailed validation issues
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
                        error_reason=f"Unexpected parsing error: {str(e)}"
                    )
                )

        return parsed_transactions, errored_transactions