# src/tests/unit/test_disposition_engine.py

import pytest
from datetime import date
from decimal import Decimal, getcontext

from src.logic.disposition_engine import DispositionEngine
from src.logic.cost_basis_strategies import FIFOBasisStrategy, AverageCostBasisStrategy
from src.core.models.transaction import Transaction
from src.core.enums.transaction_type import TransactionType

# Set the same precision as the application for consistent testing
getcontext().prec = 10 

@pytest.fixture
def fifo_engine():
    """Provides a DispositionEngine configured with FIFOBasisStrategy."""
    return DispositionEngine(cost_basis_strategy=FIFOBasisStrategy())

@pytest.fixture
def avco_engine():
    """Provides a DispositionEngine configured with AverageCostBasisStrategy."""
    return DispositionEngine(cost_basis_strategy=AverageCostBasisStrategy())

@pytest.fixture
def buy_transactions():
    """Provides mock BUY transactions with net_cost pre-calculated."""
    return [
        Transaction(transaction_id="B1", portfolio_id="P1", instrument_id="A", security_id="S1",
                    transaction_type=TransactionType.BUY, transaction_date=date(2023, 1, 1), settlement_date=date(2023, 1, 3),
                    quantity=Decimal("10"), gross_transaction_amount=Decimal("100"), net_cost=Decimal("100")), # Cost per share 10
        Transaction(transaction_id="B2", portfolio_id="P1", instrument_id="A", security_id="S1",
                    transaction_type=TransactionType.BUY, transaction_date=date(2023, 1, 5), settlement_date=date(2023, 1, 7),
                    quantity=Decimal("20"), gross_transaction_amount=Decimal("300"), net_cost=Decimal("300")), # Cost per share 15
        Transaction(transaction_id="B3", portfolio_id="P1", instrument_id="B", security_id="S2",
                    transaction_type=TransactionType.BUY, transaction_date=date(2023, 1, 2), settlement_date=date(2023, 1, 4),
                    quantity=Decimal("5"), gross_transaction_amount=Decimal("50"), net_cost=Decimal("50")), # Cost per share 10
    ]

@pytest.fixture
def sell_transactions():
    """Provides mock SELL transactions."""
    return [
        Transaction(transaction_id="S1", portfolio_id="P1", instrument_id="A", security_id="S1",
                    transaction_type=TransactionType.SELL, transaction_date=date(2023, 1, 10), settlement_date=date(2023, 1, 12),
                    quantity=Decimal("15"), gross_transaction_amount=Decimal("250")),
        Transaction(transaction_id="S2", portfolio_id="P1", instrument_id="A", security_id="S1",
                    transaction_type=TransactionType.SELL, transaction_date=date(2023, 1, 15), settlement_date=date(2023, 1, 17),
                    quantity=Decimal("20"), gross_transaction_amount=Decimal("400")),
    ]

# --- Common Tests for Both Strategies (via DispositionEngine) ---

def test_add_buy_lot(fifo_engine, avco_engine, buy_transactions):
    """Test adding a buy lot to both engines and check available quantity."""
    buy_tx = buy_transactions[0] # B1: qty 10, net_cost 100
    fifo_engine.add_buy_lot(buy_tx)
    avco_engine.add_buy_lot(buy_tx)

    assert fifo_engine.get_available_quantity("P1", "A") == Decimal("10")
    assert avco_engine.get_available_quantity("P1", "A") == Decimal("10")

def test_set_initial_lots(fifo_engine, avco_engine, buy_transactions):
    """Test setting initial lots for both engines."""
    initial_buys = [buy_transactions[0], buy_transactions[1]] # B1, B2
    fifo_engine.set_initial_lots(initial_buys)
    avco_engine.set_initial_lots(initial_buys)

    # Check available quantities after initialization
    assert fifo_engine.get_available_quantity("P1", "A") == Decimal("30") # 10 + 20
    assert avco_engine.get_available_quantity("P1", "A") == Decimal("30")

    # Verify other portfolio/instrument is not affected
    assert fifo_engine.get_available_quantity("P1", "B") == Decimal("0")
    assert avco_engine.get_available_quantity("P1", "B") == Decimal("0")


def test_get_available_quantity_no_holdings(fifo_engine, avco_engine):
    """Test getting available quantity for a non-existent holding."""
    assert fifo_engine.get_available_quantity("P_NonExistent", "I_NonExistent") == Decimal("0")
    assert avco_engine.get_available_quantity("P_NonExistent", "I_NonExistent") == Decimal("0")

# --- FIFO Specific Tests (via DispositionEngine) ---

def test_consume_sell_quantity_fifo_exact_match(fifo_engine, buy_transactions, sell_transactions):
    """Test FIFO sell where quantity exactly matches one lot."""
    fifo_engine.add_buy_lot(buy_transactions[0]) # B1: qty 10, cost 100 (avg 10)
    sell_tx = sell_transactions[0] # S1: qty 15
    sell_tx.quantity = Decimal("10") # Set to exact match quantity

    matched_cost, consumed_qty, error_reason = fifo_engine.consume_sell_quantity(sell_tx)
    
    assert error_reason is None
    assert consumed_qty == Decimal("10")
    assert matched_cost == Decimal("100") # Cost of B1
    assert fifo_engine.get_available_quantity("P1", "A") == Decimal("0")

