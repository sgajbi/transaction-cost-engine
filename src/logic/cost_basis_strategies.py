# src/logic/cost_basis_strategies.py
import logging
from typing import Protocol, Deque, Dict, Tuple, Optional
from collections import deque, defaultdict
from decimal import Decimal     

from src.core.models.transaction import Transaction
from src.logic.cost_objects import CostLot

logger = logging.getLogger(__name__) 

# --- Cost Basis Strategy Protocol ---

class CostBasisStrategy(Protocol):
    """
    Protocol (interface) for different cost basis calculation methods (e.g., FIFO, Average Cost).
    """
    def add_buy_lot(self, transaction: Transaction):
        """
        Adds a new 'buy' transaction's cost to the inventory for future disposition.
        """
        ...

    def consume_sell_quantity(
        self, portfolio_id: str, instrument_id: str, sell_quantity: Decimal
    ) -> Tuple[Decimal, Decimal, Optional[str]]:
        """
        Consumes quantity for a sell transaction based on the specific cost basis method.
        Returns:
            A tuple: (total_matched_cost, consumed_quantity, error_reason)
        """
        ...

    def set_initial_lots(self, transactions: list[Transaction]):
        """
        Initializes the strategy with existing BUY transactions.
        """
        ...

    def get_available_quantity(self, portfolio_id: str, instrument_id: str) -> Decimal:
        """
        Returns the total available quantity for a given instrument in a portfolio.
        """
        ...

# --- FIFO Cost Basis Strategy Implementation ---

class FIFOBasisStrategy:
    """
    Implements the First-In, First-Out (FIFO) cost basis method.
    Uses a deque to maintain the order of cost lots.
    """
    def __init__(self):
        # Stores cost lots: { (portfolio_id, instrument_id): Deque[CostLot] }
        self._open_lots: Dict[Tuple[str, str], Deque[CostLot]] = defaultdict(deque)

    def add_buy_lot(self, transaction: Transaction):
        """
        Adds a new cost lot from a BUY transaction to the open lots for FIFO.
        Assumes transaction.net_cost is already calculated for BUYs.
        """
        if transaction.net_cost is None:
            raise ValueError(f"Buy transaction {transaction.transaction_id} must have net_cost calculated before adding as a lot.")

        quantity = Decimal(str(transaction.quantity))
        net_cost = Decimal(str(transaction.net_cost))

        if quantity == 0:
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

    def consume_sell_quantity(
        self, portfolio_id: str, instrument_id: str, sell_quantity: Decimal
    ) -> Tuple[Decimal, Decimal, Optional[str]]:
        """
        Consumes quantity from open lots using FIFO method for a SELL transaction.
        Calculates the total matched cost and returns it along with consumed quantity.
        """
        key = (portfolio_id, instrument_id)
        required_quantity = sell_quantity
        total_matched_cost = Decimal(0)
        consumed_quantity = Decimal(0)

        available_qty = self.get_available_quantity(portfolio_id=key[0], instrument_id=key[1])
        if required_quantity > available_qty:
            return (
                Decimal(0),
                Decimal(0),
                f"Sell quantity ({required_quantity:.2f}) exceeds available holdings ({available_qty:.2f}) for instrument '{key[1]}' in portfolio '{key[0]}'."
            )

        lots_for_instrument = self._open_lots[key]

        while required_quantity > 0 and lots_for_instrument:
            current_lot = lots_for_instrument[0]

            if current_lot.remaining_quantity >= required_quantity:
                # Lot can fully cover the remaining required quantity
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

    def get_available_quantity(self, portfolio_id: str, instrument_id: str) -> Decimal:
        """
        Returns the total available quantity for a given instrument by summing remaining quantities in all FIFO lots.
        """
        key = (portfolio_id, instrument_id)
        return sum(lot.remaining_quantity for lot in self._open_lots[key])

    def set_initial_lots(self, transactions: list[Transaction]):
        """
        Initializes the FIFO strategy with existing BUY transactions.
        """
        for txn in transactions:
            if txn.transaction_type == "BUY": # Use string literal for consistency with Pydantic model
                self.add_buy_lot(txn)

# --- Average Cost Basis Strategy Implementation ---

