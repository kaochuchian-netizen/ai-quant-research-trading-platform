import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    SINOPAC_API_KEY = os.getenv("SINOPAC_API_KEY")
    SINOPAC_SECRET_KEY = os.getenv("SINOPAC_SECRET_KEY")
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    LINE_USER_ID = os.getenv("LINE_USER_ID")
    GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
    GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")


settings = Settings()
