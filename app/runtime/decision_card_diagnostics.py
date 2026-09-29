"""Bounded aggregate diagnostics only; never changes admission or cards."""
from collections import Counter
import re

def decision_card_failure_evidence(historical_admission, failed_reports, card_count):
    def reason(value):
        value = str(value or "UNSPECIFIED")
        return value if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]{0,95}", value) else "UNSTRUCTURED_REASON"
    excluded = [r for r in historical_admission if r.get("status") != "ADMITTED"]
    return {"schema_version":"decision_card_admission_diagnostic_v1",
            "requested_count":len(historical_admission),
            "historical_admitted_count":len(historical_admission)-len(excluded),
            "decision_card_count":card_count,
            "historical_exclusion_reasons":dict(sorted(Counter(reason(r.get("exclusion_reason")) for r in excluded).items())),
            "analysis_failure_reasons":dict(sorted(Counter(reason(r.get("reason")) for r in failed_reports if not r.get("exclusion_stage")).items())),
            "admission_modified":False}
