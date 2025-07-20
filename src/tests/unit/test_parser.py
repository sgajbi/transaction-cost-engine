# src/tests/unit/test_parser.py

import pytest
from datetime import date
from decimal import Decimal

from src.logic.parser import TransactionParser
from src.logic.error_reporter import ErrorReporter
from src.core.models.transaction import Transaction
from src.core.models.response import ErroredTransaction # For checking ErrorReporter content

@pytest.fixture
def error_reporter():
    """Provides a fresh ErrorReporter instance for tests."""
    return ErrorReporter()

@pytest.fixture
def parser(error_reporter):
    """Provides a TransactionParser instance with an injected ErrorReporter."""
    return TransactionParser(error_reporter=error_reporter)

def get_base_valid_transaction_data():
    """Returns a dictionary for a valid transaction."""
    return {
        "transaction_id": "txn_valid_001",
        "portfolio_id": "PORT1",
        "instrument_id": "AAPL",
        "security_id": "SEC1",
        "transaction_type": "BUY",
        "transaction_date": "2023-01-01",
        "settlement_date": "2023-01-03",
        "quantity": 10.0,
        "gross_transaction_amount": 1500.0,
        "trade_currency": "USD"
    }

def test_parse_transactions_valid_single(parser, error_reporter):
    """Test successful parsing of a single valid transaction."""
    raw_data = [get_base_valid_transaction_data()]
    parsed_txns = parser.parse_transactions(raw_data)

    assert len(parsed_txns) == 1
    assert parsed_txns[0].transaction_id == "txn_valid_001"
    assert parsed_txns[0].transaction_date == date(2023, 1, 1)
    assert parsed_txns[0].quantity == Decimal("10.0")
    assert parsed_txns[0].error_reason is None # No error for valid txn
    assert error_reporter.has_errors() is False

def test_parse_transactions_valid_multiple(parser, error_reporter):
    """Test successful parsing of multiple valid transactions."""
    raw_data = [
        get_base_valid_transaction_data(),
        {
            "transaction_id": "txn_valid_002",
            "portfolio_id": "PORT2", "instrument_id": "MSFT", "security_id": "SEC2",
            "transaction_type": "SELL", "transaction_date": "2023-01-05", "settlement_date": "2023-01-07",
            "quantity": 5.0, "gross_transaction_amount": 1000.0, "trade_currency": "USD"
        }
    ]
    parsed_txns = parser.parse_transactions(raw_data)

    assert len(parsed_txns) == 2
    assert parsed_txns[0].transaction_id == "txn_valid_001"
    assert parsed_txns[0].error_reason is None
    assert parsed_txns[1].transaction_id == "txn_valid_002"
    assert parsed_txns[1].error_reason is None
    assert error_reporter.has_errors() is False

def test_parse_transactions_invalid_missing_field(parser, error_reporter):
    """Test parsing with a transaction missing a required field."""
    invalid_data = get_base_valid_transaction_data()
    del invalid_data["transaction_type"] # Remove a required field
    raw_data = [invalid_data]

    parsed_txns = parser.parse_transactions(raw_data)

    assert len(parsed_txns) == 1
    assert parsed_txns[0].transaction_id == "txn_valid_001" # ID is still present
    assert parsed_txns[0].error_reason is not None
    assert "field required" in parsed_txns[0].error_reason.lower() # Verify error reason is set

    errors_reported = error_reporter.get_errors()
    assert len(errors_reported) == 1
    assert errors_reported[0].transaction_id == "txn_valid_001"
    assert "field required" in errors_reported[0].error_reason.lower()
    assert error_reporter.has_errors_for("txn_valid_001") is True

def test_parse_transactions_invalid_type(parser, error_reporter):
    """Test parsing with a transaction having an incorrect data type."""
    invalid_data = get_base_valid_transaction_data()
    invalid_data["quantity"] = "ten" # Invalid type
    raw_data = [invalid_data]

    parsed_txns = parser.parse_transactions(raw_data)

    assert len(parsed_txns) == 1
    assert parsed_txns[0].transaction_id == "txn_valid_001"
    assert parsed_txns[0].error_reason is not None
    # MODIFIED ASSERTION: Make it less strict or match the current Pydantic message
    assert "input should be a valid decimal" in parsed_txns[0].error_reason.lower() # Verify error reason

    errors_reported = error_reporter.get_errors()
    assert len(errors_reported) == 1
    assert errors_reported[0].transaction_id == "txn_valid_001"
    assert "input should be a valid decimal" in errors_reported[0].error_reason.lower()