class AverageCostBasisStrategy(CostBasisStrategy):
    """
    Implements the Average Cost (AVCO) method for tracking cost basis.
    This method aggregates the cost of all shares purchased and divides by the total quantity
    to determine the average cost per share.
    """
    def __init__(self):
        # Stores total quantity and total cost for each instrument/portfolio
        # Key: (portfolio_id, instrument_id)
        # Value: {'total_qty': Decimal, 'total_cost': Decimal}
        self._holdings: Dict[Tuple[str, str], Dict[str, Decimal]] = defaultdict(lambda: {'total_qty': Decimal(0), 'total_cost': Decimal(0)})
        logger.debug("AverageCostBasisStrategy initialized.") 


    def add_buy_lot(self, transaction: Transaction):
        """
        Adds a BUY transaction's quantity and cost to the aggregated holdings for average cost.
        """
        key = (transaction.portfolio_id, transaction.instrument_id)
        
        # Ensure Decimal conversion from string representation of float inputs
        buy_quantity = Decimal(str(transaction.quantity))
        buy_net_cost = Decimal(str(transaction.net_cost)) # Use net_cost for cost basis

        logger.debug(f"Before BUY: Holdings for {key}: total_qty={self._holdings[key]['total_qty']:.2f}, total_cost={self._holdings[key]['total_cost']:.2f}")
        logger.debug(f"Processing BUY {transaction.transaction_id}: quantity={buy_quantity:.2f}, net_cost={buy_net_cost:.2f}")


        self._holdings[key]['total_qty'] += buy_quantity
        self._holdings[key]['total_cost'] += buy_net_cost

        logger.debug(f"After BUY: Holdings for {key}: total_qty={self._holdings[key]['total_qty']:.2f}, total_cost={self._holdings[key]['total_cost']:.2f}")


    def consume_sell_quantity(self, portfolio_id: str, instrument_id: str, required_quantity: Decimal) -> Tuple[Decimal, Decimal, Optional[str]]:
        """
        Calculates the cost basis for a SELL transaction using the average cost method.
        """
        key = (portfolio_id, instrument_id)
        total_qty = self._holdings[key]['total_qty']
        total_cost = self._holdings[key]['total_cost']
        logger.debug(f"Processing SELL for {key}: required_quantity={required_quantity:.2f}")
        logger.debug(f"Current holdings for SELL: total_qty={total_qty:.2f}, total_cost={total_cost:.2f}")

        if required_quantity > total_qty:
            logger.warning(f"Sell quantity ({required_quantity:.2f}) exceeds available average cost holdings ({total_qty:.2f}) for instrument '{key[1]}' in portfolio '{key[0]}'.")
            return (
                Decimal(0),
                Decimal(0),
                f"Sell quantity ({required_quantity:.2f}) exceeds available average cost holdings ({total_qty:.2f}) for instrument '{key[1]}' in portfolio '{key[0]}'."
            )

        if total_qty == Decimal(0):
             return (
                Decimal(0),
                Decimal(0),
                f"No holdings for instrument '{key[1]}' in portfolio '{key[0]}' to sell against (Average Cost method).",
            )

        average_cost_per_share = total_cost / total_qty
        logger.debug(f"Calculated average_cost_per_share: {average_cost_per_share:.6f}")

        
        matched_cost = required_quantity * average_cost_per_share
        consumed_quantity = required_quantity
        logger.debug(f"Matched cost for sell quantity {consumed_quantity:.2f}: {matched_cost:.6f}")

        # Update holdings after sale
        self._holdings[key]['total_qty'] -= consumed_quantity
        self._holdings[key]['total_cost'] -= matched_cost # Deduct the cost basis of the sold shares
        logger.debug(f"After SELL: Holdings for {key}: total_qty={self._holdings[key]['total_qty']:.2f}, total_cost={self._holdings[key]['total_cost']:.2f}")

        return matched_cost, consumed_quantity, None

    def get_available_quantity(self, portfolio_id: str, instrument_id: str) -> Decimal:
        """
        Returns the total available quantity for a given instrument based on average cost holdings.
        """
        key = (portfolio_id, instrument_id)
        return self._holdings[key]['total_qty']

    def set_initial_lots(self, transactions: list[Transaction]):
        """
        Initializes the Average Cost strategy with existing BUY transactions.
        """
        logger.debug("Setting initial lots for AverageCostBasisStrategy...")

        for txn in transactions:
            if txn.transaction_type == "BUY": # Use string literal for consistency with Pydantic model
                # Add existing BUY transactions to current holdings
                key = (txn.portfolio_id, txn.instrument_id)
                self._holdings[key]['total_qty'] += Decimal(str(txn.quantity)) # Ensure Decimal from string repr
                self._holdings[key]['total_cost'] += Decimal(str(txn.net_cost)) # Ensure Decimal from string repr
                logger.debug(f"Initial BUY added: Txn ID={txn.transaction_id}, quantity={txn.quantity:.2f}, net_cost={txn.net_cost:.2f}. Current holdings: total_qty={self._holdings[key]['total_qty']:.2f}, total_cost={self._holdings[key]['total_cost']:.2f}")