"""Central timeout policy for production scheduler runtime guards."""
from __future__ import annotations
from dataclasses import asdict, dataclass

@dataclass(frozen=True)
class TimeoutPolicy:
    production_pipeline_timeout_seconds: int = 45 * 60
    production_pipeline_warning_seconds: int = 30 * 60
    stale_process_threshold_seconds: int = 90 * 60
    external_http_source_timeout_seconds: int = 15
    market_data_source_timeout_seconds: int = 20
    source_stage_soft_timeout_seconds: int = 5 * 60
    terminate_grace_seconds: int = 10

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

DEFAULT_TIMEOUT_POLICY = TimeoutPolicy()

def timeout_policy_from_env(env: dict[str, str] | None = None) -> TimeoutPolicy:
    import os
    source = env or os.environ
    def get_int(name: str, default: int) -> int:
        try:
            value = int(str(source.get(name, "")).strip())
            return value if value > 0 else default
        except Exception:
            return default
    return TimeoutPolicy(
        production_pipeline_timeout_seconds=get_int("STOCK_AI_PRODUCTION_PIPELINE_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_POLICY.production_pipeline_timeout_seconds),
        production_pipeline_warning_seconds=get_int("STOCK_AI_PRODUCTION_PIPELINE_WARNING_SECONDS", DEFAULT_TIMEOUT_POLICY.production_pipeline_warning_seconds),
        stale_process_threshold_seconds=get_int("STOCK_AI_STALE_PROCESS_THRESHOLD_SECONDS", DEFAULT_TIMEOUT_POLICY.stale_process_threshold_seconds),
        external_http_source_timeout_seconds=get_int("STOCK_AI_EXTERNAL_HTTP_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_POLICY.external_http_source_timeout_seconds),
        market_data_source_timeout_seconds=get_int("STOCK_AI_MARKET_DATA_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_POLICY.market_data_source_timeout_seconds),
        source_stage_soft_timeout_seconds=get_int("STOCK_AI_SOURCE_STAGE_SOFT_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_POLICY.source_stage_soft_timeout_seconds),
        terminate_grace_seconds=get_int("STOCK_AI_TERMINATE_GRACE_SECONDS", DEFAULT_TIMEOUT_POLICY.terminate_grace_seconds),
    )
