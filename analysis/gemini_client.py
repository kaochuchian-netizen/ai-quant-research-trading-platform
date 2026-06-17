import os

from dotenv import load_dotenv
from google import genai


load_dotenv()


class GeminiClient:

    def __init__(self, model_name="gemini-2.5-flash"):
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in .env")

        self.client = genai.Client(api_key=api_key)
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
