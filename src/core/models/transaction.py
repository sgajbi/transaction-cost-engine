# src/core/models/transaction.py

from datetime import date
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, condecimal, PositiveFloat

class Fees(BaseModel):
    """
    Represents various fees associated with a transaction.
    All fee fields are optional and default to 0.0 if not provided.
    """
    stamp_duty: condecimal(ge=0) = Field(default=0.0, description="Stamp duty fee")
    exchange_fee: condecimal(ge=0) = Field(default=0.0, description="Exchange fee")
    gst: condecimal(ge=0) = Field(default=0.0, description="Goods and Services Tax")
    brokerage: condecimal(ge=0) = Field(default=0.0, description="Brokerage fee")
    other_fees: condecimal(ge=0) = Field(default=0.0, description="Any other miscellaneous fees")

    @property
    def total_fees(self) -> float:
        """Calculates the sum of all fees."""
        # Use .as_tuple() and check for nan/infinity if condecimal allows them, though not expected with ge=0
        return float(
            self.stamp_duty +
            self.exchange_fee +
            self.gst +
            self.brokerage +
            self.other_fees
        )


class Transaction(BaseModel):
    """
    Represents a single financial transaction.
    This model includes fields for both input and computed values.
    """
    transaction_id: str = Field(..., description="Unique identifier for the transaction")
    portfolio_id: str = Field(..., alias="portfolioId", description="Identifier for the portfolio")
    instrument_id: str = Field(..., alias="instrumentId", description="Identifier for the instrument (e.g., ticker)")
    security_id: str = Field(..., description="Unique identifier for the specific security")
    transaction_type: str = Field(..., description="Type of transaction (e.g., BUY, SELL, DIVIDEND)")
    transaction_date: date = Field(..., description="Date the transaction occurred (ISO format)")
    settlement_date: date = Field(..., description="Date the transaction settled (ISO format)")
    quantity: PositiveFloat = Field(..., description="Quantity of the instrument involved in the transaction")
    gross_transaction_amount: condecimal(ge=0) = Field(..., description="Gross amount of the transaction")
    net_transaction_amount: Optional[condecimal(ge=0)] = Field(None, description="Net amount of the transaction (optional, can be input or calculated)")
    fees: Optional[Fees] = Field(default_factory=Fees, description="Detailed breakdown of fees")
    accrued_interest: Optional[condecimal(ge=0)] = Field(default=0.0, description="Accrued interest for the transaction")
    average_price: Optional[condecimal(ge=0)] = Field(None, description="Average price of the instrument at the time of transaction")
    trade_currency: str = Field(..., alias="tradeCurrency", description="Currency of the transaction")

    # --- Computed / Enriched Fields
    net_cost: Optional[condecimal(ge=0)] = Field(None, description="Calculated net cost for BUYs")
    gross_cost: Optional[condecimal(ge=0)] = Field(None, description="Calculated gross cost for BUYs")
    realized_gain_loss: Optional[condecimal()] = Field(None, description="Calculated realized gain/loss for SELLs")
    error_reason: Optional[str] = Field(None, description="Reason for transaction processing failure")

    class Config:
        populate_by_name = True # Allows using both alias and field name for input
        from_attributes = True # For Pydantic v2, allows creating model from ORM objects (though not used directly here, good practice)
        json_encoders = {
            date: lambda v: v.isoformat() # Ensure date objects are serialized to ISO format strings
        }
        # Pydantic v2 replaces 'json_loads' and 'json_dumps' with 'json_schema_extra' or custom serializers if needed.
        # For simple JSON handling, FastAPI handles this.
        arbitrary_types_allowed = False # Ensure strict typing