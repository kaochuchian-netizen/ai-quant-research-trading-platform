# AI-DEV-116 Sinopac API Test Application Completion V1

## Scope

AI-DEV-116 is limited to controlled Sinopac/Shioaji API opening test support.
It does not enable formal trading, auto trading, scheduler execution, strategy
signal execution, portfolio changes, LINE notifications, or production
`place_order` behavior.

## Allowed

- Shioaji package/runtime health check with version requirement `>= 1.2`.
- `simulation=True` login test after Richard's same-run confirmation.
- `simulation=True` stock order-placement test after Richard's same-run confirmation.
- Optional `simulation=True` futures order-placement test; disabled by default.
- JSON evidence records for application review.
- API test status inspection.

## Safety Gates

- Runtime order tests require a confirmation phrase in the same command.
- All runtime commands instantiate Shioaji with `simulation=True`.
- The non-venv runtime checked during repo-side preparation did not have
  Shioaji installed and returned `PackageNotFoundError`. The project venv
  runtime used for validation currently reports Shioaji `1.5.1`, which satisfies
  the official `>= 1.2` requirement.
- Formal simulation login/order evidence must not be generated until Richard
  explicitly approves that exact run after the runtime health check is ready.
- The official service window is Monday-Friday 08:00-20:00 Asia/Taipei.
- 18:00-20:00 requires explicit Taiwan IP attestation.
- Stock and futures order tests sleep at least one second before submitting the
  simulated order.
- The tool never prints API keys, secrets, tokens, or `.env` content.

## Current Runtime Status

As of the AI-DEV-116 repo-side PR, runtime status depends on the interpreter:

- System/non-venv Python health check: Shioaji not installed,
  `error_class=PackageNotFoundError`.
- Project `./venv/bin/python` health check: Shioaji `1.5.1`,
  `import_ok=true`, `version_ok=true`.

This PR intentionally stops at repo-side tooling and evidence contracts. It does
not run `login-test`, `stock-order-test`, or `futures-order-test`.

## Commands

Offline application package:

```bash
python3 scripts/orchestrator/sinopac_api_test_application.py build-application \
  --output /tmp/sinopac_api_test_application_result.json \
  --pretty
```

Offline health check:

```bash
python3 scripts/orchestrator/sinopac_api_test_application.py health-check --pretty
```

Validate evidence:

```bash
python3 scripts/orchestrator/validate_sinopac_api_test_application_result.py \
  --input /tmp/sinopac_api_test_application_result.json \
  --pretty
```

Simulation login test, only after Richard explicitly approves that run:

```bash
python3 scripts/orchestrator/sinopac_api_test_application.py login-test \
  --confirm RICHARD_APPROVES_SIMULATION_LOGIN_TEST \
  --output /tmp/sinopac_api_login_test_result.json \
  --pretty
```

Simulation stock order test, only after Richard explicitly approves that run:

```bash
python3 scripts/orchestrator/sinopac_api_test_application.py stock-order-test \
  --confirm RICHARD_APPROVES_SIMULATION_STOCK_PLACE_ORDER_TEST \
  --stock-id 2330 \
  --quantity 1 \
  --price 1 \
  --output /tmp/sinopac_api_stock_order_test_result.json \
  --pretty
```

Optional simulation futures order test, disabled unless `--enable-futures` is
passed and Richard explicitly approves that run:

```bash
python3 scripts/orchestrator/sinopac_api_test_application.py futures-order-test \
  --enable-futures \
  --confirm RICHARD_APPROVES_SIMULATION_FUTURES_PLACE_ORDER_TEST \
  --futures-code TXF \
  --contract-month <YYYYMM> \
  --quantity 1 \
  --price 1 \
  --output /tmp/sinopac_api_futures_order_test_result.json \
  --pretty
```

## Forbidden

- `production=True` order placement.
- Formal order placement.
- Auto trading.
- Scheduler or cron integration.
- Strategy signal integration.
- Portfolio mutation.
- Secret printing.
- Running simulation order tests without Richard's same-run confirmation.

## Validation

```bash
python3 -m py_compile \
  scripts/orchestrator/sinopac_api_test_application.py \
  scripts/orchestrator/validate_sinopac_api_test_application_result.py

python3 scripts/orchestrator/sinopac_api_test_application.py build-application \
  --output /tmp/sinopac_api_test_application_result.json \
  --pretty

python3 scripts/orchestrator/validate_sinopac_api_test_application_result.py \
  --input /tmp/sinopac_api_test_application_result.json \
  --pretty
```
