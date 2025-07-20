
# Transaction Cost Engine

A FastAPI-based microservice designed to process financial transactions, calculate their associated costs (Net Cost, Gross Cost), and determine realized gain or loss using the First-In, First-Out (FIFO) cost basis methodology. This engine is built to handle both new incoming transactions and existing, previously processed transactions to maintain an accurate portfolio cost basis.

## Table of Contents

  - [Features](https://www.google.com/search?q=%23features)
  - [Technologies Used](https://www.google.com/search?q=%23technologies-used)
  - [Project Structure](https://www.google.com/search?q=%23project-structure)
  - [Setup and Installation](https://www.google.com/search?q=%23setup-and-installation)
      - [Prerequisites](https://www.google.com/search?q=%23prerequisites)
      - [Cloning the Repository](https://www.google.com/search?q=%23cloning-the-repository)
      - [Install Dependencies](https://www.google.com/search?q=%23install-dependencies)
      - [Run the Application](https://www.google.com/search?q=%23run-the-application)
  - [API Usage](https://www.google.com/search?q=%23api-usage)
      - [Endpoint](https://www.google.com/search?q=%23endpoint)
      - [Request Body Example](https://www.google.com/search?q=%23request-body-example)
      - [Response Body Example](https://www.google.com/search?q=%23response-body-example)
      - [Accessing API Documentation](https://www.google.com/search?q=%23accessing-api-documentation)
  - [Logging](https://www.google.com/search?q=%23logging)
  - [Key Design Principles](https://www.google.com/search?q=%23key-design-principles)
  - [Future Enhancements](https://www.google.com/search?q=%23future-enhancements)

## Features

  * **Comprehensive Transaction Processing**: Ingests lists of both new and existing transactions for integrated processing.
  * **Cost Calculation**: Calculates `net_cost`, `gross_cost`, and `realized_gain_loss` for various transaction types.
  * **Configurable Cost Basis Methods**: Supports different methods for calculating the cost basis of sold securities.
     * **FIFO (First-In, First-Out)**: The default method, where the oldest acquired shares are considered sold first.
     * **Average Cost**: Calculates a weighted average cost for all shares held, and uses this average for disposition.  
  * **Realized Gain/Loss Calculation**: Determines the realized gain or loss for `SELL` transactions based on the matched cost lots.
  * **Decimal Precision**: Utilizes Python's `decimal.Decimal` type for all financial calculations to ensure high precision and prevent floating-point inaccuracies.
  * **Robust Data Validation**: Leverages Pydantic for strict schema validation of incoming transaction data.
  * **Modular and Extensible Design**: Clear separation of concerns into API, Core Models, Logic, and Services layers.
  * **Error Reporting**: Identifies and reports on individual transactions that fail validation or processing, allowing the successful ones to proceed.
  * **FastAPI Integration**: Provides a modern, high-performance web API with automatic interactive documentation (Swagger UI/OpenAPI).

## Technologies Used

  * **Python**: 3.9+
  * **FastAPI**: For building the web API.
  * **Pydantic**: For data validation, serialization, and deserialization.
  * **Poetry**: For dependency management and project packaging.
  * **Uvicorn**: An ASGI server for running the FastAPI application.
  * **Logging**: Standard Python logging for operational insights.

## Project Structure

```

├── src/
│   ├── api/
│   │   ├── main.py
│   │   └── v1/
│   │       ├── init.py
│   │       ├── router.py         # NEW: Aggregates all v1 API routers
│   │       └── transactions.py   # FastAPI router for transaction processing
│   ├── core/
│   │   ├── config/             # Centralized application settings
│   │   │   └── settings.py
│   │   ├── enums/
│   │   │   ├── init.py
│   │   │   ├── cost_method.py
│   │   │   └── transaction_type.py # Defines TransactionType enum (BUY, SELL, etc.)
│   │   └── models/
│   │       ├── init.py
│   │       ├── request.py      # Pydantic model for API request payload
│   │       ├── response.py     # Pydantic model for API response payload
│   │       └── transaction.py  # Pydantic model for a single Transaction object
│   ├── logic/
│   │   ├── init.py
│   │   ├── cost_basis_strategies.py # Implements different cost basis methods
│   │   ├── cost_calculator.py  # Calculates gross/net cost and gain/loss based on strategy
│   │   ├── cost_objects.py     # Shared data structures for cost logic (e.g., CostLot)
│   │   ├── disposition_engine.py # Manages cost lots (FIFO)
│   │   ├── error_reporter.py   # Collects and manages processing errors
│   │   ├── parser.py           # Parses raw transaction data into Transaction models
│   │   └── sorter.py           # Sorts transactions for correct processing order
│   ├── services/
│   │   ├── init.py
│   │   └── transaction_processor.py # Orchestrates the end-to-end transaction flow
├── .env.example                # Example environment variables (if any)
├── poetry.lock                 # Poetry lock file
├── pyproject.toml              # Poetry project definition
└── README.md                   # This file
```

## Setup and Installation


### Prerequisites

  * Python 3.9+ installed on your system.
  * [Poetry](https://www.google.com/search?q=https://python-poetry.org/docs/%23installation) for dependency management.

### Cloning the Repository

```bash
git clone https://github.com/your_username/transaction-cost-engine.git
cd transaction-cost-engine
```

### Install Dependencies

```bash
poetry install
```

### Run the Application

Start the FastAPI application using Uvicorn:

```bash
poetry run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

  * `--host 0.0.0.0`: Makes the server accessible externally (useful in Docker/VMs).
  * `--port 8000`: Runs the server on port 8000.
  * `--reload`: Enables auto-reloading on code changes (great for development).

## API Usage

The core functionality is exposed via a single POST endpoint.

### Endpoint

`POST /api/v1/process`

### Request Body Example

The request expects a JSON body conforming to the `TransactionProcessingRequest` schema.

```json
{
  "existing_transactions": [
    {
      "transaction_id": "existing_buy_001",
      "portfolio_id": "PORT001",
      "instrument_id": "AAPL",
      "security_id": "SEC001",
      "transaction_type": "BUY",
      "transaction_date": "2023-01-01T00:00:00Z",
      "settlement_date": "2023-01-03T00:00:00Z",
      "quantity": 10.0,
      "gross_transaction_amount": 1500.0,
      "net_transaction_amount": 1505.5,
      "fees": {"brokerage": 5.5},
      "accrued_interest": 0.0,
      "average_price": 150.0,
      "trade_currency": "USD",
      "net_cost": 1505.5,
      "gross_cost": 1500.0,
      "realized_gain_loss": null
    }
  ],
  "new_transactions": [
    {
      "transaction_id": "new_buy_001",
      "portfolio_id": "PORT001",
      "instrument_id": "AAPL",
      "security_id": "SEC001",
      "transaction_type": "BUY",
      "transaction_date": "2023-01-10T00:00:00Z",
      "settlement_date": "2023-01-12T00:00:00Z",
      "quantity": 5.0,
      "gross_transaction_amount": 760.0,
      "fees": {"brokerage": 2.0},
      "trade_currency": "USD"
    },
    {
      "transaction_id": "new_sell_001",
      "portfolio_id": "PORT001",
      "instrument_id": "AAPL",
      "security_id": "SEC001",
      "transaction_type": "SELL",
      "transaction_date": "2023-01-15T00:00:00Z",
      "settlement_date": "2023-01-17T00:00:00Z",
      "quantity": 8.0,
      "gross_transaction_amount": 1250.0,
      "fees": {"brokerage": 3.0},
      "trade_currency": "USD"
    },
    {
      "transaction_id": "invalid_sell_001",
      "portfolio_id": "PORT001",
      "instrument_id": "MSFT",
      "security_id": "SEC002",
      "transaction_type": "SELL",
      "transaction_date": "2023-01-18T00:00:00Z",
      "settlement_date": "2023-01-20T00:00:00Z",
      "quantity": 100.0,
      "gross_transaction_amount": 10000.0,
      "fees": {"brokerage": 10.0},
      "trade_currency": "USD"
    }
  ]
}
```

### Response Body Example

The response will contain two lists: `processed_transactions` (successfully processed transactions with computed costs) and `errored_transactions` (transactions that failed processing, along with their error reasons).

```json
{
  "processed_transactions": [
    {
      "transaction_id": "new_buy_001",
      "portfolio_id": "PORT001",
      "instrument_id": "AAPL",
      "security_id": "SEC001",
      "transaction_type": "BUY",
      "transaction_date": "2023-01-10",
      "settlement_date": "2023-01-12",
      "quantity": 5.0,
      "gross_transaction_amount": 760.0,
      "net_transaction_amount": null,
      "fees": {"stamp_duty": 0.0, "exchange_fee": 0.0, "gst": 0.0, "brokerage": 2.0, "other_fees": 0.0},
      "accrued_interest": 0.0,
      "average_price": 152.4,
      "trade_currency": "USD",
      "net_cost": 762.0,
      "gross_cost": 760.0,
      "realized_gain_loss": null,
      "error_reason": null
    },
    {
      "transaction_id": "new_sell_001",
      "portfolio_id": "PORT001",
      "instrument_id": "AAPL",
      "security_id": "SEC001",
      "transaction_type": "SELL",
      "transaction_date": "2023-01-15",
      "settlement_date": "2023-01-17",
      "quantity": 8.0,
      "gross_transaction_amount": 1250.0,
      "net_transaction_amount": null,
      "fees": {"stamp_duty": 0.0, "exchange_fee": 0.0, "gst": 0.0, "brokerage": 3.0, "other_fees": 0.0},
      "accrued_interest": 0.0,
      "average_price": 156.25,
      "trade_currency": "USD",
      "net_cost": 0.0,
      "gross_cost": 0.0,
      "realized_gain_loss": -14.0, # Example value based on FIFO logic
      "error_reason": null
    }
  ],
  "errored_transactions": [
    {
      "transaction_id": "invalid_sell_001",
      "error_reason": "Sell quantity (100.00) exceeds available holdings (0.00) for instrument 'MSFT' in portfolio 'PORT001'."
    }
  ]
}
```

### Accessing API Documentation

Once the server is running, you can access the interactive API documentation (Swagger UI) at:
`http://0.0.0.0:8000/docs`

## Logging

The application is configured with Python's standard `logging` module. You'll see `INFO` messages in your console providing insights into the data types and flow at various stages of transaction processing (API, Service, Parser). Errors are logged with `ERROR` or `EXCEPTION` levels.

To enable basic console logging for development, ensure you have something like this in your main application entry point (`src/api/main.py`):

```python
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
```

## Configuration

The application's behavior can be configured using environment variables. Create a `.env` file in the root directory of your project (next to `pyproject.toml`).

### `COST_BASIS_METHOD`

This variable determines which cost basis method the engine will use for calculating gains/losses on SELL transactions.

* **Allowed values**: `FIFO` (default), `AVERAGE_COST`
* **Example `.env` file for FIFO (default):**
    ```env
    COST_BASIS_METHOD=FIFO
    ```
* **Example `.env` file for Average Cost:**
    ```env
    COST_BASIS_METHOD=AVERAGE_COST
    ```

## Key Design Principles

  * **Dependency Injection**: Components like `TransactionProcessor`, `CostCalculator`, etc., are instantiated and passed as dependencies, promoting loose coupling and testability.
  * **Separation of Concerns**: Each module (e.g., `parser`, `disposition_engine`, `cost_calculator`) has a single, well-defined responsibility.
  * **Data Immutability (Pydantic)**: Pydantic models help enforce data schemas and can be configured for immutability, ensuring data integrity.
  * **Precision for Financials**: Consistent use of `decimal.Decimal` prevents rounding errors common with `float` types.

## Future Enhancements

  * **Support for Other Cost Basis Methods**: Extend `CostCalculator` with strategies for LIFO (Last-In, First-Out), Average Cost, etc.
  * **Persistence Layer**: Integrate with a database (SQL, NoSQL) to store transactions and portfolio data persistently.
  * **Asynchronous Processing**: Implement `async/await` patterns for I/O-bound operations (e.g., database calls) to improve concurrency.
  * **Authentication and Authorization**: Secure API endpoints for production deployment.
  * **Advanced Error Handling**: More granular error codes and detailed explanations for API consumers.
  * **Unit and Integration Tests**: Comprehensive test suite to ensure correctness and prevent regressions.

-----