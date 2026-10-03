import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEMO_MODE = os.getenv("DEMO_MODE", "true").strip().lower() in ("1", "true", "yes")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
SAARTHI_MODEL = os.getenv("SAARTHI_MODEL", "claude-opus-5-5").strip()
DB_PATH = Path(os.getenv("SAARTHI_DB", str(BASE_DIR / "saarthi.db")))


def llm_enabled() -> bool:
    return (not DEMO_MODE) and bool(ANTHROPIC_API_KEY)
