# src/logic/sorter.py

from typing import List
from src.core.models.transaction import Transaction

class TransactionSorter:
    """
    Responsible for merging lists of transactions and sorting them
    according to defined processing rules.
    """

    def sort_transactions(
        self,
        existing_transactions: List[Transaction],
        new_transactions: List[Transaction]
    ) -> List[Transaction]:
        """
        Merges existing and new transactions and sorts them.

        Sorting Rules:
        1. Primary sort: transaction_date ascending.
        2. Secondary sort: quantity descending (for transactions on the same date).

        Args:
            existing_transactions: A list of previously processed Transaction objects.
            new_transactions: A list of new Transaction objects to be processed.

        Returns:
            A single, sorted list of all Transaction objects.
        """
        all_transactions = existing_transactions + new_transactions

        # Sort based on transaction_date (ascending) and then quantity (descending)
        # Python's sort is stable, so secondary sort won't disrupt primary sort if keys are equal
        all_transactions.sort(key=lambda txn: (txn.transaction_date, -txn.quantity))

        return all_transactions