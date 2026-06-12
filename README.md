# MiniBNG: Subscriber-Aware Routing and CGNAT Engine

MiniBNG is a telco edge router simulator that models subscriber sessions,
dynamic IP allocation, policy enforcement, CGNAT translation, longest-prefix
route lookup, packet decision tracing, and router-style metrics.

## Why This Project Exists

MiniBNG is inspired by broadband edge router and BNG behavior. It was built to
understand how telecom routing software coordinates subscriber state, control
plane configuration, and data plane packet decisions. The project focuses on
making forwarding behavior explainable: every simulated packet returns a clear
decision trace showing why it was forwarded or dropped.

## Key Features

- Subscriber session management
- Dynamic private IP allocation
- Subscriber policy enforcement
- CGNAT translation table
- Static route table with longest prefix match
- Explainable packet decision trace
- Router-style metrics
- FastAPI backend
- Router-style CLI
- One-shot demo command

## Architecture

```text
Subscriber Packet
      |
      v
Subscriber Lookup
      |
      v
Subscriber Status Check
      |
      v
Policy Check
      |
      v
CGNAT Translation
      |
      v
Route Lookup
      |
      v
Forward / Drop Decision
      |
      v
Metrics + Decision Trace
```

For a deeper module-level walkthrough, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Project Structure

```text
backend/
  app/
    main.py                 FastAPI application and API routes
    models.py               Pydantic request/response models
    subscriber_manager.py   Subscriber session store
    ip_allocator.py         Dynamic private IP allocator
    policy_engine.py        Subscriber traffic policy evaluation
    nat_engine.py           CGNAT translation table
    route_table.py          Static routes and longest-prefix lookup
    packet_simulator.py     Explainable packet decision pipeline
    metrics.py              Router-style counters
  tests/                    Backend test suite

cli/
  minibng_cli.py            Router-style Typer CLI

docs/
  ARCHITECTURE.md           Module and pipeline documentation
  DEMO.md                   Demo walkthrough and interview script
```

## Tech Stack

- Python
- FastAPI
- Pydantic
- Typer
- Rich
- Requests
- Pytest

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run Backend

```bash
uvicorn backend.app.main:app --reload --port 8001
```

## Run Tests

```bash
python3 -m pytest backend
```

## Demo Commands

Prepare the demo state:

```bash
python3 cli/minibng_cli.py demo seed
```

Run the full demo flow:

```bash
python3 cli/minibng_cli.py demo run
```

Demo summary:

- DNS packet forwarded
- Web packet forwarded
- SSH packet dropped by policy
- Metrics show 3 packets, 2 forwarded, 1 dropped

## Manual CLI Examples

Add a subscriber:

```bash
python3 cli/minibng_cli.py add subscriber user-501 --plan 50Mbps
```

Add a default route:

```bash
python3 cli/minibng_cli.py add route 0.0.0.0/0 --interface core0 --next-hop 192.168.1.1
```

Set a subscriber policy:

```bash
python3 cli/minibng_cli.py set policy user-501 --allowed --protocol TCP --protocol UDP --port 53 --port 80 --port 443
```

Simulate a packet:

```bash
python3 cli/minibng_cli.py simulate packet user-501 --source-port 45677 --destination-ip 8.8.8.8 --destination-port 53 --protocol UDP
```

Show metrics:

```bash
python3 cli/minibng_cli.py show metrics
```

By default, the CLI calls `http://127.0.0.1:8001`. Override it with:

```bash
MINIBNG_API_URL=http://127.0.0.1:8000 python3 cli/minibng_cli.py show metrics
```

## API Endpoints Overview

- `/subscribers` - create, list, block, unblock, and delete subscribers
- `/routes` - add, list, delete, and lookup routes
- `/policies` - configure subscriber-aware traffic policies
- `/nat` - create, list, delete, clear, and count CGNAT translations
- `/simulate-packet` - run explainable packet forwarding simulation
- `/metrics` - inspect and reset router-style counters

## What I Learned

- Control plane vs data plane responsibilities
- Subscriber-aware forwarding
- NAT and CGNAT concepts
- Longest-prefix match route lookup
- Policy-based packet decisions
- Observability and debugging with metrics and traces

## Future Improvements

- Linux namespace subscriber simulation
- Real packet forwarding using raw sockets or eBPF
- SQLite/PostgreSQL persistence
- Streamlit/React dashboard
- Docker Compose
- Prometheus/Grafana metrics
