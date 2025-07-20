# src/tests/integration/test_api_process_transactions.py

import pytest
from fastapi.testclient import TestClient
from src.api.main import app # Import the FastAPI app instance
from src.core.models.response import TransactionProcessingResponse
from src.core.enums.cost_method import CostMethod
from decimal import Decimal
from datetime import date
import json # NEW: Import json for custom encoder

# Helper function to serialize Decimal to string for JSON
def decimal_to_str(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    # Handle dicts and lists recursively
    if isinstance(obj, dict):
        return {k: decimal_to_str(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [decimal_to_str(elem) for elem in obj]
    return obj


@pytest.fixture(scope="module")
def client():
    """Provides a TestClient for the FastAPI application."""
    # Use 'with' statement for proper client lifecycle management
    with TestClient(app) as c:
        yield c

# Sample valid transaction data
def get_sample_buy_transaction(id="buy_new", qty=10.0, amount=1000.0, date_str="2023-01-05", brokerage_fee=5.0):
    return {
        "transaction_id": id,
        "portfolio_id": "P_INT_001",
        "instrument_id": "AAPL",
        "security_id": "SEC_AAPL",
        "transaction_type": "BUY",
        "transaction_date": f"{date_str}T00:00:00Z",
        "settlement_date": f"{date_str}T00:00:00Z",
        "quantity": qty,
        "gross_transaction_amount": amount,
        "fees": {"brokerage": brokerage_fee},
        "accrued_interest": 0.0,
        "trade_currency": "USD"
    }

def get_sample_sell_transaction(id="sell_new", qty=5.0, amount=800.0, date_str="2023-01-10", brokerage_fee=3.0):
    return {
        "transaction_id": id,
        "portfolio_id": "P_INT_001",
        "instrument_id": "AAPL",
        "security_id": "SEC_AAPL",
        "transaction_type": "SELL",
        "transaction_date": f"{date_str}T00:00:00Z",
        "settlement_date": f"{date_str}T00:00:00Z",
        "quantity": qty,
        "gross_transaction_amount": amount,
        "fees": {"brokerage": brokerage_fee},
        "accrued_interest": 0.0,
        "trade_currency": "USD"
    }

def get_sample_interest_transaction(id="interest_new", amount=10.0, date_str="2023-01-01"):
    return {
        "transaction_id": id,
        "portfolio_id": "P_INT_001",
        "instrument_id": "CASH",
        "security_id": "SEC_CASH",
        "transaction_type": "INTEREST",
        "transaction_date": f"{date_str}T00:00:00Z",
        "settlement_date": f"{date_str}T00:00:00Z",
        "quantity": 0.0,
        "gross_transaction_amount": amount,
        "trade_currency": "USD"
    }

# --- Test Cases ---

@pytest.mark.parametrize("cost_method", [CostMethod.FIFO, CostMethod.AVERAGE_COST])
def test_process_transactions_buy_only(client, cost_method, monkeypatch):
    """Test processing a single BUY transaction."""
    monkeypatch.setenv("COST_BASIS_METHOD", cost_method.value)

    request_body = {
        "existing_transactions": [],
        "new_transactions": [get_sample_buy_transaction()]
    }
    # MODIFIED: Convert Decimals to string for JSON serialization
    response = client.post("/api/v1/process", json=decimal_to_str(request_body)) 

    assert response.status_code == 200
    response_data = TransactionProcessingResponse(**response.json())
    assert len(response_data.processed_transactions) == 1
    assert len(response_data.errored_transactions) == 0

    processed_buy = response_data.processed_transactions[0]
    assert processed_buy.transaction_id == "buy_new"
    assert processed_buy.gross_cost == Decimal("1000.0")
    assert processed_buy.net_cost == Decimal("1005.0") # 1000 + 5 (fees)
    assert processed_buy.realized_gain_loss is None

@pytest.mark.parametrize("cost_method", [CostMethod.FIFO, CostMethod.AVERAGE_COST])
def test_process_transactions_sell_with_existing_holdings(client, cost_method, monkeypatch):
    """Test processing a SELL transaction with pre-existing holdings."""
    monkeypatch.setenv("COST_BASIS_METHOD", cost_method.value)

    # Existing buy: 10 shares @ 100 (net 105 per share)
    existing_buy = get_sample_buy_transaction(id="buy_existing", qty=10.0, amount=1000.0, date_str="2023-01-01", brokerage_fee=Decimal("5.0"))
    existing_buy["net_cost"] = Decimal("1050.0") # Simulate pre-calculated net cost for existing
    existing_buy["gross_cost"] = Decimal("1000.0")
    existing_buy["average_price"] = Decimal("105.0")

    # New sell: 5 shares @ 800
    new_sell = get_sample_sell_transaction(id="sell_new", qty=5.0, amount=800.0, date_str="2023-01-02")

    request_body = {
        "existing_transactions": [existing_buy],
        "new_transactions": [new_sell]
    }
    # MODIFIED: Convert Decimals to string for JSON serialization
    response = client.post("/api/v1/process", json=decimal_to_str(request_body)) 

    assert response.status_code == 200
    response_data = TransactionProcessingResponse(**response.json())
    assert len(response_data.processed_transactions) == 1
    assert len(response_data.errored_transactions) == 0

    processed_sell = response_data.processed_transactions[0]
    assert processed_sell.transaction_id == "sell_new"
    # Cost basis from existing buy (1050 / 10 = 105 per share)
    # Matched cost for 5 shares = 5 * 105 = 525
    # Realized Gain/Loss = Sell proceeds - Matched Cost = 800 - 525 = 275
    assert processed_sell.realized_gain_loss == Decimal("275.0")
    assert processed_sell.gross_cost == Decimal("-525.0") # Gross cost is matched cost (negative for sell)
    assert processed_sell.net_cost == Decimal("-525.0")   # Net cost is matched cost (negative for sell)


@pytest.mark.parametrize("cost_method", [CostMethod.FIFO, CostMethod.AVERAGE_COST])
def test_process_transactions_sell_insufficient_holdings(client, cost_method, monkeypatch):
    """Test processing a SELL transaction with insufficient holdings."""
    monkeypatch.setenv("COST_BASIS_METHOD", cost_method.value)

    # Existing buy: 1 share @ 100
    existing_buy = get_sample_buy_transaction(id="buy_existing", qty=1.0, amount=100.0, date_str="2023-01-01", brokerage_fee=Decimal("5.0"))
    existing_buy["net_cost"] = Decimal("105.0")
    existing_buy["gross_cost"] = Decimal("100.0")
    existing_buy["average_price"] = Decimal("100.0")

    # New sell: 5 shares (more than available)
    new_sell = get_sample_sell_transaction(id="sell_new", qty=5.0, amount=800.0, date_str="2023-01-02")

    request_body = {
        "existing_transactions": [existing_buy],
        "new_transactions": [new_sell]
    }
    # MODIFIED: Convert Decimals to string for JSON serialization
    response = client.post("/api/v1/process", json=decimal_to_str(request_body)) 

    assert response.status_code == 200
    response_data = TransactionProcessingResponse(**response.json())
    assert len(response_data.processed_transactions) == 0 # Should not be processed
    assert len(response_data.errored_transactions) == 1

    errored_sell = response_data.errored_transactions[0]
    assert errored_sell.transaction_id == "sell_new"
    assert "exceeds available holdings" in errored_sell.error_reason.lower()


def test_process_transactions_invalid_input_validation_error(client):
    """Test processing with an invalid new transaction (missing required field)."""
    invalid_buy_data = get_sample_buy_transaction()
    del invalid_buy_data["instrument_id"] # Remove required field

    request_body = {
        "existing_transactions": [],
        "new_transactions": [invalid_buy_data]
    }
    # MODIFIED: Convert Decimals to string for JSON serialization
    response = client.post("/api/v1/process", json=decimal_to_str(request_body)) 

    assert response.status_code == 200
    response_data = TransactionProcessingResponse(**response.json())
    assert len(response_data.processed_transactions) == 0
    assert len(response_data.errored_transactions) == 1

    errored_txn = response_data.errored_transactions[0]
    assert errored_txn.transaction_id == "buy_new"
    assert "field required" in errored_txn.error_reason.lower()


def test_process_transactions_mixed_valid_and_invalid_input(client):
    """Test processing a mix of valid and invalid new transactions."""
    valid_buy = get_sample_buy_transaction(id="buy_valid")
    invalid_sell = get_sample_sell_transaction(id="sell_invalid")
    del invalid_sell["quantity"] # Make it invalid

    request_body = {
        "existing_transactions": [],
        "new_transactions": [valid_buy, invalid_sell]
    }
    # MODIFIED: Convert Decimals to string for JSON serialization
    response = client.post("/api/v1/process", json=decimal_to_str(request_body)) 

    assert response.status_code == 200
    response_data = TransactionProcessingResponse(**response.json())
    assert len(response_data.processed_transactions) == 1
    assert response_data.processed_transactions[0].transaction_id == "buy_valid"
    
    assert len(response_data.errored_transactions) == 1
    assert response_data.errored_transactions[0].transaction_id == "sell_invalid"
    assert "field required" in response_data.errored_transactions[0].error_reason.lower()


@pytest.mark.parametrize("cost_method", [CostMethod.FIFO, CostMethod.AVERAGE_COST])
def test_process_transactions_complex_flow_fifo_vs_avco(client, cost_method, monkeypatch):
    """
    Test a more complex flow with multiple buys and sells,
    differentiating expected results based on FIFO vs. AVCO.
    """
    monkeypatch.setenv("COST_BASIS_METHOD", cost_method.value)

    # Existing Buys (unsorted by date for realism, sorter should handle)
    existing_transactions = [
        get_sample_buy_transaction(id="E_B1", qty=Decimal("10"), amount=Decimal("1000"), date_str="2023-01-01", brokerage_fee=Decimal("5.0")), # Cost 100/share
        get_sample_buy_transaction(id="E_B2", qty=Decimal("20"), amount=Decimal("2500"), date_str="2023-01-05", brokerage_fee=Decimal("5.0")), # Cost 125/share
        get_sample_buy_transaction(id="E_B3", qty=Decimal("5"), amount=Decimal("600"), date_str="2023-01-03", brokerage_fee=Decimal("5.0")), # Cost 120/share
    ]
    # Add net_cost to existing transactions for DispositionEngine initialization
    # In a real scenario, these would already have costs computed from previous runs
    # For FIFO: B1 (Jan 1, 10@100), B3 (Jan 3, 5@120), B2 (Jan 5, 20@125)
    existing_transactions[0]["net_cost"] = existing_transactions[0]["gross_transaction_amount"] + existing_transactions[0]["fees"]["brokerage"]
    existing_transactions[1]["net_cost"] = existing_transactions[1]["gross_transaction_amount"] + existing_transactions[1]["fees"]["brokerage"]
    existing_transactions[2]["net_cost"] = existing_transactions[2]["gross_transaction_amount"] + existing_transactions[2]["fees"]["brokerage"]


    # New transactions
    new_transactions = [
        get_sample_sell_transaction(id="N_S1", qty=Decimal("12"), amount=Decimal("1500"), date_str="2023-01-08"), # Sell 12 shares
        get_sample_buy_transaction(id="N_B4", qty=Decimal("15"), amount=Decimal("1600"), date_str="2023-01-10"), # Buy 15 shares @ ~106.67
        get_sample_sell_transaction(id="N_S2", qty=Decimal("20"), amount=Decimal("2200"), date_str="2023-01-12"), # Sell 20 shares
        get_sample_interest_transaction(id="N_I1", amount=Decimal("50"), date_str="2023-01-15") # Non-stock transaction
    ]

    request_body = {
        "existing_transactions": existing_transactions,
        "new_transactions": new_transactions
    }
    # MODIFIED: Convert Decimals to string for JSON serialization
    response = client.post("/api/v1/process", json=decimal_to_str(request_body)) 

    assert response.status_code == 200
    response_data = TransactionProcessingResponse(**response.json())
    assert len(response_data.errored_transactions) == 0

    processed_map = {txn.transaction_id: txn for txn in response_data.processed_transactions}
    assert len(processed_map) == len(new_transactions) # All new transactions should be processed

    # Verify N_I1 (Interest)
    assert processed_map["N_I1"].gross_cost == Decimal("50")
    assert processed_map["N_I1"].net_cost == Decimal("50")
    assert processed_map["N_I1"].realized_gain_loss is None

    # Verify N_S1 (Sell 12 shares)
    n_s1_processed = processed_map["N_S1"]
    if cost_method == CostMethod.FIFO:
        # FIFO: Consume 10 shares from E_B1 (cost 1000)
        # Then consume 2 shares from E_B3 (cost 2 * 120 = 240)
        # Total matched cost = 1000 + 240 = 1240
        # Gain/Loss = 1500 (proceeds) - 1240 = 260
        assert n_s1_processed.realized_gain_loss == Decimal("260.0")
        assert n_s1_processed.gross_cost == Decimal("-1240.0")
    elif cost_method == CostMethod.AVERAGE_COST:
        # Initial AVCO: Total Qty = 10+20+5 = 35. Total Cost = 1000+2500+600 = 4100
        # Avg Cost = 4100 / 35 = 117.142857...
        # Matched cost for 12 shares = 12 * (4100/35) = 1405.7142857...
        # Gain/Loss = 1500 - 1405.7142857 = 94.2857143
        expected_avco_gain_loss_ns1 = Decimal("1500") - (Decimal("12") * (Decimal("4100") / Decimal("35")))
        assert n_s1_processed.realized_gain_loss == expected_avco_gain_loss_ns1.quantize(Decimal('0.01')) # Quantize for comparison
        expected_avco_gross_cost_ns1 = -(Decimal("12") * (Decimal("4100") / Decimal("35")))
        assert n_s1_processed.gross_cost == expected_avco_gross_cost_ns1.quantize(Decimal('0.01'))
    
    # Verify N_S2 (Sell 20 shares)
    n_s2_processed = processed_map["N_S2"]
    if cost_method == CostMethod.FIFO:
        # FIFO:
        # Remaining holdings after N_S1: E_B3 (3 shares @ 120), E_B2 (20 shares @ 125)
        # E_B3 (3 shares from 5 original)
        # E_B2 (20 shares)
        # Sorted FIFO lots: E_B3_remaining (3@120), E_B2 (20@125), N_B4 (15@106.67) - N_B4 is processed after N_S1
        # Re-sort for FIFO: E_B3 (remaining 3@120), E_B2 (20@125), N_B4 (15@106.66666)

        # N_S1 consumed E_B1 (10@100) and 2 from E_B3 (2@120).
        # Remaining: E_B3: (5-2=3) at 120, E_B2: (20) at 125.
        # Then N_B4 added: 15@1600/15 = 106.66666...
        # So at N_S2 (Jan 12): lots are E_B3_rem (3@120), E_B2 (20@125), N_B4 (15@106.66666)
        # Consume 20 shares from lots:
        # - all 3 from E_B3 (3 * 120 = 360)
        # - then 17 from E_B2 (17 * 125 = 2125)
        # Total matched cost = 360 + 2125 = 2485
        # Gain/Loss = 2200 (proceeds) - 2485 = -285
        assert n_s2_processed.realized_gain_loss == Decimal("-285.0")
        assert n_s2_processed.gross_cost == Decimal("-2485.0")
    elif cost_method == CostMethod.AVERAGE_COST:
        # AVCO:
        # Initial: 35 shares @ 4100 cost (avg 117.142857...)
        # After N_S1 (sold 12 shares): Remaining 35-12 = 23 shares. Remaining cost = 4100 - (12 * 4100/35) = 4100 - 1405.7142857 = 2694.2857143
        # Then N_B4 (bought 15 shares @ 1600) added: Total Qty = 23+15 = 38. Total Cost = 2694.2857143 + 1600 = 4294.2857143
        # New Avg Cost = 4294.2857143 / 38 = 113.0075...
        # Matched cost for 20 shares = 20 * (4294.2857143 / 38) = 2260.15...
        # Gain/Loss = 2200 - 2260.15... = -60.15...
        
        # Helper for AVCO calculations from previous state
        initial_qty = Decimal(35)
        initial_cost = Decimal(4100)
        
        after_ns1_qty = initial_qty - Decimal(12)
        after_ns1_cost = initial_cost - (Decimal(12) * initial_cost / initial_qty)
        
        after_nb4_qty = after_ns1_qty + Decimal(15)
        after_nb4_cost = after_ns1_cost + Decimal(1600)
        
        expected_avco_matched_cost_ns2 = Decimal(20) * (after_nb4_cost / after_nb4_qty)
        expected_avco_gain_loss_ns2 = Decimal("2200") - expected_avco_matched_cost_ns2

        assert n_s2_processed.realized_gain_loss == expected_avco_gain_loss_ns2.quantize(Decimal('0.01'))
        assert n_s2_processed.gross_cost == -expected_avco_matched_cost_ns2.quantize(Decimal('0.01'))