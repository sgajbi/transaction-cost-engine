# src/logic/cost_calculator.py

from typing import Protocol
from decimal import Decimal, getcontext

from src.core.models.transaction import Transaction
from src.core.enums.transaction_type import TransactionType
from src.logic.disposition_engine import DispositionEngine # Import the engine
from src.logic.error_reporter import ErrorReporter # Import the error reporter

# Set precision for Decimal calculations (e.g., 10 decimal places)
getcontext().prec = 10

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
        Also adds the lot to the disposition engine.
        """
        # Gross = gross_transaction_amount (as provided)
        transaction.gross_cost = Decimal(str(transaction.gross_transaction_amount))

        # Net = gross + fees + accrued_interest
        total_fees = Decimal(str(transaction.fees.total_fees)) if transaction.fees else Decimal(0)
        accrued_interest = Decimal(str(transaction.accrued_interest)) if transaction.accrued_interest is not None else Decimal(0)

        transaction.net_cost = transaction.gross_cost + total_fees + accrued_interest

        # For BUYs, average_price can be updated or calculated, depending on your business rule.
        # Here, we'll set it to the effective cost per share if not already provided.
        if transaction.quantity > 0:
            calculated_average_price = transaction.net_cost / Decimal(str(transaction.quantity))
            if transaction.average_price is None:
                transaction.average_price = calculated_average_price
            # If provided average_price is significantly different, you might log a warning or flag.
        else:
            transaction.average_price = Decimal(0) # Or None, based on desired behavior for 0 quantity buys

        # Add the buy transaction as an open lot for future sells
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
        Calculates Realized Gain/Loss for a SELL transaction using FIFO cost matching.
        """
        sell_quantity = Decimal(str(transaction.quantity))
        sell_proceeds = Decimal(str(transaction.gross_transaction_amount))

        # Gross/Net cost are not applicable for SELLs in the same way as BUYs
        transaction.gross_cost = Decimal(0)
        transaction.net_cost = Decimal(0)

        total_matched_cost, consumed_quantity, error_reason = \
            disposition_engine.consume_sell_quantity_fifo(transaction)

        if error_reason:
            # If disposition engine reports an error (e.g., insufficient quantity)
            error_reporter.add_error(transaction.transaction_id, error_reason)
            transaction.realized_gain_loss = None # Or Decimal(0), based on desired behavior for errored sells
            # Mark the transaction as failed by setting error_reason directly on the transaction
            # (though the ErrorReporter also tracks it)
            transaction.error_reason = error_reason
            return

        # Realized Gain/Loss = sell proceeds - matched buy cost
        # Only calculate if a valid quantity was consumed
        if consumed_quantity > 0:
            transaction.realized_gain_loss = sell_proceeds - total_matched_cost
        else:
            transaction.realized_gain_loss = Decimal(0) # If no quantity matched (e.g., 0 quantity sell)

        # For SELLs, average_price might represent the average sell price or average matched buy price.
        # Let's set it to average sell price for now.
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
        disposition_engine: DispositionEngine, # Not used for these types, but interface requires it
        error_reporter: ErrorReporter # Not typically used for simple calculations, but interface requires it
    ) -> None:
        """
        Sets gross_cost and net_cost based on transaction amounts.
        Realized gain/loss is not applicable.
        """
        # For simplicity, for these types, gross_cost and net_cost might just reflect
        # the transaction amount itself or zero if not applicable.
        # Adjust this logic based on exact business rules for each type.

        # Example: For INTEREST, DIVIDEND, DEPOSIT, WITHDRAWAL, FEE, OTHER
        # Net and Gross cost might just be the provided gross/net transaction amount,
        # or it might be treated as 0 as it doesn't represent an 'asset acquisition cost'.
        # Assuming for now they represent the amount of value itself.
        transaction.gross_cost = Decimal(str(transaction.gross_transaction_amount))
        # Use provided net_transaction_amount if available, otherwise default to gross
        if transaction.net_transaction_amount is not None:
            transaction.net_cost = Decimal(str(transaction.net_transaction_amount))
        else:
            transaction.net_cost = transaction.gross_cost # Default if net not provided

        transaction.realized_gain_loss = None # Not applicable for these types
        transaction.average_price = None # Not applicable for these types


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
            TransactionType.BUY: BuyStrategy(),
            TransactionType.SELL: SellStrategy(),
            TransactionType.INTEREST: DefaultStrategy(),
            TransactionType.DIVIDEND: DefaultStrategy(),
            TransactionType.DEPOSIT: DefaultStrategy(),
            TransactionType.WITHDRAWAL: DefaultStrategy(),
            TransactionType.FEE: DefaultStrategy(),
            TransactionType.OTHER: DefaultStrategy(),
            # Add other specific strategies here as needed
        }
        self._default_strategy = DefaultStrategy() # Fallback for unknown types (though enum should prevent)

    def calculate_transaction_costs(self, transaction: Transaction):
        """
        Delegates cost calculation to the appropriate strategy based on transaction type.
        """
        transaction_type_enum: Optional[TransactionType] = None
        try:
            # Convert string transaction type to enum for lookup
            transaction_type_enum = TransactionType(transaction.transaction_type)
        except ValueError:
            # This should ideally be caught by TransactionParser, but as a safeguard:
            self._error_reporter.add_error(
                transaction.transaction_id,
                f"Unknown transaction type '{transaction.transaction_type}'. Cannot calculate costs."
            )
            # Mark the transaction as failed and skip calculation
            transaction.error_reason = f"Unknown transaction type '{transaction.transaction_type}'."
            return

        strategy = self._strategies.get(transaction_type_enum, self._default_strategy)
        strategy.calculate_costs(transaction, self._disposition_engine, self._error_reporter)