# src/tests/unit/test_cost_calculator.py

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock # For mocking dependencies

from src.logic.cost_calculator import CostCalculator, BuyStrategy, SellStrategy, DefaultStrategy
from src.logic.disposition_engine import DispositionEngine
from src.logic.error_reporter import ErrorReporter
from src.core.models.transaction import Transaction
from src.core.models.transaction import Fees # To create Fees object for Transaction
from src.core.enums.transaction_type import TransactionType

# Common fixtures
@pytest.fixture
def mock_disposition_engine():
    """Mock DispositionEngine for isolating CostCalculator tests."""
    return MagicMock(spec=DispositionEngine)

@pytest.fixture
def error_reporter():
    """Provides a fresh ErrorReporter instance for each test."""
    return ErrorReporter()

@pytest.fixture
def cost_calculator(mock_disposition_engine, error_reporter):
    """Provides a CostCalculator instance with mocked dependencies."""
    return CostCalculator(
        disposition_engine=mock_disposition_engine,
        error_reporter=error_reporter
    )

# Mock Transaction data for consistency
@pytest.fixture
def buy_transaction_data():
    return Transaction(
        transaction_id="BUY001", portfolio_id="P1", instrument_id="AAPL", security_id="S1",
        transaction_type=TransactionType.BUY, transaction_date=date(2023, 1, 1), settlement_date=date(2023, 1, 3),
        quantity=Decimal("10"), gross_transaction_amount=Decimal("1500"), trade_currency="USD",
        fees=Fees(brokerage=Decimal("5.5")), accrued_interest=Decimal("10.0")
    )

@pytest.fixture
def sell_transaction_data():
    return Transaction(
        transaction_id="SELL001", portfolio_id="P1", instrument_id="AAPL", security_id="S1",
        transaction_type=TransactionType.SELL, transaction_date=date(2023, 1, 10), settlement_date=date(2023, 1, 12),
        quantity=Decimal("5"), gross_transaction_amount=Decimal("800"), trade_currency="USD",
        fees=Fees(brokerage=Decimal("2.0"))
    )

@pytest.fixture
def interest_transaction_data():
    return Transaction(
        transaction_id="INT001", portfolio_id="P2", instrument_id="CASH", security_id="C1",
        transaction_type=TransactionType.INTEREST, transaction_date=date(2023, 2, 1), settlement_date=date(2023, 2, 1),
        quantity=Decimal("0"), gross_transaction_amount=Decimal("10.50"), trade_currency="USD",
        net_transaction_amount=Decimal("9.0")
    )

@pytest.fixture
def dividend_transaction_data():
    return Transaction(
        transaction_id="DIV001", portfolio_id="P1", instrument_id="MSFT", security_id="S2",
        transaction_type=TransactionType.DIVIDEND, transaction_date=date(2023, 3, 1), settlement_date=date(2023, 3, 1),
        quantity=Decimal("0"), gross_transaction_amount=Decimal("25.00"), trade_currency="USD",
        fees=Fees(gst=Decimal("1.0"))
    )

@pytest.fixture
def unknown_transaction_data():
    # Intentionally malformed type to test error path
    return Transaction(
        transaction_id="UNKNOWN001", portfolio_id="P3", instrument_id="XYZ", security_id="S3",
        transaction_type="UNKNOWN_TYPE", transaction_date=date(2023, 4, 1), settlement_date=date(2023, 4, 1),
        quantity=Decimal("1"), gross_transaction_amount=Decimal("10"), trade_currency="USD"
    )

# --- Test BuyStrategy ---
def test_buy_strategy_calculate_costs(cost_calculator, mock_disposition_engine, buy_transaction_data):
    """Test BuyStrategy calculates net_cost, gross_cost, average_price and adds to disposition engine."""
    transaction = buy_transaction_data
    cost_calculator.calculate_transaction_costs(transaction)

    assert transaction.gross_cost == Decimal("1500")
    # net = gross + fees + accrued_interest = 1500 + 5.5 + 10 = 1515.5
    assert transaction.net_cost == Decimal("1515.5")
    # average_price = net_cost / quantity = 1515.5 / 10 = 151.55
    assert transaction.average_price == Decimal("151.55")
    assert transaction.realized_gain_loss is None

    mock_disposition_engine.add_buy_lot.assert_called_once_with(transaction)
    assert cost_calculator._error_reporter.has_errors() is False

