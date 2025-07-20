# src/tests/unit/test_sorter.py

import pytest
from datetime import date
from decimal import Decimal

from src.core.models.transaction import Transaction
from src.logic.sorter import TransactionSorter

@pytest.fixture
def sorter():
    """Provides a TransactionSorter instance for tests."""
    return TransactionSorter()

@pytest.fixture
def mock_transactions():
    """Provides a set of mock Transaction objects for testing."""
    return [
        # Existing transactions
        Transaction(
            transaction_id="exist_001", portfolio_id="P1", instrument_id="A", security_id="S1",
            transaction_type="BUY", transaction_date=date(2023, 1, 5), settlement_date=date(2023, 1, 7),
            quantity=Decimal("10.0"), gross_transaction_amount=Decimal("100.0"), trade_currency="USD"
        ),
        Transaction(
            transaction_id="exist_002", portfolio_id="P1", instrument_id="B", security_id="S2",
            transaction_type="BUY", transaction_date=date(2023, 1, 1), settlement_date=date(2023, 1, 3),
            quantity=Decimal("5.0"), gross_transaction_amount=Decimal("50.0"), trade_currency="USD"
        ),
        Transaction(
            transaction_id="exist_003", portfolio_id="P1", instrument_id="A", security_id="S1",
            transaction_type="SELL", transaction_date=date(2023, 1, 10), settlement_date=date(2023, 1, 12),
            quantity=Decimal("3.0"), gross_transaction_amount=Decimal("30.0"), trade_currency="USD"
        ),
        # New transactions
        Transaction(
            transaction_id="new_001", portfolio_id="P1", instrument_id="C", security_id="S3",
            transaction_type="BUY", transaction_date=date(2023, 1, 8), settlement_date=date(2023, 1, 10),
            quantity=Decimal("20.0"), gross_transaction_amount=Decimal("200.0"), trade_currency="USD"
        ),
        Transaction(
            transaction_id="new_002", portfolio_id="P1", instrument_id="A", security_id="S1",
            transaction_type="BUY", transaction_date=date(2023, 1, 5), settlement_date=date(2023, 1, 7),
            quantity=Decimal("15.0"), gross_transaction_amount=Decimal("150.0"), trade_currency="USD"
        ), # Same date as exist_001, but higher quantity for secondary sort test
        Transaction(
            transaction_id="new_003", portfolio_id="P1", instrument_id="D", security_id="S4",
            transaction_type="SELL", transaction_date=date(2023, 1, 1), settlement_date=date(2023, 1, 3),
            quantity=Decimal("2.0"), gross_transaction_amount=Decimal("20.0"), trade_currency="USD"
        ) # Same date as exist_002, lower quantity (should come after exist_002)
    ]

def test_sort_transactions_empty_lists(sorter):
    """Test sorting with empty existing and new transaction lists."""
    sorted_txns = sorter.sort_transactions([], [])
    assert len(sorted_txns) == 0

def test_sort_transactions_only_existing(sorter, mock_transactions):
    """Test sorting with only existing transactions."""
    existing = [mock_transactions[0], mock_transactions[2], mock_transactions[1]] # Unsorted
    sorted_txns = sorter.sort_transactions(existing, [])
    
    # Expected order: exist_002 (Jan 1, qty 5), exist_001 (Jan 5, qty 10), exist_003 (Jan 10, qty 3)
    assert sorted_txns[0].transaction_id == "exist_002"
    assert sorted_txns[1].transaction_id == "exist_001"
    assert sorted_txns[2].transaction_id == "exist_003"
    assert len(sorted_txns) == 3

def test_sort_transactions_only_new(sorter, mock_transactions):
    """Test sorting with only new transactions."""
    new = [mock_transactions[4], mock_transactions[3], mock_transactions[5]] # Unsorted
    sorted_txns = sorter.sort_transactions([], new)
    
    # Expected order: new_003 (Jan 1, qty 2), new_002 (Jan 5, qty 15), new_001 (Jan 8, qty 20)
    assert sorted_txns[0].transaction_id == "new_003"
    assert sorted_txns[1].transaction_id == "new_002"
    assert sorted_txns[2].transaction_id == "new_001"
    assert len(sorted_txns) == 3

def test_sort_transactions_mixed_lists(sorter, mock_transactions):
    """Test sorting with mixed existing and new transactions."""
    existing = [mock_transactions[0], mock_transactions[1]] # exist_001 (Jan 5), exist_002 (Jan 1)
    new = [mock_transactions[3], mock_transactions[4]] # new_001 (Jan 8), new_002 (Jan 5)

    sorted_txns = sorter.sort_transactions(existing, new)

    # Expected order:
    # 1. exist_002 (Jan 1, qty 5)
    # 2. new_002 (Jan 5, qty 15) - larger quantity than exist_001 on same date
    # 3. exist_001 (Jan 5, qty 10) - smaller quantity than new_002 on same date
    # 4. new_001 (Jan 8, qty 20)
    assert sorted_txns[0].transaction_id == "exist_002"
    assert sorted_txns[1].transaction_id == "new_002"
    assert sorted_txns[2].transaction_id == "exist_001"
    assert sorted_txns[3].transaction_id == "new_001"
    assert len(sorted_txns) == 4

def test_sort_transactions_same_date_different_quantity(sorter):
    """Test secondary sort by quantity (descending) for transactions on the same date."""
    txn1 = Transaction(
        transaction_id="txn1", portfolio_id="P1", instrument_id="A", security_id="S1",
        transaction_type="BUY", transaction_date=date(2023, 2, 1), settlement_date=date(2023, 2, 3),
        quantity=Decimal("10.0"), gross_transaction_amount=Decimal("100.0"), trade_currency="USD"
    )
    txn2 = Transaction(
        transaction_id="txn2", portfolio_id="P1", instrument_id="A", security_id="S1",
        transaction_type="BUY", transaction_date=date(2023, 2, 1), settlement_date=date(2023, 2, 3),
        quantity=Decimal("20.0"), gross_transaction_amount=Decimal("200.0"), trade_currency="USD"
    )
    txn3 = Transaction(
        transaction_id="txn3", portfolio_id="P1", instrument_id="A", security_id="S1",
        transaction_type="SELL", transaction_date=date(2023, 2, 1), settlement_date=date(2023, 2, 3),
        quantity=Decimal("5.0"), gross_transaction_amount=Decimal("50.0"), trade_currency="USD"
    )

    transactions = [txn1, txn3, txn2] # Deliberately unsorted input
    sorted_txns = sorter.sort_transactions([], transactions) # Pass as new transactions

    # Expected order: txn2 (qty 20), txn1 (qty 10), txn3 (qty 5)
    assert sorted_txns[0].transaction_id == "txn2"
    assert sorted_txns[1].transaction_id == "txn1"
    assert sorted_txns[2].transaction_id == "txn3"
    assert len(sorted_txns) == 3