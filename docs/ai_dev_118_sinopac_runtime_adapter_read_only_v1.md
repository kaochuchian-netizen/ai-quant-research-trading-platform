# AI-DEV-118 Sinopac Runtime Adapter Read-only V1

## Runtime Adapter Architecture

AI-DEV-118 adds a read-only Sinopac/Shioaji runtime adapter on top of the
AI-DEV-117 trading gateway boundary. The adapter lives in
`app/trading/sinopac_adapter.py` and is intentionally limited to package import
checks, Shioaji version discovery, quote/account adapter skeletons, runtime
capability reporting, and dry-run health output.

The gateway can mount this adapter through
`TradingGateway.with_sinopac_runtime_adapter()`. Mounting the adapter does not
create a broker client, call login, submit orders, read `.env`, connect strategy
signals, update schedules, write production databases, or send LINE/Email.

## Quote / Account / Order Boundary

- Quote: `SinopacQuoteAdapter` exposes the same validation-oriented quote
  interface as the gateway quote boundary. It declares snapshot and kbars
  capability but does not fetch live broker data.
- Account: `SinopacAccountAdapter` exposes a read-only account capability
  skeleton. It does not load account identifiers or balances from a broker.
- Order: runtime order execution is blocked. The runtime adapter exposes
  blocking methods only so validators can prove simulation and production order
  paths remain closed.

## Relationship To AI-DEV-116 And AI-DEV-117

AI-DEV-116 documented the controlled Sinopac API test application path and the
future explicit approval requirements for broker login and simulation testing.
AI-DEV-117 introduced the offline trading gateway architecture with schemas,
capabilities, adapters, and hard order safety gates.

AI-DEV-118 connects those two steps by adding a Shioaji-aware runtime adapter
surface without continuing into login, credential loading, simulation order
certification, production trading, scheduler wiring, or notification delivery.

## Why Login And Orders Remain Blocked

Login remains blocked by default because broker credentials are outside this PR
and must not be read from `.env` or any secret store during read-only adapter
validation. A login function exists only as an explicit future boundary and
raises a blocked exception in this version.

Simulation and production order execution remain blocked because this PR is not
a trading certification task. Production execution is unsupported, and
simulation execution requires a separate same-run approval and evidence path.

## Future AI-DEV-119 Simulation Certification Path

AI-DEV-119 can certify simulation behavior only after explicit approval for that
specific run. The future path should:

- keep production execution disabled;
- load credentials only inside an approved runtime command;
- avoid printing secrets, tokens, account identifiers, or `.env` content;
- instantiate Shioaji in simulation mode only;
- require same-run human approval before simulation execution;
- produce JSON evidence for login and simulation test results;
- prove no scheduler, strategy signal, LINE/Email, or production database side
  effects occurred.

## Safety Checklist

- No broker login is called by AI-DEV-118 validation.
- No simulation order is executed.
- No production order is executed.
- No `.env`, API key, token, secret, or account value is read or printed.
- No scheduler, cron, or systemd configuration is changed.
- No production database is modified.
- No strategy signal is connected.
- No LINE or Email notification is sent.
- Runtime health reports `runtime_ready` when Shioaji is importable and
  `runtime_degraded` when the adapter surface is safe but Shioaji is missing.

## Validation

```bash
./venv/bin/python -m py_compile \
  app/trading/sinopac_adapter.py \
  app/trading/runtime_health.py \
  app/trading/gateway.py \
  scripts/orchestrator/validate_sinopac_runtime_adapter_v1.py

./venv/bin/python scripts/orchestrator/validate_sinopac_runtime_adapter_v1.py --pretty

./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```