def test_buy_strategy_calculate_costs_zero_quantity(cost_calculator, mock_disposition_engine, buy_transaction_data):
    """Test BuyStrategy with zero quantity buy."""
    transaction = buy_transaction_data
    transaction.quantity = Decimal("0")
    transaction.gross_transaction_amount = Decimal("0")
    transaction.net_cost = None # Reset for test, should be calculated based on fees/interest

    cost_calculator.calculate_transaction_costs(transaction)

    assert transaction.gross_cost == Decimal("0")
    assert transaction.net_cost == Decimal("15.5") # Fees (5.5) + Accrued Interest (10.0) still apply if non-zero transaction amount is 0
    assert transaction.average_price == Decimal("0") # Should be 0 or None for 0 quantity
    assert transaction.realized_gain_loss is None
    
    # add_buy_lot should NOT be called for zero quantity
    mock_disposition_engine.add_buy_lot.assert_not_called()
    assert cost_calculator._error_reporter.has_errors() is False

def test_buy_strategy_add_buy_lot_raises_error(cost_calculator, mock_disposition_engine, buy_transaction_data):
    """Test BuyStrategy correctly reports error if add_buy_lot fails."""
    mock_disposition_engine.add_buy_lot.side_effect = ValueError("Simulated add lot error")
    transaction = buy_transaction_data

    cost_calculator.calculate_transaction_costs(transaction)

    mock_disposition_engine.add_buy_lot.assert_called_once_with(transaction)
    assert cost_calculator._error_reporter.has_errors_for(transaction.transaction_id) is True
    assert "Simulated add lot error" in cost_calculator._error_reporter.get_errors()[0].error_reason

# --- Test SellStrategy ---
def test_sell_strategy_calculate_costs_gain(cost_calculator, mock_disposition_engine, sell_transaction_data):
    """Test SellStrategy calculates realized gain."""
    transaction = sell_transaction_data
    # Mock consume_sell_quantity to return a matched cost leading to gain
    # Sell 5 shares for 800. Matched cost for 5 shares was 500 (avg 100). Gain = 300.
    mock_disposition_engine.consume_sell_quantity.return_value = (Decimal("500"), Decimal("5"), None)

    cost_calculator.calculate_transaction_costs(transaction)

    mock_disposition_engine.consume_sell_quantity.assert_called_once_with(transaction)
    assert transaction.realized_gain_loss == Decimal("300") # 800 (proceeds) - 500 (matched cost)
    assert transaction.gross_cost == Decimal("-500") # Negative matched cost
    assert transaction.net_cost == Decimal("-500")   # Negative matched cost
    assert transaction.average_price == Decimal("160") # 800 / 5
    assert cost_calculator._error_reporter.has_errors() is False

def test_sell_strategy_calculate_costs_loss(cost_calculator, mock_disposition_engine, sell_transaction_data):
    """Test SellStrategy calculates realized loss."""
    transaction = sell_transaction_data
    # Mock consume_sell_quantity to return a matched cost leading to loss
    # Sell 5 shares for 800. Matched cost for 5 shares was 1000 (avg 200). Loss = -200.
    mock_disposition_engine.consume_sell_quantity.return_value = (Decimal("1000"), Decimal("5"), None)

    cost_calculator.calculate_transaction_costs(transaction)

    assert transaction.realized_gain_loss == Decimal("-200") # 800 - 1000
    assert transaction.gross_cost == Decimal("-1000")
    assert transaction.net_cost == Decimal("-1000")
    assert transaction.average_price == Decimal("160")
    assert cost_calculator._error_reporter.has_errors() is False

