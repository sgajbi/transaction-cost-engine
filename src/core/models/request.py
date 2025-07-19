# src/core/models/request.py

from typing import List
from pydantic import BaseModel, Field
from src.core.models.transaction import Transaction

class TransactionProcessingRequest(BaseModel):
    """
    Represents the input payload for the transaction processing API.
    """
    existing_transactions: List[Transaction] = Field(
        default_factory=list,
        description="List of previously processed transactions with cost fields already computed."
    )
    new_transactions: List[Transaction] = Field(
        ...,
        description="New transactions to be processed (including possible backdated ones)."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "existing_transactions": [
                    {
                        "transaction_id": "existing_buy_001",
                        "portfolioId": "PORT001",
                        "instrumentId": "AAPL",
                        "security_id": "SEC001",
                        "transaction_type": "BUY",
                        "transaction_date": "2023-01-01",
                        "settlement_date": "2023-01-03",
                        "quantity": 10.0,
                        "gross_transaction_amount": 1500.0,
                        "net_transaction_amount": 1505.5,
                        "fees": {"brokerage": 5.5},
                        "accrued_interest": 0.0,
                        "average_price": 150.0,
                        "tradeCurrency": "USD",
                        "net_cost": 1505.5,
                        "gross_cost": 1500.0,
                        "realized_gain_loss": None
                    }
                ],
                "new_transactions": [
                    {
                        "transaction_id": "new_buy_001",
                        "portfolioId": "PORT001",
                        "instrumentId": "AAPL",
                        "security_id": "SEC001",
                        "transaction_type": "BUY",
                        "transaction_date": "2023-01-10",
                        "settlement_date": "2023-01-12",
                        "quantity": 5.0,
                        "gross_transaction_amount": 760.0,
                        "fees": {"brokerage": 2.0},
                        "tradeCurrency": "USD"
                    },
                    {
                        "transaction_id": "new_sell_001",
                        "portfolioId": "PORT001",
                        "instrumentId": "AAPL",
                        "security_id": "SEC001",
                        "transaction_type": "SELL",
                        "transaction_date": "2023-01-15",
                        "settlement_date": "2023-01-17",
                        "quantity": 8.0,
                        "gross_transaction_amount": 1250.0,
                        "fees": {"brokerage": 3.0},
                        "tradeCurrency": "USD"
                    },
                    {
                        "transaction_id": "invalid_sell_001",
                        "portfolioId": "PORT001",
                        "instrumentId": "MSFT",
                        "security_id": "SEC002",
                        "transaction_type": "SELL",
                        "transaction_date": "2023-01-18",
                        "settlement_date": "2023-01-20",
                        "quantity": 100.0, 
                        "gross_transaction_amount": 10000.0,
                        "fees": {"brokerage": 10.0},
                        "tradeCurrency": "USD"
                    }
                ]
            }
        }