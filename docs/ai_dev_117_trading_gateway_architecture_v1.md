# AI-DEV-117 Trading Gateway Architecture V1

## Architecture

AI-DEV-117 introduces `app/trading/` as an offline architecture boundary for
future Sinopac/Shioaji integration. The gateway layer is intentionally separate
from `analysis`, `report`, `scheduler`, and delivery pipelines.

The first version contains only schemas, capability declarations, validation
adapters, and safety gates. It does not import Shioaji, does not read `.env`,
does not login, does not submit simulation orders, and does not submit
production orders.

## Quote / Account / Order Boundary

- Quote: `SnapshotRequest`, `KbarsRequest`, and quote capability checks live in
  `quote_adapter.py` and `broker_capability.py`.
- Account: `AccountStatusRequest`, read-only `Position`, and read-only
  `Balance` schemas live behind `account_adapter.py`.
- Order: `OrderProposal`, `SimulationOrderRequest`, and
  `ProductionOrderRequest` live behind `order_adapter.py` and `risk_gate.py`.

The facade in `gateway.py` wires these boundaries together for dry-run
validation without broker runtime dependencies.

## Safety Gates

The explicit safety functions are:

- `assert_no_production_order()`: always blocks production order requests.
- `assert_explicit_simulation_approval()`: blocks simulation requests unless a
  same-run approval flag and reference are supplied.
- `validate_order_proposal()`: validates symbol, quantity, price, and blocks
  production proposal mode.
- `validate_risk_limits()`: enforces max quantity, max notional, allowed side,
  and optional allowed symbol limits.

Production execution is not supported in V1. Simulation execution remains
blocked by default and this task does not execute a simulation order.

## Relationship To AI-DEV-116

AI-DEV-116 prepared a controlled Sinopac API test application package and
documented the future explicit approval path for simulation login and simulation
order tests. AI-DEV-117 does not consume credentials and does not continue those
runtime tests. It provides the architecture boundary that future approved
simulation work can target without contaminating analysis, report, or scheduler
code.

## Future Path To Simulation Test

A future task may add a Shioaji-backed simulation adapter only after explicit
human approval for that exact run. The future adapter must preserve these
requirements:

- load credentials only inside an approved runtime command;
- never print secrets, account IDs, tokens, or `.env` content;
- instantiate broker runtime in simulation mode only;
- require explicit same-run approval before any simulation execution;
- produce audit evidence showing no scheduler, notification, or production
  trading side effects.

## Future Path To Production Execution

Production execution requires a separate design review, explicit human approval,
runtime account controls, risk limits, audit logs, rollback procedures, and an
operator-controlled enablement mechanism. V1 hard-blocks production order
requests and should not be treated as production trading readiness.

## Explicit Human Approval Requirements

Human approval is required before any future task may:

- read broker credentials or `.env`;
- call broker login;
- submit a simulation order;
- submit a production order;
- connect trading actions to scheduler, strategy signals, LINE, Email, or a
  production database.

## Validation

```bash
./venv/bin/python -m py_compile \
  app/trading/gateway.py \
  app/trading/quote_adapter.py \
  app/trading/account_adapter.py \
  app/trading/order_adapter.py \
  app/trading/risk_gate.py \
  app/trading/broker_capability.py \
  app/trading/schemas.py \
  scripts/orchestrator/validate_trading_gateway_v1.py

./venv/bin/python scripts/orchestrator/validate_trading_gateway_v1.py --pretty

./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```
