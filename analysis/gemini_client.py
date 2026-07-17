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

    def generate(self, prompt):
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            return response.text

        except Exception as e:
            return f"Gemini Error: {str(e)}"


def generate_analysis(prompt):
    client = GeminiClient()
    return client.generate(prompt)


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