def test_sell_strategy_consume_sell_quantity_returns_error(cost_calculator, mock_disposition_engine, sell_transaction_data):
    """Test SellStrategy handles error from consume_sell_quantity."""
    transaction = sell_transaction_data
    error_msg = "Insufficient holdings for sell"
    mock_disposition_engine.consume_sell_quantity.return_value = (Decimal("0"), Decimal("0"), error_msg)

    cost_calculator.calculate_transaction_costs(transaction)

    mock_disposition_engine.consume_sell_quantity.assert_called_once_with(transaction)
    assert transaction.realized_gain_loss is None # Or Decimal(0) depending on exact requirement for errored sells
    assert transaction.gross_cost == Decimal("0")
    assert transaction.net_cost == Decimal("0")
    assert cost_calculator._error_reporter.has_errors_for(transaction.transaction_id) is True
    assert error_msg in cost_calculator._error_reporter.get_errors()[0].error_reason

def test_sell_strategy_calculate_costs_zero_quantity_sell(cost_calculator, mock_disposition_engine, sell_transaction_data):
    """Test SellStrategy with zero quantity sell."""
    transaction = sell_transaction_data
    transaction.quantity = Decimal("0")
    transaction.gross_transaction_amount = Decimal("0") # No proceeds for zero sell

    mock_disposition_engine.consume_sell_quantity.return_value = (Decimal("0"), Decimal("0"), None)

    cost_calculator.calculate_transaction_costs(transaction)

    assert transaction.realized_gain_loss == Decimal("0") # No gain/loss for zero quantity
    assert transaction.gross_cost == Decimal("0")
    assert transaction.net_cost == Decimal("0")
    assert transaction.average_price == Decimal("0") # 0 proceeds / 0 quantity -> 0
    mock_disposition_engine.consume_sell_quantity.assert_called_once_with(transaction)
    assert cost_calculator._error_reporter.has_errors() is False

# --- Test DefaultStrategy (for other transaction types) ---
def test_default_strategy_calculate_costs_interest(cost_calculator, mock_disposition_engine, interest_transaction_data):
    """Test DefaultStrategy for an INTEREST transaction."""
    transaction = interest_transaction_data
    cost_calculator.calculate_transaction_costs(transaction)

    assert transaction.gross_cost == Decimal("10.50")
    assert transaction.net_cost == Decimal("9.0") # Uses net_transaction_amount if provided
    assert transaction.realized_gain_loss is None
    assert transaction.average_price is None
    mock_disposition_engine.add_buy_lot.assert_not_called()
    mock_disposition_engine.consume_sell_quantity.assert_not_called()
    assert cost_calculator._error_reporter.has_errors() is False

def test_default_strategy_calculate_costs_dividend(cost_calculator, mock_disposition_engine, dividend_transaction_data):
    """Test DefaultStrategy for a DIVIDEND transaction."""
    transaction = dividend_transaction_data
    cost_calculator.calculate_transaction_costs(transaction)

    assert transaction.gross_cost == Decimal("25.00")
    assert transaction.net_cost == Decimal("25.00") # Falls back to gross if net not provided
    assert transaction.realized_gain_loss is None
    assert transaction.average_price is None
    assert cost_calculator._error_reporter.has_errors() is False

# --- Test CostCalculator's dispatch logic ---
def test_cost_calculator_unknown_transaction_type(cost_calculator, error_reporter, unknown_transaction_data):
    """Test CostCalculator handles unknown transaction types and reports error."""
    transaction = unknown_transaction_data
    cost_calculator.calculate_transaction_costs(transaction)

    assert error_reporter.has_errors_for(transaction.transaction_id) is True
    assert "Unknown transaction type" in error_reporter.get_errors()[0].error_reason
    # Check that costs/gain/loss are not set or are default for errored transaction
    # Since the strategy is not found, the default strategy might not set these either.
    assert transaction.gross_cost is None # Default strategy handles this but it won't be called if type is unknown for mapping
    assert transaction.net_cost is None
    assert transaction.realized_gain_loss is None