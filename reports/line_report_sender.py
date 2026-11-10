import os
import requests
from dotenv import load_dotenv

load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
LINE_USER_IDS = os.getenv("LINE_USER_IDS")


def get_line_user_ids():
    if LINE_USER_IDS:
        return [
            user_id.strip()
            for user_id in LINE_USER_IDS.split(",")
            if user_id.strip()
        ]

    if LINE_USER_ID:
        return [LINE_USER_ID]

    raise ValueError("LINE_USER_ID or LINE_USER_IDS not found in .env")


def send_line_report(message):
    url = "https://api.line.me/v2/bot/message/push"

    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    status_codes = []

    for user_id in get_line_user_ids():
        payload = {
            "to": user_id,
            "messages": [
                {
                    "type": "text",
                    "text": message
                }
            ]
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=10
        )

        status_codes.append((user_id, response.status_code))

        if response.status_code >= 300:
            raise Exception(
                f"LINE push failed for {user_id}: "
                f"{response.status_code} {response.text}"
            )

    return status_codes
