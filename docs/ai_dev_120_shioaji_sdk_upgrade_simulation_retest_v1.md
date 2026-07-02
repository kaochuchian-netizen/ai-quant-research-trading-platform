# AI-DEV-120 Shioaji SDK Upgrade Simulation Retest V1

## Scope

AI-DEV-120 updates the repo dependency pin for Shioaji after the AI-DEV-119
official simulation login/order test was blocked by Sinopac returning:

```text
StatusCode: 503, Please update the version of shioaji.
```

The GCP venv was observed on Shioaji `1.5.1`. PyPI lists Shioaji `1.5.4` as
the latest release, so this task pins the repo dependency to `shioaji==1.5.4`
and updates the official simulation test dry-run evidence to require `>= 1.5.4`.

## Changed Files

- `requirements.txt`
- `scripts/orchestrator/sinopac_official_api_test.py`
- `scripts/orchestrator/validate_ai_branch.py`
- `templates/sinopac_official_api_test_result.example.json`
- `docs/ai_dev_119_sinopac_official_api_online_test_certification_v1.md`
- `docs/ai_dev_120_shioaji_sdk_upgrade_simulation_retest_v1.md`

## Safety

- No simulation login is executed by this task.
- No simulation order is executed by this task.
- No production order is possible or executed.
- No secrets, `.env`, tokens, or credentials are read or printed.
- No LINE or Email notification is sent.
- No scheduler, cron, or systemd configuration is changed.
- Execute mode remains reserved for a separate same-run Richard approval after
  this branch is merged.

## Validation

Use the project venv for all validation:

```bash
./venv/bin/python -m pip show shioaji
./venv/bin/python -m py_compile scripts/orchestrator/sinopac_official_api_test.py
./venv/bin/python scripts/orchestrator/validate_sinopac_official_api_test_v1.py --pretty
./venv/bin/python scripts/orchestrator/sinopac_official_api_test.py --mode dry-run --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

Do not run execute mode as part of this task. The official simulation retest
must be approved separately after merge.