def test_consume_sell_quantity_fifo_partial_and_full_match(fifo_engine, buy_transactions, sell_transactions):
    """Test FIFO sell where quantity consumes multiple lots."""
    fifo_engine.add_buy_lot(buy_transactions[0]) # B1: qty 10, cost 100 (avg 10)
    fifo_engine.add_buy_lot(buy_transactions[1]) # B2: qty 20, cost 300 (avg 15)
    
    sell_tx = sell_transactions[0] # S1: qty 15
    # Should consume all of B1 (10 @ 10) and 5 from B2 (5 @ 15)

    matched_cost, consumed_qty, error_reason = fifo_engine.consume_sell_quantity(sell_tx)
    
    assert error_reason is None
    assert consumed_qty == Decimal("15")
    assert matched_cost == (Decimal("10") * Decimal("10")) + (Decimal("5") * Decimal("15")) # 100 + 75 = 175
    assert matched_cost == Decimal("175")
    assert fifo_engine.get_available_quantity("P1", "A") == Decimal("15") # Remaining from B2 (20-5=15)

def test_consume_sell_quantity_fifo_insufficient_holdings(fifo_engine, buy_transactions, sell_transactions):
    """Test FIFO sell with insufficient holdings."""
    fifo_engine.add_buy_lot(buy_transactions[0]) # B1: qty 10, cost 100
    sell_tx = sell_transactions[1] # S2: qty 20 (more than available)

    matched_cost, consumed_qty, error_reason = fifo_engine.consume_sell_quantity(sell_tx)
    
    assert error_reason is not None
    assert "exceeds available holdings" in error_reason
    assert consumed_qty == Decimal("0")
    assert matched_cost == Decimal("0")
    assert fifo_engine.get_available_quantity("P1", "A") == Decimal("10") # Holdings should be unchanged

# --- Average Cost Specific Tests (via DispositionEngine) ---

def test_consume_sell_quantity_avco_single_buy(avco_engine, buy_transactions, sell_transactions):
    """Test AVCO sell after a single buy."""
    avco_engine.add_buy_lot(buy_transactions[0]) # B1: qty 10, cost 100 (avg 10)
    sell_tx = sell_transactions[0] # S1: qty 15
    sell_tx.quantity = Decimal("5") # Sell 5

    matched_cost, consumed_qty, error_reason = avco_engine.consume_sell_quantity(sell_tx)
    
    assert error_reason is None
    assert consumed_qty == Decimal("5")
    assert matched_cost == Decimal("5") * Decimal("10") # 5 * (100/10) = 50
    assert matched_cost == Decimal("50")
    assert avco_engine.get_available_quantity("P1", "A") == Decimal("5") # 10 - 5 = 5

def test_consume_sell_quantity_avco_multiple_buys(avco_engine, buy_transactions, sell_transactions):
    """Test AVCO sell after multiple buys, recalculating average cost."""
    avco_engine.add_buy_lot(buy_transactions[0]) # B1: qty 10, cost 100
    avco_engine.add_buy_lot(buy_transactions[1]) # B2: qty 20, cost 300
    # Total: qty 30, cost 400. Average cost = 400/30 = 13.3333...

    sell_tx = sell_transactions[0] # S1: qty 15

    matched_cost, consumed_qty, error_reason = avco_engine.consume_sell_quantity(sell_tx)
    
    assert error_reason is None
    assert consumed_qty == Decimal("15")
    # 15 * (400/30) = 15 * 13.333333333 = 200
    assert matched_cost == Decimal("200") 
    assert avco_engine.get_available_quantity("P1", "A") == Decimal("15") # 30 - 15 = 15
    # Remaining cost should be 400 - 200 = 200. Average should still be 200/15 = 13.3333...

def test_consume_sell_quantity_avco_insufficient_holdings(avco_engine, buy_transactions, sell_transactions):
    """Test AVCO sell with insufficient holdings."""
    avco_engine.add_buy_lot(buy_transactions[0]) # B1: qty 10, cost 100
    sell_tx = sell_transactions[1] # S2: qty 20 (more than available)

    matched_cost, consumed_qty, error_reason = avco_engine.consume_sell_quantity(sell_tx)
    
    assert error_reason is not None
    assert "exceeds available average cost holdings" in error_reason
    assert consumed_qty == Decimal("0")
    assert matched_cost == Decimal("0")
    assert avco_engine.get_available_quantity("P1", "A") == Decimal("10") # Holdings should be unchanged

def test_get_all_open_lots_fifo_specific(fifo_engine, buy_transactions):
    """Test get_all_open_lots for FIFO, checking internal state."""
    fifo_engine.add_buy_lot(buy_transactions[0]) # B1
    fifo_engine.add_buy_lot(buy_transactions[1]) # B2
    
    all_lots = fifo_engine.get_all_open_lots()
    assert ("P1", "A") in all_lots
    assert len(all_lots[("P1", "A")]) == 2
    assert all_lots[("P1", "A")][0].transaction_id == "B1"
    assert all_lots[("P1", "A")][1].transaction_id == "B2"
    assert all_lots[("P1", "A")][0].remaining_quantity == Decimal("10") # Check remaining quantity

def test_get_all_open_lots_avco_not_applicable(avco_engine):
    """Test get_all_open_lots raises NotImplementedError for AVCO."""
    with pytest.raises(NotImplementedError) as excinfo:
        avco_engine.get_all_open_lots()
    assert "get_all_open_lots is not applicable for AverageCostBasisStrategy" in str(excinfo.value)