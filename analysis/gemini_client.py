import os
from functools import lru_cache

from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()


class GeminiClient:

    def __init__(self, model_name="gemini-2.5-flash"):
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in .env")

        self.client = _client(api_key)
        self.model_name = model_name

    def generate(self, prompt, *, structured=False):
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            text = response.text
            if structured:
                return {"status": "SUCCESS" if isinstance(text, str) and text.strip() else "PARSE_ERROR",
                        "text": text if isinstance(text, str) else "", "reason_code": None if text else "AI_EMPTY_RESPONSE"}
            return text

        except Exception as e:
            if structured:
                message = f"{type(e).__name__} {e}".lower()
                code = ("TIMEOUT" if any(x in message for x in ("timeout", "deadline", "504")) else
                        "QUOTA" if any(x in message for x in ("429", "quota", "resource_exhausted")) else
                        "PARSE_ERROR" if isinstance(e, (ValueError, TypeError)) else "TRANSPORT_ERROR")
                return {"status": code, "reason_code": "AI_" + code, "text": ""}
            return f"Gemini Error: {str(e)}"


def generate_analysis(prompt, *, structured=False):
    try:
        client = GeminiClient()
        return client.generate(prompt, structured=structured)
    except Exception:
        if structured:
            return {"status": "CONFIGURATION_ERROR", "reason_code": "AI_CLIENT_UNAVAILABLE", "text": ""}
        raise


@lru_cache(maxsize=1)
def _client(api_key: str):
    """Reuse one process client with bounded request and retry policy."""
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=12_000,
            retry_options=types.HttpRetryOptions(
                attempts=2, initial_delay=0.5, max_delay=0.5, exp_base=1.0, jitter=0.0,
            ),
        ),
    )
