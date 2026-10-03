"""Document file storage behind one interface.

  DocumentStorage.upload(user_id, data, filename, mime) -> {storage, key, url}
  DocumentStorage.secure_url(key, version_id, ttl)       -> short-lived URL
  DocumentStorage.read(key)                               -> bytes (local only)
  DocumentStorage.delete(key)

CloudinaryStorage is used when CLOUDINARY_URL is set and the `cloudinary` package
is installed. Files go up as private ("authenticated") raw assets and are served
through expiring signed download URLs. Otherwise LocalStorage keeps files under
backend/uploads/ and serves them through an HMAC-signed, expiring app URL.

Only file bytes live here. All metadata lives in the application database."""
import hashlib
import hmac
import logging
import os
import secrets
import time
import uuid
from pathlib import Path

from app.config import BASE_DIR

log = logging.getLogger("saarthi.storage")
_SECRET_FILE = BASE_DIR / ".storage_secret"


def _secret() -> bytes:
    env = os.getenv("SAARTHI_STORAGE_SECRET")
    if env:
        return env.encode()
    if not _SECRET_FILE.exists():
        _SECRET_FILE.write_text(secrets.token_hex(32))
    return _SECRET_FILE.read_text().strip().encode()


def sign(version_id: str, expires: int) -> str:
    return hmac.new(_secret(), f"{version_id}:{expires}".encode(), hashlib.sha256).hexdigest()


def verify_signature(version_id: str, expires: int, sig: str) -> bool:
    return expires >= int(time.time()) and hmac.compare_digest(sign(version_id, expires), sig or "")


class LocalStorage:
    name = "local"

    def __init__(self, root: Path = BASE_DIR / "uploads"):
        self.root = root
        self.root.mkdir(exist_ok=True)

    def upload(self, user_id: str, data: bytes, filename: str, mime: str) -> dict:
        ext = Path(filename).suffix.lower()[:8] or ".bin"
        key = f"{user_id}/{uuid.uuid4().hex}{ext}"
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return {"storage": self.name, "key": key, "url": None}

    def secure_url(self, key: str, version_id: str, ttl: int = 300) -> str:
        exp = int(time.time()) + ttl
        return f"/api/documents/file/{version_id}?exp={exp}&sig={sign(version_id, exp)}"

    def read(self, key: str) -> bytes:
        return (self.root / key).read_bytes()

    def path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise PermissionError("Path outside storage root")
        return p

    def delete(self, key: str) -> None:
        try:
            (self.root / key).unlink()
        except FileNotFoundError:
            pass


class CloudinaryStorage:
    name = "cloudinary"

    def __init__(self):
        import cloudinary  # configured from CLOUDINARY_URL by the SDK
        cloudinary.config(secure=True)
        self.folder = os.getenv("CLOUDINARY_FOLDER", "saarthi-sandbox")

    def upload(self, user_id: str, data: bytes, filename: str, mime: str) -> dict:
        import cloudinary.uploader
        public_id = f"{self.folder}/{user_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
        res = cloudinary.uploader.upload(data, public_id=public_id, resource_type="raw", type="authenticated",
                                         overwrite=False)
        return {"storage": self.name, "key": res["public_id"], "url": None}

    def secure_url(self, key: str, version_id: str, ttl: int = 300) -> str:
        import cloudinary.utils
        return cloudinary.utils.private_download_url(key, "", resource_type="raw", type="authenticated",
                                                     expires_at=int(time.time()) + ttl)

    def read(self, key: str) -> bytes:
        raise NotImplementedError("Cloudinary files are fetched by signed URL, not read server-side")

    def delete(self, key: str) -> None:
        import cloudinary.uploader
        cloudinary.uploader.destroy(key, resource_type="raw", type="authenticated")


_storage = None


def get_storage():
    global _storage
    if _storage is None:
        if os.getenv("CLOUDINARY_URL"):
            try:
                _storage = CloudinaryStorage()
            except Exception as e:  # package missing or bad config: keep the demo working
                log.warning("Cloudinary unavailable (%s) - using local storage", e)
        if _storage is None:
            _storage = LocalStorage()
    return _storage


def status() -> dict:
    s = get_storage()
    return {"backend": s.name, "cloudinary_configured": bool(os.getenv("CLOUDINARY_URL"))}
