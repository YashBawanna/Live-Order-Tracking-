# Real-Time Order Notification System

A production-structured FastAPI backend that streams live order changes to browser clients using **Server-Sent Events (SSE)**.

Built to demonstrate clean architecture, OOP principles, and SOLID design in a real Python backend.

---

## How It Works

```
Browser/Client
    │  REST  POST / PATCH / DELETE
    ▼
FastAPI Routes  (routes/)
    │  calls
    ▼
OrderRepository  (repositories/)
    │  writes to
    ▼
SQL Server — orders table
    │  DB trigger fires automatically
    ▼
change_log table
    ▲  polled every 1s
ChangeLogPoller  (services/poller.py)
    │  broadcasts JSON payload
    ▼
asyncio.Queue (one per tab)
    │  streamed as SSE
    ▼
Browser — real-time update received
```

---

## Project Structure

```
orders_api/
├── main.py                     # App init, middleware, router registration only
├── config.py                   # All env vars in one place
├── database.py                 # pyodbc connection factory
├── models.py                   # Pydantic request schemas
├── dependencies.py             # DI wiring — concrete classes injected here
│
├── repositories/
│   ├── base.py                 # Abstract interfaces (OrderRepository, etc.)
│   ├── sqlserver.py            # SQL Server implementation
│   └── change_log.py           # Change log read/acknowledge repository
│
├── services/
│   └── poller.py               # ChangeLogPoller class (background broadcast loop)
│
├── routes/
│   ├── orders.py               # CRUD endpoints (/orders)
│   └── stream.py               # SSE endpoint (/stream), diagnostics (/clients)
│
├── db/
│   └── init_db.py              # Schema creation, trigger, seed data
│
├── .env.example
├── requirements.txt
└── README.md
```

---

## OOP Concepts Applied

| Concept | Where |
|---|---|
| **Encapsulation** | `ChangeLogPoller` owns its client list and lock — not exposed as globals |
| **Abstraction** | `OrderRepository`, `AbstractChangeLogRepository` hide DB details from routes |
| **Inheritance** | `SqlServerOrderRepository` inherits from `OrderRepository` |
| **Polymorphism** | Routes accept any `OrderRepository` subclass via Depends() |

---

## SOLID Principles Applied

### S — Single Responsibility
Every module has exactly one job:
- `config.py` → reads env vars
- `database.py` → produces a DB connection
- `repositories/sqlserver.py` → talks to SQL Server
- `services/poller.py` → polls and broadcasts
- `routes/orders.py` → handles HTTP

### O — Open / Closed
To add a **Postgres backend**, create `PostgresOrderRepository(OrderRepository)` and update one line in `dependencies.py`. Zero changes to routes or the poller.

### L — Liskov Substitution
`SqlServerOrderRepository` can replace `OrderRepository` anywhere without breaking callers. Routes don't care which subclass they get.

### I — Interface Segregation
`OrderReaderRepository` and `OrderWriterRepository` are separate abstract classes. A read-only consumer (e.g. a reporting service) can depend only on the reader interface.

### D — Dependency Inversion
Routes depend on `OrderRepository` (abstraction), not `SqlServerOrderRepository` (detail). The poller depends on `AbstractChangeLogRepository`, not on pyodbc directly. All wiring lives in `dependencies.py`.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/orders` | List all orders (newest first) |
| `POST` | `/orders` | Create a new order |
| `PATCH` | `/orders/{id}` | Update order status |
| `DELETE` | `/orders/{id}` | Delete an order |
| `GET` | `/stream` | SSE stream — real-time change events |
| `GET` | `/clients` | Number of currently connected SSE clients |

### Order Status Values
`pending` → `shipped` → `delivered` / `cancelled`

### Example Payloads

**POST /orders**
```json
{
  "customer_name": "Yogesh Kumar",
  "product_name": "Galaxy Tab S11",
  "status": "pending"
}
```

**PATCH /orders/1**
```json
{ "status": "shipped" }
```

### SSE Event Format
```
data: {"log_id": 7, "operation": "UPDATE", "order_id": 1,
       "customer_name": "Yogesh Kumar", "product_name": "Galaxy Tab S11",
       "status": "shipped", "changed_at": "2026-06-05T10:30:00"}
```

---

## Setup

### Prerequisites
- Python 3.11+
- SQL Server (local or Azure SQL)
- ODBC Driver 17 for SQL Server

### Install

```bash
# 1. Clone / unzip the project
cd orders_api

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your DB credentials
```

### Run

```bash
uvicorn main:app --reload
```

Interactive API docs: http://localhost:8000/docs

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DB_SERVER` | `localhost` | SQL Server host |
| `DB_NAME` | `OrdersDB` | Database name |
| `DB_USER` | `sa` | SQL Server username |
| `DB_PASSWORD` | *(required)* | SQL Server password |
| `DB_DRIVER` | `ODBC Driver 17 for SQL Server` | ODBC driver name |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `POLL_INTERVAL` | `1` | Seconds between change_log polls |
| `SSE_KEEPALIVE_TIMEOUT` | `15` | Seconds between SSE keepalive pings |

---

## Extending the System

### Swap the database (e.g. to Postgres)
1. Create `repositories/postgres.py` implementing `OrderRepository`
2. In `dependencies.py`, change:
   ```python
   # Before
   return SqlServerOrderRepository()
   # After
   return PostgresOrderRepository()
   ```
That's it. Routes, poller, and models are untouched.

### Add a new endpoint
Create a new router in `routes/`, inject the repo via `Depends(get_order_repository)`, and register it in `main.py` with `app.include_router(...)`.

---

## Planned Improvements
- [ ] Structured logging (replace `print` with `logging`)
- [ ] Unit and integration tests
- [ ] Connection pooling via `aioodbc`
- [ ] Docker + docker-compose setup