def test_parse_transactions_mixed_valid_and_invalid(parser, error_reporter):
    """Test parsing a mix of valid and invalid transactions."""
    valid_data = get_base_valid_transaction_data()
    
    invalid_data = get_base_valid_transaction_data()
    invalid_data["transaction_id"] = "txn_invalid_001"
    del invalid_data["portfolio_id"] # Make it invalid

    raw_data = [valid_data, invalid_data]
    parsed_txns = parser.parse_transactions(raw_data)

    assert len(parsed_txns) == 2
    # Check valid transaction
    assert parsed_txns[0].transaction_id == "txn_valid_001"
    assert parsed_txns[0].error_reason is None
    # Check invalid transaction
    assert parsed_txns[1].transaction_id == "txn_invalid_001"
    assert parsed_txns[1].error_reason is not None
    assert "field required" in parsed_txns[1].error_reason.lower()

    errors_reported = error_reporter.get_errors()
    assert len(errors_reported) == 1
    assert errors_reported[0].transaction_id == "txn_invalid_001"
    assert "field required" in errors_reported[0].error_reason.lower()
    assert error_reporter.has_errors_for("txn_invalid_001") is True


def test_parse_transactions_unexpected_exception(parser, error_reporter, mocker):
    """Test parsing handles an unexpected general exception."""
    # Mock Pydantic's internal validation to raise a generic exception
    mocker.patch.object(parser._single_transaction_adapter, 'validate_python', side_effect=Exception("Simulated unexpected error"))

    raw_data = [get_base_valid_transaction_data()]
    parsed_txns = parser.parse_transactions(raw_data)

    assert len(parsed_txns) == 1
    assert parsed_txns[0].transaction_id == "txn_valid_001" # ID is from initial data
    assert parsed_txns[0].error_reason is not None
    assert "unexpected parsing error" in parsed_txns[0].error_reason.lower()

    errors_reported = error_reporter.get_errors()
    assert len(errors_reported) == 1
    assert errors_reported[0].transaction_id == "txn_valid_001"
    assert "unexpected parsing error" in errors_reported[0].error_reason.lower()
    assert error_reporter.has_errors_for("txn_valid_001") is True

def test_parse_transactions_empty_list(parser, error_reporter):
    """Test parsing an empty list."""
    parsed_txns = parser.parse_transactions([])
    assert len(parsed_txns) == 0
    assert error_reporter.has_errors() is False

def test_parse_transactions_handles_missing_transaction_id_and_other_required_fields(parser, error_reporter):
    """Test parsing a transaction where transaction_id and other required fields are missing."""
    raw_data = [{
        "portfolio_id": "P1", "instrument_id": "A", "security_id": "S1",
        "transaction_type": "BUY", "transaction_date": "2023-01-01", "settlement_date": "2023-01-03",
        "quantity": 10.0, "gross_transaction_amount": 100.0, "trade_currency": "USD"
    }]
    parsed_txns = parser.parse_transactions(raw_data)

    assert len(parsed_txns) == 1
    # For a missing transaction_id, the parser now uses "UNKNOWN_ID_AFTER_PARSE_FAIL" for the stub
    assert parsed_txns[0].transaction_id == "UNKNOWN_ID_AFTER_PARSE_FAIL" 
    assert parsed_txns[0].error_reason is not None
    assert "field required" in parsed_txns[0].error_reason.lower() # Error for transaction_id

    errors_reported = error_reporter.get_errors()
    assert len(errors_reported) == 1
    # The ErrorReporter receives "UNKNOWN_ID_BEFORE_PARSE" if transaction_id was truly not in raw_data,
    # before the stub is created.
    assert errors_reported[0].transaction_id == "UNKNOWN_ID_BEFORE_PARSE" 
    assert "field required" in errors_reported[0].error_reason.lower()