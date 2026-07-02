"""Safe Shioaji runtime check wrapper.

This legacy entrypoint intentionally does not login, read secrets, or print
account data. Use the controlled AI-DEV-116 tool for approved simulation tests.
"""

from scripts.orchestrator.sinopac_api_test_application import health_check, stable_json


class _Args:
    run_id = "legacy-test-shioaji-health-check"


if __name__ == "__main__":
    print(stable_json(health_check(_Args()), pretty=True), end="")
