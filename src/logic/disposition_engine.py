# src/logic/disposition_engine.py

from collections import defaultdict, deque
from typing import Deque, Optional, Tuple # Removed Dict, List as we use built-in generics
from decimal import Decimal, getcontext # Use Decimal for precise financial calculations
from src.core.models.transaction import Transaction # <--- ADD THIS LINE

# Set precision for Decimal calculations (e.g., 10 decimal places)
getcontext().prec = 10

class CostLot:
    """Represents a single 'lot' of securities acquired through a BUY transaction."""
    def __init__(self, transaction_id: str, quantity: Decimal, cost_per_share: Decimal):
        self.transaction_id = transaction_id
        self.original_quantity = quantity # The initial quantity of this lot
        self.remaining_quantity = quantity # Quantity still available in this lot
        self.cost_per_share = cost_per_share

    @property
    def total_cost(self) -> Decimal:
        """Calculates the total cost of the original lot."""
        return self.original_quantity * self.cost_per_share

    def __repr__(self) -> str:
        return (f"CostLot(txn_id='{self.transaction_id}', "
                f"original_qty={self.original_quantity:.2f}, "
                f"remaining_qty={self.remaining_quantity:.2f}, "
                f"cost_per_share={self.cost_per_share:.4f})")


class DispositionEngine:
    """
    Manages the 'cost lots' for instruments within portfolios, tracking
    available quantities for FIFO cost basis matching.
    """
    def __init__(self):
        # Stores cost lots: { (portfolio_id, instrument_id): Deque[CostLot] }
        self._open_lots: dict[tuple[str, str], deque[CostLot]] = defaultdict(deque) # Changed Dict and Tuple to dict and tuple

    def add_buy_lot(self, transaction: Transaction):
        """
        Adds a new cost lot from a BUY transaction to the open lots.
        Assumes transaction.net_cost is already calculated for BUYs.
        """
        if transaction.net_cost is None:
            raise ValueError(f"Buy transaction {transaction.transaction_id} must have net_cost calculated before adding as a lot.")

        # Ensure decimal types for calculations
        quantity = Decimal(str(transaction.quantity))
        net_cost = Decimal(str(transaction.net_cost))

        # Handle potential division by zero if quantity is 0, though Pydantic 'PositiveFloat' should prevent this for input
        if quantity == 0:
            # For a 0 quantity BUY, we don't add a lot that can be sold against
            # Potentially an error, but disposition engine doesn't report it
            return

        cost_per_share = net_cost / quantity
        key = (transaction.portfolio_id, transaction.instrument_id)
        self._open_lots[key].append(
            CostLot(
                transaction_id=transaction.transaction_id,
                quantity=quantity,
                cost_per_share=cost_per_share
            )
        )

    def get_available_quantity(self, portfolio_id: str, instrument_id: str) -> Decimal:
        """
        Returns the total available quantity for a given instrument in a portfolio.
        """
        key = (portfolio_id, instrument_id)
        total_qty = Decimal(0)
        for lot in self._open_lots[key]:
            total_qty += lot.remaining_quantity
        return total_qty

    def consume_sell_quantity_fifo(
        self, transaction: Transaction
    ) -> Tuple[Decimal, Decimal, Optional[str]]: # Tuple is from typing, so it's fine
        """
        Consumes quantity from open lots using FIFO method for a SELL transaction.
        Calculates the total matched cost and returns it along with consumed quantity.

        Args:
            transaction: The SELL transaction.

        Returns:
            A tuple:
            - total_matched_cost: The total cost basis of the lots consumed.
            - consumed_quantity: The actual quantity consumed from lots (might be less than requested if insufficient).
            - error_reason: An error string if quantity exceeds available, otherwise None.
        """
        key = (transaction.portfolio_id, transaction.instrument_id)
        sell_quantity = Decimal(str(transaction.quantity))
        required_quantity = sell_quantity
        total_matched_cost = Decimal(0)
        consumed_quantity = Decimal(0)

        # Check if enough quantity is available first
        available_qty = self.get_available_quantity(portfolio_id=key[0], instrument_id=key[1])
        if required_quantity > available_qty:
            return (
                Decimal(0),
                Decimal(0),
                f"Sell quantity ({required_quantity:.2f}) exceeds available holdings ({available_qty:.2f}) for instrument '{key[1]}' in portfolio '{key[0]}'."
            )

        lots_for_instrument = self._open_lots[key]

        while required_quantity > 0 and lots_for_instrument:
            current_lot = lots_for_instrument[0] # FIFO: get the oldest lot

            if current_lot.remaining_quantity >= required_quantity:
                # Lot can cover the remaining required quantity
                total_matched_cost += required_quantity * current_lot.cost_per_share
                consumed_quantity += required_quantity
                current_lot.remaining_quantity -= required_quantity
                required_quantity = Decimal(0) # All required quantity consumed
                if current_lot.remaining_quantity == 0:
                    lots_for_instrument.popleft() # Remove fully consumed lot
            else:
                # Lot cannot fully cover, consume what's available in this lot
                total_matched_cost += current_lot.remaining_quantity * current_lot.cost_per_share
                consumed_quantity += current_lot.remaining_quantity
                required_quantity -= current_lot.remaining_quantity
                lots_for_instrument.popleft() # This lot is now fully consumed

        return total_matched_cost, consumed_quantity, None

    def get_all_open_lots(self) -> dict[tuple[str, str], deque[CostLot]]: # Changed Dict and Tuple to dict and tuple
        """For debugging or testing: returns the current state of all open lots."""
        return self._open_lots

    def set_initial_lots(self, transactions: list[Transaction]): # Changed List to list
        """
        Initializes the disposition engine with existing BUY transactions.
        This is crucial for processing new SELLs against existing holdings.
        """
        for txn in transactions:
            if txn.transaction_type == TransactionType.BUY.value:
                self.add_buy_lot(txn)