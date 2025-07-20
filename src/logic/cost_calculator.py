# src/logic/cost_calculator.py

from typing import Protocol, Optional
from decimal import Decimal

from src.core.models.transaction import Transaction
from src.core.enums.transaction_type import TransactionType
from src.logic.disposition_engine import DispositionEngine
from src.logic.error_reporter import ErrorReporter

# REMOVED: getcontext().prec = 10 (now in main.py)

class TransactionCostStrategy(Protocol):
    """
    Protocol (interface) for transaction cost calculation strategies.
    Each strategy implements specific logic for a transaction type.
    """
    def calculate_costs(
        self,
        transaction: Transaction,
        disposition_engine: DispositionEngine,
        error_reporter: ErrorReporter
    ) -> None:
        """
        Calculates the net cost, gross cost, and realized gain/loss for a transaction.
        Modifies the transaction object in place.
        """
        ... # Protocol does not contain implementation details


class BuyStrategy:
    """Strategy for calculating costs for BUY transactions."""
    def calculate_costs(
        self,
        transaction: Transaction,
        disposition_engine: DispositionEngine,
        error_reporter: ErrorReporter
    ) -> None:
        """
        Calculates Net Cost and Gross Cost for a BUY transaction.
        Also adds the lot to the disposition engine (if quantity > 0).
        """
        # Gross = gross_transaction_amount (as provided)
        transaction.gross_cost = Decimal(str(transaction.gross_transaction_amount))

        # Net = gross + fees + accrued_interest
        total_fees = transaction.fees.total_fees if transaction.fees else Decimal(0)
        accrued_interest = Decimal(str(transaction.accrued_interest)) if transaction.accrued_interest is not None else Decimal(0)

        transaction.net_cost = transaction.gross_cost + total_fees + accrued_interest

        if transaction.quantity > 0:
            calculated_average_price = transaction.net_cost / Decimal(str(transaction.quantity))
            if transaction.average_price is None:
                transaction.average_price = calculated_average_price
        else:
            transaction.average_price = Decimal(0)

        # Only add the buy transaction as an open lot if quantity is greater than zero
        if transaction.quantity > Decimal(0): # FIX: Add quantity check before calling add_buy_lot
            try:
                disposition_engine.add_buy_lot(transaction)
            except ValueError as e:
                error_reporter.add_error(transaction.transaction_id, str(e))


class SellStrategy:
    """Strategy for calculating costs and realized gain/loss for SELL transactions."""
    def calculate_costs(
        self,
        transaction: Transaction,
        disposition_engine: DispositionEngine,
        error_reporter: ErrorReporter
    ) -> None:
        """
        Calculates Realized Gain/Loss for a SELL transaction using the disposition engine,
        and sets gross_cost/net_cost to the negative of the matched cost.
        """
        sell_quantity = Decimal(str(transaction.quantity))
        sell_proceeds = Decimal(str(transaction.gross_transaction_amount))

        # Use the generic consume_sell_quantity which delegates to the chosen strategy
        total_matched_cost, consumed_quantity, error_reason = \
            disposition_engine.consume_sell_quantity(transaction)

        if error_reason:
            error_reporter.add_error(transaction.transaction_id, error_reason)
            transaction.realized_gain_loss = None
            transaction.gross_cost = Decimal(0)
            transaction.net_cost = Decimal(0)
            return

        if consumed_quantity > 0:
            transaction.realized_gain_loss = sell_proceeds - total_matched_cost
            transaction.gross_cost = -total_matched_cost
            transaction.net_cost = -total_matched_cost
        else:
            transaction.realized_gain_loss = Decimal(0)
            transaction.gross_cost = Decimal(0)
            transaction.net_cost = Decimal(0)

        if sell_quantity > 0:
            transaction.average_price = sell_proceeds / sell_quantity
        else:
            transaction.average_price = Decimal(0)


class DefaultStrategy:
    """
    Default strategy for other transaction types (Interest, Dividend, Deposit, Withdrawal, Fee, Other).
    These typically don't involve cost basis or realized gain/loss calculations in the same way.
    """
    def calculate_costs(
        self,
        transaction: Transaction,
        disposition_engine: DispositionEngine,
        error_reporter: ErrorReporter
    ) -> None:
        """
        Sets gross_cost and net_cost based on transaction amounts.
        Realized gain/loss is not applicable.
        """
        transaction.gross_cost = Decimal(str(transaction.gross_transaction_amount))
        if transaction.net_transaction_amount is not None:
            transaction.net_cost = Decimal(str(transaction.net_transaction_amount))
        else:
            transaction.net_cost = transaction.gross_cost

        transaction.realized_gain_loss = None
        transaction.average_price = None


class CostCalculator:
    """
    Applies the appropriate cost calculation strategy based on transaction type.
    """

    def __init__(
        self,
        disposition_engine: DispositionEngine,
        error_reporter: ErrorReporter
    ):
        self._disposition_engine = disposition_engine
        self._error_reporter = error_reporter
        self._strategies: dict[TransactionType, TransactionCostStrategy] = {
            TransactionType.BUY: BuyStrategy(),
            TransactionType.SELL: SellStrategy(),
            TransactionType.INTEREST: DefaultStrategy(),
            TransactionType.DIVIDEND: DefaultStrategy(),
            TransactionType.DEPOSIT: DefaultStrategy(),
            TransactionType.WITHDRAWAL: DefaultStrategy(),
            TransactionType.FEE: DefaultStrategy(),
            TransactionType.OTHER: DefaultStrategy(),
        }
        self._default_strategy = DefaultStrategy()

    def calculate_transaction_costs(self, transaction: Transaction):
        """
        Delegates cost calculation to the appropriate strategy based on transaction type.
        """
        transaction_type_enum: Optional[TransactionType] = None
        try:
            transaction_type_enum = TransactionType(transaction.transaction_type)
        except ValueError:
            self._error_reporter.add_error(
                transaction.transaction_id,
                f"Unknown transaction type '{transaction.transaction_type}'. Cannot calculate costs."
            )
            return

        strategy = self._strategies.get(transaction_type_enum, self._default_strategy)
        strategy.calculate_costs(transaction, self._disposition_engine, self._error_reporter)