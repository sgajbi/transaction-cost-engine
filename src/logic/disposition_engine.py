# src/logic/disposition_engine.py

# src/logic/disposition_engine.py

from collections import defaultdict, deque
from typing import Deque, Optional, Tuple, Dict
from decimal import Decimal # Removed 'getcontext' import as it's no longer used here
from src.core.models.transaction import Transaction
from src.core.enums.transaction_type import TransactionType
from src.logic.cost_basis_strategies import CostBasisStrategy, FIFOBasisStrategy, AverageCostBasisStrategy
from src.logic.cost_objects import CostLot


class DispositionEngine:
    """
    Manages the 'cost lots' for instruments within portfolios,
    delegating the actual cost basis calculation logic to a specific strategy.
    """
    def __init__(self, cost_basis_strategy: CostBasisStrategy):
        self._cost_basis_strategy = cost_basis_strategy

    def add_buy_lot(self, transaction: Transaction):
        """
        Delegates adding a new BUY transaction to the active cost basis strategy.
        """
        self._cost_basis_strategy.add_buy_lot(transaction)

    def get_available_quantity(self, portfolio_id: str, instrument_id: str) -> Decimal:
        """
        Delegates getting available quantity to the active cost basis strategy.
        """
        return self._cost_basis_strategy.get_available_quantity(portfolio_id, instrument_id)

    def consume_sell_quantity(
        self, transaction: Transaction
    ) -> Tuple[Decimal, Decimal, Optional[str]]:
        """
        Delegates consuming quantity for a SELL transaction to the active cost basis strategy.
        """
        sell_quantity = Decimal(str(transaction.quantity))
        return self._cost_basis_strategy.consume_sell_quantity(
            transaction.portfolio_id, transaction.instrument_id, sell_quantity
        )

    def set_initial_lots(self, transactions: list[Transaction]):
        """
        Delegates initializing the disposition engine with existing BUY transactions
        to the active cost basis strategy.
        """
        self._cost_basis_strategy.set_initial_lots(transactions)

    def get_all_open_lots(self) -> Dict[Tuple[str, str], Deque[CostLot]]:
        """
        For debugging or testing: returns the current state of all open lots.
        Note: This method might not be directly applicable or fully representative
        for non-FIFO strategies (e.g., Average Cost).
        """
        # This implementation requires specific attributes from FIFOBasisStrategy.
        # If the active strategy is AverageCostBasisStrategy, it will raise an error.
        if isinstance(self._cost_basis_strategy, FIFOBasisStrategy):
            return self._cost_basis_strategy._open_lots
        elif isinstance(self._cost_basis_strategy, AverageCostBasisStrategy):
             raise NotImplementedError("get_all_open_lots is not applicable for AverageCostBasisStrategy. Consider adding a method like get_all_current_holdings_average_cost to the strategy if needed.")
        else:
            raise NotImplementedError(f"get_all_open_lots not implemented for {type(self._cost_basis_strategy).__name__}")