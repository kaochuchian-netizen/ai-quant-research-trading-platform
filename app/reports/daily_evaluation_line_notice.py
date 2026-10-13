"""One idempotent, completion-only LINE notice for a valid natural 17:00 review."""
from __future__ import annotations

import json
import os
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION="daily_evaluation_line_notice_v1"


def public_dashboard_url(base_url: str) -> str:
    return base_url.rstrip("/")+"/dashboard/daily-evaluation/latest/index.html"


def message(base_url: str) -> str:
    return "【17:00 策略檢討】\n今日策略檢討已完成\n查看 Dashboard："+public_dashboard_url(base_url)


def _identity(value: dict[str, Any]) -> dict[str, str]:
    identity=str(value.get("identity") or "")
    date=str(value.get("report_date") or "")
    if len(identity)!=64 or not date or value.get("status")!="VALID":
        raise ValueError("DAILY_NOTICE_EVALUATION_INVALID")
    return {"identity":identity,"report_date":date,"channel":"line","kind":"daily_evaluation_completion"}


def _receipt_path(root: Path, identity: dict[str, str]) -> Path:
    token=sha256(json.dumps(identity,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return root/(token+".json")


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix=".daily-evaluation-line-",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as handle:
            json.dump(value,handle,sort_keys=True,ensure_ascii=False)
            handle.write("\n");handle.flush();os.fsync(handle.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp): os.unlink(temp)


def deliver(*, value: dict[str, Any], dashboard: dict[str, Any], base_url: str, sender: Callable[[str], Any], receipt_root: Path) -> dict[str, Any]:
    """Send only after immutable evaluation and public Dashboard publication both succeed."""
    if dashboard.get("status")!="PUBLISHED":
        return {"send_attempted":False,"send_status":"suppressed_dashboard_not_published","secret_values_printed":False}
    identity=_identity(value)
    path=_receipt_path(Path(receipt_root),identity)
    if path.exists():
        try: saved=json.loads(path.read_text(encoding="utf-8"))
        except (OSError,ValueError,TypeError):
            return {"send_attempted":False,"send_status":"suppressed_invalid_receipt","secret_values_printed":False}
        if saved.get("schema_version")==SCHEMA_VERSION and saved.get("identity")==identity and saved.get("status")=="sent":
            return {"send_attempted":False,"send_status":"already_delivered","secret_values_printed":False}
        return {"send_attempted":False,"send_status":"suppressed_existing_receipt","secret_values_printed":False}
    text=message(base_url)
    try:
        sender(text)
    except Exception as exc:
        return {"send_attempted":True,"send_status":"failed","error_type":exc.__class__.__name__,"secret_values_printed":False}
    _atomic_json(path,{"schema_version":SCHEMA_VERSION,"status":"sent","identity":identity,"message_sha256":sha256(text.encode()).hexdigest()})
    return {"send_attempted":True,"send_status":"sent","secret_values_printed":False}
