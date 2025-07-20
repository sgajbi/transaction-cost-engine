# src/tests/integration/test_api_process_transactions.py

import pytest
from fastapi.testclient import TestClient
from src.api.main import app # Import the FastAPI app instance
from src.core.models.response import TransactionProcessingResponse
from src.core.enums.cost_method import CostMethod
from decimal import Decimal
from datetime import date
import json

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
    with TestClient(app) as c:
        yield c

# Sample valid transaction data
def get_sample_buy_transaction(id="buy_new", qty=Decimal("10.0"), amount=Decimal("1000.0"), date_str="2023-01-05", brokerage_fee=Decimal("5.0")):
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
        "accrued_interest": Decimal("0.0"),
        "trade_currency": "USD"
    }

def get_sample_sell_transaction(id="sell_new", qty=Decimal("5.0"), amount=Decimal("800.0"), date_str="2023-01-10", brokerage_fee=Decimal("3.0")):
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
        "accrued_interest": Decimal("0.0"),
        "trade_currency": "USD"
    }

def get_sample_interest_transaction(id="interest_new", amount=Decimal("10.0"), date_str="2023-01-01"):
    return {
        "transaction_id": id,
        "portfolio_id": "P_INT_001",
        "instrument_id": "CASH",
        "security_id": "SEC_CASH",
        "transaction_type": "INTEREST",
        "transaction_date": f"{date_str}T00:00:00Z",
        "settlement_date": f"{date_str}T00:00:00Z",
        "quantity": Decimal("0.0"),
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
    existing_buy = get_sample_buy_transaction(id="buy_existing", qty=Decimal("10.0"), amount=Decimal("1000.0"), date_str="2023-01-01", brokerage_fee=Decimal("5.0"))
    existing_buy["net_cost"] = Decimal("1050.0") # Simulate pre-calculated net cost for existing
    existing_buy["gross_cost"] = Decimal("1000.0")
    existing_buy["average_price"] = Decimal("105.0")

    # New sell: 5 shares @ 800
    new_sell = get_sample_sell_transaction(id="sell_new", qty=Decimal("5.0"), amount=Decimal("800.0"), date_str="2023-01-02")

    request_body = {
        "existing_transactions": [existing_buy],
        "new_transactions": [new_sell]
    }
    response = client.post("/api/v1/process", json=decimal_to_str(request_body)) 

    assert response.status_code == 200
    response_data = TransactionProcessingResponse(**response.json())
    assert len(response_data.processed_transactions) == 1
    assert len(response_data.errored_transactions) == 0

    processed_sell = response_data.processed_transactions[0]
    assert processed_sell.transaction_id == "sell_new"
    # Cost basis from existing buy (1050 / 10 = 105 per share)
    # Matched cost for 5 shares = 5 * 105 = 525
    # Realized Gain/Loss = Sell proceeds (800) - Matched Cost (525) - Sell Fees (3.0) = 800 - 525 - 3 = 272
    assert processed_sell.realized_gain_loss == Decimal("272.0")
    assert processed_sell.gross_cost == Decimal("-525.0")
    assert processed_sell.net_cost == Decimal("-525.0")


@pytest.mark.parametrize("cost_method", [CostMethod.FIFO, CostMethod.AVERAGE_COST])
def test_process_transactions_sell_insufficient_holdings(client, cost_method, monkeypatch):
    """Test processing a SELL transaction with insufficient holdings."""
    monkeypatch.setenv("COST_BASIS_METHOD", cost_method.value)

    # Existing buy: 1 share @ 100
    existing_buy = get_sample_buy_transaction(id="buy_existing", qty=Decimal("1.0"), amount=Decimal("100.0"), date_str="2023-01-01", brokerage_fee=Decimal("5.0"))
    existing_buy["net_cost"] = Decimal("105.0")
    existing_buy["gross_cost"] = Decimal("100.0")
    existing_buy["average_price"] = Decimal("100.0")

    # New sell: 5 shares (more than available)
    new_sell = get_sample_sell_transaction(id="sell_new", qty=Decimal("5.0"), amount=Decimal("800.0"), date_str="2023-01-02")

    request_body = {
        "existing_transactions": [existing_buy],
        "new_transactions": [new_sell]
    }
    response = client.post("/api/v1/process", json=decimal_to_str(request_body)) 

    assert response.status_code == 200
    response_data = TransactionProcessingResponse(**response.json())
    assert len(response_data.processed_transactions) == 0
    assert len(response_data.errored_transactions) == 1

    errored_sell = response_data.errored_transactions[0]
    assert errored_sell.transaction_id == "sell_new"
    # MODIFIED: Make assertion more robust against exact string changes
    assert "exceeds available" in errored_sell.error_reason.lower() and "holdings" in errored_sell.error_reason.lower()


def test_process_transactions_invalid_input_validation_error(client):
    """Test processing with an invalid new transaction (missing required field)."""
    invalid_buy_data = get_sample_buy_transaction()
    del invalid_buy_data["instrument_id"] # Remove required field

    request_body = {
        "existing_transactions": [],
        "new_transactions": [invalid_buy_data]
    }
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
    # Create base transactions as dictionaries
    existing_tx_data_base = [
        get_sample_buy_transaction(id="E_B1", qty=Decimal("10"), amount=Decimal("1000"), date_str="2023-01-01", brokerage_fee=Decimal("5.0")), # Gross 1000, Fees 5.0
        get_sample_buy_transaction(id="E_B2", qty=Decimal("20"), amount=Decimal("2500"), date_str="2023-01-05", brokerage_fee=Decimal("5.0")), # Gross 2500, Fees 5.0
        get_sample_buy_transaction(id="E_B3", qty=Decimal("5"), amount=Decimal("600"), date_str="2023-01-03", brokerage_fee=Decimal("5.0")), # Gross 600, Fees 5.0
    ]
    
    # Deep copy and then calculate net_cost for existing transactions
    # This ensures each existing_transaction dict is independent and its net_cost is correctly calculated based on its own amounts/fees
    existing_transactions = []
    for txn_data in existing_tx_data_base:
        txn_copy = dict(txn_data) # Shallow copy is enough for top-level dict
        txn_copy["net_cost"] = txn_copy["gross_transaction_amount"] + txn_copy["fees"]["brokerage"]
        txn_copy["gross_cost"] = txn_copy["gross_transaction_amount"] # Gross cost for existing is its gross amount
        txn_copy["average_price"] = txn_copy["net_cost"] / txn_copy["quantity"]
        existing_transactions.append(txn_copy)


    # New transactions
    new_transactions = [
        get_sample_sell_transaction(id="N_S1", qty=Decimal("12"), amount=Decimal("1500"), date_str="2023-01-08", brokerage_fee=Decimal("3.0")), # Sell 12 shares
        get_sample_buy_transaction(id="N_B4", qty=Decimal("15"), amount=Decimal("1600"), date_str="2023-01-10", brokerage_fee=Decimal("5.0")), # Buy 15 shares @ ~106.67
        get_sample_sell_transaction(id="N_S2", qty=Decimal("20"), amount=Decimal("2200"), date_str="2023-01-12", brokerage_fee=Decimal("3.0")), # Sell 20 shares
        get_sample_interest_transaction(id="N_I1", amount=Decimal("50"), date_str="2023-01-15") # Non-stock transaction
    ]

    request_body = {
        "existing_transactions": existing_transactions,
        "new_transactions": new_transactions
    }
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
        # FIFO:
        # Existing Lots (sorted by date, then quantity, then fees/cost): E_B1 (10@100.5), E_B3 (5@121), E_B2 (20@125.25)
        # Sell 12 shares:
        # - Consume 10 shares from E_B1: cost = 10 * 100.5 = 1005.0
        # - Consume 2 shares from E_B3: cost = 2 * 121.0 = 242.0
        # Total matched cost = 1005.0 + 242.0 = 1247.0
        # Gain/Loss = 1500 (gross proceeds) - 1247.0 (matched cost) - 3.0 (sell fees) = 250.0
        assert n_s1_processed.realized_gain_loss == Decimal("250.0")
        assert n_s1_processed.gross_cost == Decimal("-1247.0")
    elif cost_method == CostMethod.AVERAGE_COST:
        # Initial AVCO:
        # E_B1 net_cost: 1005.0 (10 shares)
        # E_B2 net_cost: 2505.0 (20 shares)
        # E_B3 net_cost: 605.0 (5 shares)
        # Total Qty = 10+20+5 = 35. Total Cost = 1005.0 + 2505.0 + 605.0 = 4115.0
        # Avg Cost = 4115.0 / 35 = 117.57142857...
        # Matched cost for 12 shares = 12 * (4115.0 / 35) = 1416.857142857...
        # Gain/Loss = 1500 (gross proceeds) - 1416.857142857 (matched cost) - 3.0 (sell fees) = 80.142857143...
        expected_avco_gain_loss_ns1 = Decimal("1500") - (Decimal("12") * (Decimal("4115.0") / Decimal("35"))) - Decimal("3.0")
        assert n_s1_processed.realized_gain_loss.quantize(Decimal('0.01')) == expected_avco_gain_loss_ns1.quantize(Decimal('0.01'))
        expected_avco_gross_cost_ns1 = -(Decimal("12") * (Decimal("4115.0") / Decimal("35")))
        assert n_s1_processed.gross_cost.quantize(Decimal('0.01')) == expected_avco_gross_cost_ns1.quantize(Decimal('0.01'))
    
    # Verify N_S2 (Sell 20 shares)
    n_s2_processed = processed_map["N_S2"]
    if cost_method == CostMethod.FIFO:
        # FIFO:
        # Initial lots: E_B1 (10@100.5), E_B3 (5@121), E_B2 (20@125.25)
        # After N_S1 (Sell 12 shares):
        # - E_B1 fully consumed (10 shares)
        # - E_B3 partially consumed (2 shares from 5 total). Remaining E_B3: 3 shares @ 121.0
        # Remaining FIFO lots (sorted by date): E_B3_rem (3@121.0), E_B2 (20@125.25)
        # Then N_B4 (Buy 15 shares, Net Cost: 1600 + 5 = 1605.0. Cost/share = 1605.0/15 = 107.0) is added.
        # FIFO lots at N_S2: E_B3_rem (3@121.0), E_B2 (20@125.25), N_B4 (15@107.0)
        # Consume 20 shares for N_S2 (Sell 20):
        # - All 3 from E_B3_rem: cost = 3 * 121.0 = 363.0
        # - Remaining 17 shares from E_B2: cost = 17 * 125.25 = 2129.25
        # Total matched cost = 363.0 + 2129.25 = 2492.25
        # Gain/Loss = 2200 (gross proceeds) - 2492.25 (matched cost) - 3.0 (sell fees) = -295.25
        assert n_s2_processed.realized_gain_loss == Decimal("-295.25")
        assert n_s2_processed.gross_cost == Decimal("-2492.25")
    elif cost_method == CostMethod.AVERAGE_COST:
        # AVCO:
        # Initial: Total Qty = 35. Total Cost = 4115.0
        # After N_S1 (sold 12 shares):
        # Qty = 35 - 12 = 23
        # Cost = 4115.0 - (12 * 4115.0 / 35) = 4115.0 - 1416.857142857 = 2698.142857143
        # Then N_B4 (bought 15 shares @ 1600 net 1605.0) added:
        # Total Qty = 23 + 15 = 38
        # Total Cost = 2698.142857143 + 1605.0 = 4303.142857143
        # New Avg Cost = 4303.142857143 / 38 = 113.2406015...
        # Matched cost for 20 shares = 20 * (4303.142857143 / 38) = 2264.811867...
        # Gain/Loss = 2200 (gross proceeds) - 2264.811867 (matched cost) - 3.0 (sell fees) = -67.811867...
        
        # Helper for AVCO calculations from previous state
        initial_qty = Decimal(35)
        initial_cost = Decimal("4115.0")
        
        after_ns1_qty = initial_qty - Decimal(12)
        after_ns1_cost = initial_cost - (Decimal(12) * initial_cost / initial_qty)
        
        after_nb4_qty = after_ns1_qty + Decimal(15)
        after_nb4_cost = after_ns1_cost + Decimal("1605.0")
        
        expected_avco_matched_cost_ns2 = Decimal(20) * (after_nb4_cost / after_nb4_qty)
        expected_avco_gain_loss_ns2 = Decimal("2200") - expected_avco_matched_cost_ns2 - Decimal("3.0")

        assert n_s2_processed.realized_gain_loss.quantize(Decimal('0.01')) == expected_avco_gain_loss_ns2.quantize(Decimal('0.01'))
        assert n_s2_processed.gross_cost.quantize(Decimal('0.01')) == (-expected_avco_matched_cost_ns2).quantize(Decimal('0.01'))