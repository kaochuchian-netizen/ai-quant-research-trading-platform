# AI-DEV-163 Manual Rerun Runtime Activation Trace

- bridge: `scripts/orchestrator/manual_rerun_runtime_bridge.py`
- post_route: `/stock-ai-dashboard/api/manual-rerun`
- status_route: `/stock-ai-dashboard/api/manual-rerun/status`
- health_route: `/stock-ai-dashboard/api/manual-rerun/healthz`
- pin_config_sources: runtime env `STOCK_AI_MANUAL_RERUN_PIN_HASH` or runtime-only config file
- runtime_pin_configured_for_validation: False
- actual_line_sent: False
- actual_email_sent: False
- production_pipeline_executed: False

Operator must set the runtime PIN hash directly on GCP. Do not paste the PIN into Codex, ChatGPT, GitHub, docs, logs, or artifacts.
