# src/logic/error_reporter.py

from typing import Dict, Any, Optional
from src.core.models.response import ErroredTransaction

class ErrorReporter:
    """
    Manages the collection and reporting of processing errors for transactions.
    """

    def __init__(self):
        self._errored_transactions: dict[str, ErroredTransaction] = {} 
   
    def get_errors(self) -> list[ErroredTransaction]:
        """
        Adds an error for a specific transaction. If an error for the same
        transaction ID already exists, it updates the reason or appends to it.
        """
        if transaction_id in self._errored_transactions:
            # Append new error reason if one already exists for this transaction
            existing_reason = self._errored_transactions[transaction_id].error_reason
            if error_reason not in existing_reason: # Avoid duplicate messages
                self._errored_transactions[transaction_id].error_reason += f"; {error_reason}"
        else:
            self._errored_transactions[transaction_id] = ErroredTransaction(
                transaction_id=transaction_id,
                error_reason=error_reason
            )

    def add_errored_transaction(self, errored_txn: ErroredTransaction):
        """
        Adds an existing ErroredTransaction object to the collection.
        This is useful for propagating errors directly from other components.
        """
        self.add_error(errored_txn.transaction_id, errored_txn.error_reason)

    def get_errors(self) -> List[ErroredTransaction]:
        """
        Returns a list of all collected errored transactions.
        """
        return list(self._errored_transactions.values())

    def has_errors(self) -> bool:
        """
        Checks if any errors have been reported.
        """
        return bool(self._errored_transactions)

    def clear(self):
        """
        Clears all collected errors.
        """
        self._errored_transactions = {}