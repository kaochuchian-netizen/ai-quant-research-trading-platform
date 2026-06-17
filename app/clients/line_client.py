import requests

from app.config.settings import settings


def get_line_user_ids():
    if settings.LINE_USER_IDS:
        return [
            user_id.strip()
            for user_id in settings.LINE_USER_IDS.split(",")
            if user_id.strip()
        ]

    if settings.LINE_USER_ID:
        return [settings.LINE_USER_ID]

    raise ValueError("LINE_USER_ID or LINE_USER_IDS not found in .env")


def push_line_message(message: str) -> None:
    url = "https://api.line.me/v2/bot/message/push"

    headers = {
        "Authorization": f"Bearer {settings.LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    for user_id in get_line_user_ids():
        payload = {
            "to": user_id,
            "messages": [
                {
                    "type": "text",
                    "text": message,
                }
            ],
        }

        response = requests.post(url, headers=headers, json=payload, timeout=10)

        if response.status_code >= 300:
            raise Exception(
                f"LINE push failed for {user_id}: "
                f"{response.status_code} {response.text}"
            )
