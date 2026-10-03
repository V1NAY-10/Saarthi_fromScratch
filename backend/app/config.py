import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# Real environment variables (set by the hosting platform) win over a local .env file.
load_dotenv(BASE_DIR / ".env", override=False)

DEMO_MODE = os.getenv("DEMO_MODE", "true").strip().lower() in ("1", "true", "yes")

# Writable state (SQLite DB, uploaded files, storage signing secret). Point this at a
# persistent volume in production; defaults to the backend folder for local dev.
DATA_DIR = Path(os.getenv("SAARTHI_DATA_DIR", str(BASE_DIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.getenv("SAARTHI_DB", str(DATA_DIR / "saarthi.db")))

# Built frontend (vite build output). When present, the API also serves the web app.
FRONTEND_DIST = Path(os.getenv("SAARTHI_FRONTEND_DIST", str(BASE_DIR.parent / "frontend" / "dist")))

# Comma-separated list of allowed browser origins; "*" allows any (fine for the sandbox).
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

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
