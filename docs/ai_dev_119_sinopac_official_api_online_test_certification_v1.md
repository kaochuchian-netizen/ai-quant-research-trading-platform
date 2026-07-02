# AI-DEV-119 Sinopac Official API Online Test Certification V1

## Scope

AI-DEV-119 provides a controlled evidence tool for the Sinopac/Shioaji official
API online test. It supports offline dry-run evidence and, only after Richard's
same-run approval, Shioaji `simulation=True` login plus `simulation=True`
`place_order` evidence.

This task does not enable formal orders, `production=True`, strategy signals,
schedulers, cron, systemd, LINE, Email, production pipelines, or production
database writes.

## Official Test Requirements

- Shioaji API testing must complete login and `place_order` in simulation mode.
- Shioaji version must be `>= 1.2`.
- The official test window is Monday-Friday 08:00-20:00 Asia/Taipei.
- 18:00-20:00 Asia/Taipei requires Taiwan IP attestation.
- Securities and futures must be tested separately.
- Order tests must be at least 1 second apart.
- The API key used for execute mode must have trading permission.

## Safety Gates

- Dry-run mode does not read secrets, login, or place orders.
- Execute mode requires:
  - `--i-understand-this-runs-simulation-login`
  - `--i-understand-this-runs-simulation-order`
  - `--richard-approval RICHARD_APPROVES_AI_DEV_119_SIMULATION_LOGIN_AND_ORDER`
- The tool always creates `shioaji.Shioaji(simulation=True)`.
- `--production` is accepted only to fail closed.
- Stock simulation order is enabled by default for execute mode.
- Futures simulation order is disabled unless `--enable-futures` and a contract
  month are provided.
- API keys, secrets, tokens, and account identifiers are masked in JSON output.
- No LINE or Email notification is sent.
- No scheduler, cron, or systemd integration is changed.
- No strategy signal is connected.
- No production database is modified.

## Dry-Run Command

```bash
./venv/bin/python scripts/orchestrator/sinopac_official_api_test.py \
  --mode dry-run \
  --pretty
```

Dry-run expected output has:

- `decision: sinopac_official_api_test_dry_run_ready`
- `side_effects.secrets_read: false`
- `side_effects.simulation_login_called: false`
- `side_effects.simulation_order_called: false`
- `test_results.login.status: not_run`
- `test_results.stock_place_order.status: not_run`

## Execute Command

Richard approval is required before running this command. Execute mode performs
real Shioaji simulation login and simulation order calls, but never
`production=True`.

```bash
./venv/bin/python scripts/orchestrator/sinopac_official_api_test.py \
  --mode execute \
  --i-understand-this-runs-simulation-login \
  --i-understand-this-runs-simulation-order \
  --richard-approval RICHARD_APPROVES_AI_DEV_119_SIMULATION_LOGIN_AND_ORDER \
  --stock-id 2330 \
  --quantity 1 \
  --price 1 \
  --pretty
```

If running during 18:00-20:00 Asia/Taipei from a Taiwan IP, add:

```bash
  --taiwan-ip-attested
```

Optional futures testing remains disabled by default. It requires separate
intent in the same execute command:

```bash
  --enable-futures \
  --futures-code TXF \
  --futures-contract-month <YYYYMM>
```

## Expected Execute Output

Successful execute output has:

- `decision: sinopac_official_api_simulation_tests_completed`
- `approval.richard_same_run_approval_present: true`
- `test_results.login.ok: true`
- `test_results.login.simulation: true`
- `test_results.stock_place_order.ok: true`
- `test_results.stock_place_order.simulation: true`
- `side_effects.production_order_called: false`
- `side_effects.line_sent: false`
- `side_effects.email_sent: false`
- masked credential and account fields only

## No Production Order Policy

Production orders are categorically blocked. This tool must not be connected to
strategy signals, scheduler jobs, cron, systemd, production pipelines, delivery
channels, or production databases. Passing `--production` returns a blocked JSON
result and exits non-zero.

## Validation

```bash
./venv/bin/python -m py_compile \
  scripts/orchestrator/sinopac_official_api_test.py \
  scripts/orchestrator/validate_sinopac_official_api_test_v1.py

./venv/bin/python scripts/orchestrator/validate_sinopac_official_api_test_v1.py --pretty

./venv/bin/python scripts/orchestrator/sinopac_official_api_test.py --mode dry-run --pretty

./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```
