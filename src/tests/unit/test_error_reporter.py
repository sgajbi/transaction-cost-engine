# src/tests/unit/test_error_reporter.py

import pytest
from src.logic.error_reporter import ErrorReporter
from src.core.models.response import ErroredTransaction

@pytest.fixture
def error_reporter():
    """Provides a fresh ErrorReporter instance for each test."""
    return ErrorReporter()

def test_add_error_single(error_reporter):
    """Test adding a single error."""
    transaction_id = "txn_001"
    error_reason = "Invalid quantity"
    error_reporter.add_error(transaction_id, error_reason)
    
    errors = error_reporter.get_errors()
    assert len(errors) == 1
    assert errors[0].transaction_id == transaction_id
    assert errors[0].error_reason == error_reason
    assert error_reporter.has_errors() is True
    assert error_reporter.has_errors_for(transaction_id) is True
    assert error_reporter.has_errors_for("non_existent_txn") is False

def test_add_error_multiple_different_transactions(error_reporter):
    """Test adding errors for multiple different transactions."""
    error_reporter.add_error("txn_001", "Invalid quantity")
    error_reporter.add_error("txn_002", "Missing required field")
    
    errors = error_reporter.get_errors()
    assert len(errors) == 2
    assert {e.transaction_id for e in errors} == {"txn_001", "txn_002"}
    assert error_reporter.has_errors() is True
    assert error_reporter.has_errors_for("txn_001") is True
    assert error_reporter.has_errors_for("txn_002") is True
    assert error_reporter.has_errors_for("txn_003") is False

def test_add_error_duplicate_id_appends_reason(error_reporter):
    """Test adding an error for an existing transaction ID appends the reason."""
    error_reporter.add_error("txn_001", "Invalid quantity")
    error_reporter.add_error("txn_001", "Insufficient funds")
    
    errors = error_reporter.get_errors()
    assert len(errors) == 1
    assert errors[0].transaction_id == "txn_001"
    assert errors[0].error_reason == "Invalid quantity; Insufficient funds"
    
def test_add_error_duplicate_id_does_not_append_same_reason(error_reporter):
    """Test adding the exact same reason for an existing ID does not append it again."""
    error_reporter.add_error("txn_001", "Invalid quantity")
    error_reporter.add_error("txn_001", "Invalid quantity")
    
    errors = error_reporter.get_errors()
    assert len(errors) == 1
    assert errors[0].transaction_id == "txn_001"
    assert errors[0].error_reason == "Invalid quantity"

def test_add_errored_transaction(error_reporter):
    """Test adding an already created ErroredTransaction object."""
    errored_txn = ErroredTransaction(transaction_id="txn_003", error_reason="Schema mismatch")
    error_reporter.add_errored_transaction(errored_txn)
    
    errors = error_reporter.get_errors()
    assert len(errors) == 1
    assert errors[0].transaction_id == "txn_003"
    assert errors[0].error_reason == "Schema mismatch"
    assert error_reporter.has_errors_for("txn_003") is True


def test_get_errors_empty(error_reporter):
    """Test getting errors when no errors have been added."""
    assert error_reporter.get_errors() == []
    assert error_reporter.has_errors() is False
    assert error_reporter.has_errors_for("any_txn") is False

def test_clear_errors(error_reporter):
    """Test clearing all collected errors."""
    error_reporter.add_error("txn_001", "Test error")
    assert error_reporter.has_errors() is True
    
    error_reporter.clear()
    assert error_reporter.get_errors() == []
    assert error_reporter.has_errors() is False
    assert error_reporter.has_errors_for("txn_001") is False

def test_has_errors_for_method(error_reporter):
    """Test has_errors_for method for existence of specific transaction errors."""
    error_reporter.add_error("txn_exists", "Some error")
    assert error_reporter.has_errors_for("txn_exists") is True
    assert error_reporter.has_errors_for("txn_non_existent") is False