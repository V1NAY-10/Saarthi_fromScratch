"""Request-scoped helpers. The sandbox app identifies the signed-in user with an
X-User-Id header (set by the frontend after registration)."""
from fastapi import Header, HTTPException

from app.database import db


def current_user(x_user_id: str | None = Header(default=None)) -> dict:
    if not x_user_id:
        raise HTTPException(401, "Sign in first")
    u = db.query_one("SELECT * FROM users WHERE id=?", (x_user_id,))
    if not u:
        raise HTTPException(401, "Unknown user - please sign in again")
    return u


def own_journey(jid: str, user: dict) -> dict:
    j = db.query_one("SELECT * FROM journeys WHERE id=?", (jid,))
    if not j or j["user_id"] != user["id"]:
        raise HTTPException(404, "Journey not found")
    return j
