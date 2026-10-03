import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

DEMO_MODE = os.getenv("DEMO_MODE", "true").strip().lower() in ("1", "true", "yes")
DB_PATH = Path(os.getenv("SAARTHI_DB", str(BASE_DIR / "saarthi.db")))

# ---- LLM provider: Gemini (google-genai)
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
LLM_PROVIDER = "gemini"
SAARTHI_MODEL = GEMINI_MODEL

# Legacy aliases kept so existing references don't crash
ANTHROPIC_API_KEY = ""
ANTHROPIC_MODEL = ""


def llm_key() -> str:
    return GEMINI_API_KEY


def llm_enabled() -> bool:
    return (not DEMO_MODE) and bool(GEMINI_API_KEY)
