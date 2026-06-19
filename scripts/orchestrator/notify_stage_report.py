#!/usr/bin/env python3
"""Prepare or deliver an Orchestrator stage report notice.

Default mode is preview only. Delivery requires --send and external environment
configuration. This module never stores account settings in the repository.
"""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path
from typing import Any

ENV_HOST = "ORCH_MAIL_HOST"
ENV_PORT = "ORCH_MAIL_PORT"
ENV_USER = "ORCH_MAIL_USER"
ENV_PASS = "ORCH_MAIL_PASS"
ENV_FROM = "ORCH_MAIL_FROM"
ENV_TO = "ORCH_MAIL_TO"


def read_notice(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def first_subject_line(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("Subject:"):
            subject = line.replace("Subject:", "", 1).strip()
            if subject:
                return subject
    return "AI Orchestrator stage report"


def env_value(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def load_mail_config() -> dict[str, str]:
    config = {
        "host": env_value(ENV_HOST),
        "port": env_value(ENV_PORT) or "587",
        "user": env_value(ENV_USER),
        "password": env_value(ENV_PASS),
        "from_addr": env_value(ENV_FROM),
        "to_addr": env_value(ENV_TO),
    }
    missing = [key for key, value in config.items() if key != "port" and not value]
    if missing:
        raise ValueError("missing mail config: " + ", ".join(missing))
    return {key: str(value) for key, value in config.items()}


def build_message(config: dict[str, str], subject: str, body: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = config["from_addr"]
    message["To"] = config["to_addr"]
    message["Subject"] = subject
    message.set_content(body)
    return message


def preview_payload(subject: str, body: str) -> dict[str, Any]:
    return {
        "mode": "preview",
        "send": False,
        "subject": subject,
        "notice_chars": len(body),
        "configured_to": env_value(ENV_TO),
        "configured_from": env_value(ENV_FROM),
        "required_env": [ENV_HOST, ENV_PORT, ENV_USER, ENV_PASS, ENV_FROM, ENV_TO],
    }


def send_message(config: dict[str, str], message: EmailMessage) -> None:
    port = int(config["port"])
    if port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(config["host"], port, context=context) as server:
            server.login(config["user"], config["password"])
            server.send_message(message)
        return

    context = ssl.create_default_context()
    with smtplib.SMTP(config["host"], port) as server:
        server.starttls(context=context)
        server.login(config["user"], config["password"])
        server.send_message(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or send an Orchestrator stage report notice.")
    parser.add_argument("--notice", required=True, help="Path to rendered notice markdown.")
    parser.add_argument("--subject", help="Optional subject override.")
    parser.add_argument("--send", action="store_true", help="Actually deliver the notice.")
    args = parser.parse_args()

    body = read_notice(Path(args.notice))
    subject = args.subject or first_subject_line(body)

    if not args.send:
        json.dump(preview_payload(subject, body), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    config = load_mail_config()
    message = build_message(config, subject, body)
    send_message(config, message)
    print("sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
