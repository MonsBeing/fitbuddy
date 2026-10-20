from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    app_name = os.getenv("APP_NAME", "FitBuddy")
    database_url = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'fitbuddy.db').as_posix()}")
    google_api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    plan_model = os.getenv("GEMINI_PLAN_MODEL", "gemini-3.8-flash")
    tip_model = os.getenv("GEMINI_TIP_MODEL", "gemini-3.8-flash")
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    ai_timeout_seconds = float(os.getenv("AI_TIMEOUT_SECONDS", "45"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
