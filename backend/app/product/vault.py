"""Saarthi Document Vault.

Upload once, reuse across journeys. Each upload is validated, stored through the
storage abstraction (Cloudinary or local), read by document intelligence and
recorded as a *version*. Uploading the same kind of document again (same type;
for statements, same account) adds a new version instead of replacing the old
one, and journeys record the exact version they used."""
import hashlib
import uuid

from app.database import db
from app.product.journeys import NotFound, ProductError
from app.services import docintel, journal, storage

MAX_BYTES = 5 * 1024 * 1024
ALLOWED = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg", "text/plain": ".txt"}
SINGLE_INSTANCE = {"PAN", "AADHAAR", "DRIVING_LICENCE", "SALARY_SLIP", "FORM16", "MEDICAL_REPORT"}


def _sniff(data: bytes, declared: str) -> str:
    """Trust the bytes, not the browser's Content-Type."""
    if data[:5] == b"%PDF-":
        return "application/pdf"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if declared == "text/plain":
        try:
            data[:4096].decode("utf-8")
            return "text/plain"
        except UnicodeDecodeError:
            pass
    return "application/octet-stream"


def upload(user: dict, data: bytes, filename: str, declared_mime: str, doc_type_hint: str | None = None,
           replace_document_id: str | None = None) -> dict:
    if not data:
        raise ProductError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise ProductError("Files must be 5 MB or smaller.")
    mime = _sniff(data, declared_mime)
    if mime not in ALLOWED:
        raise ProductError("Upload a PDF, PNG, JPG or plain-text file.")
    file_hash = hashlib.sha256(data).hexdigest()
    dup = db.query_one("SELECT * FROM document_versions WHERE user_id=? AND file_hash=?", (user["id"], file_hash))
    if dup:
        return get(user, dup["document_id"]) | {"duplicate": True}

    text = docintel.extract_text(data, mime)
    readable = bool(text.strip())
    doc_type = docintel.classify(text, filename, doc_type_hint)
    fields = docintel.parse(doc_type, text) if readable else {}
    c = docintel.checks(doc_type, fields, readable, user)
    status = docintel.status_for(doc_type, fields, c)

    target = None
    if replace_document_id:
        target = db.query_one("SELECT * FROM documents WHERE id=? AND user_id=?", (replace_document_id, user["id"]))
        if not target:
            raise NotFound("Document not found.")
    elif doc_type in SINGLE_INSTANCE:
        target = db.query_one("SELECT * FROM documents WHERE user_id=? AND doc_type=? AND source!='registry' "
                              "ORDER BY updated_at DESC", (user["id"], doc_type))
    elif doc_type == "BANK_STATEMENT" and fields.get("account_masked"):
        for d in db.query("SELECT * FROM documents WHERE user_id=? AND doc_type='BANK_STATEMENT'", (user["id"],)):
            if (d["meta"] or {}).get("account_masked") == fields["account_masked"]:
                target = d
                break

    stored = storage.get_storage().upload(user["id"], data, filename, mime)
    doc_id = target["id"] if target else f"doc-{uuid.uuid4().hex[:8]}"
    version = (target["latest_version"] or 0) + 1 if target else 1
    vid = f"dv-{uuid.uuid4().hex[:8]}"
    now = db.now_iso()
    db.insert("document_versions", {"id": vid, "document_id": doc_id, "user_id": user["id"], "version": version,
                                    "storage": stored["storage"], "file_key": stored["key"], "file_url": stored["url"],
                                    "file_hash": file_hash, "mime_type": mime, "size": len(data),
                                    "original_name": filename[:120], "uploaded_at": now, "status": status,
                                    "extracted_text": text[:20000], "fields": fields, "checks": c})
    meta = docintel.public_fields(fields)
    row = {"id": doc_id, "user_id": user["id"], "doc_type": doc_type, "name": docintel.TYPE_LABEL[doc_type],
           "status": status, "source": f"Uploaded · {stored['storage']} storage", "updated_at": now,
           "meta": {**meta, "summary": docintel.summary(doc_type, fields)}, "latest_version": version,
           "latest_version_id": vid, "verification_status": status, "expiry_date": fields.get("expiry_date")}
    db.insert("documents", row)
    journal.audit(None, "vault", "DOCUMENT_UPLOADED",
                  f"{docintel.TYPE_LABEL[doc_type]} v{version} added to vault ({status.lower().replace('_', ' ')})",
                  {"document_id": doc_id, "version": version, "storage": stored["storage"], "size": len(data)},
                  user_id=user["id"])
    _notify_waiting_journeys(user, doc_type)
    return get(user, doc_id)


def _notify_waiting_journeys(user: dict, doc_type: str) -> None:
    """A journey waiting for a document re-plans as soon as a candidate arrives."""
    from app.agents import orchestrator
    for j in db.query("SELECT * FROM journeys WHERE user_id=? AND status='ATTENTION'", (user["id"],)):
        want = j["state"].get("waiting_for_document")
        if want and (want == doc_type or (want == "IDENTITY" and doc_type in docintel.IDENTITY_TYPES)):
            orchestrator.reopen(j["id"], f"New {docintel.TYPE_LABEL[doc_type].lower()} added to your vault")


def create_registry_record(user: dict, pan_ok: bool) -> None:
    """KYC from the PAN registry: a verified PAN record with no uploaded file."""
    did, vid, now = f"doc-pan-{user['id']}", f"dv-pan-{user['id']}", db.now_iso()
    fields = {"name": user["name"], "dob": user["dob"], "pan_masked": user["pan"][:5] + "••••" + user["pan"][-1],
              "_pan_hash": user["pan"]}
    status = "VERIFIED" if pan_ok else "FAILED"
    db.insert("document_versions", {"id": vid, "document_id": did, "user_id": user["id"], "version": 1,
                                    "storage": "registry", "file_key": None, "file_url": None, "file_hash": None,
                                    "mime_type": None, "size": 0, "original_name": None, "uploaded_at": now,
                                    "status": status, "extracted_text": "",
                                    "fields": fields, "checks": {"readable": True, "name_match": 1.0,
                                                                  "dob_match": True, "pan_match": True}})
    db.insert("documents", {"id": did, "user_id": user["id"], "doc_type": "PAN", "name": "PAN (registry record)",
                            "status": status, "source": "registry", "updated_at": now,
                            "meta": {**docintel.public_fields(fields), "summary": fields["pan_masked"]},
                            "latest_version": 1, "latest_version_id": vid, "verification_status": status,
                            "expiry_date": None})


def _public_version(v: dict) -> dict:
    return {"id": v["id"], "version": v["version"], "status": v["status"], "uploaded_at": v["uploaded_at"],
            "mime_type": v["mime_type"], "size": v["size"], "original_name": v["original_name"],
            "storage": v["storage"], "fields": docintel.public_fields(v["fields"] or {}), "checks": v["checks"],
            "has_file": bool(v["file_key"])}


def get(user: dict, doc_id: str) -> dict:
    d = db.query_one("SELECT * FROM documents WHERE id=? AND user_id=?", (doc_id, user["id"]))
    if not d:
        raise NotFound("Document not found.")
    versions = db.query("SELECT * FROM document_versions WHERE document_id=? ORDER BY version DESC", (doc_id,))
    used = db.query("""SELECT jd.journey_id, jd.role, jd.version_id, j.title FROM journey_documents jd
                       JOIN journeys j ON j.id = jd.journey_id WHERE jd.document_id=?""", (doc_id,))
    return {**d, "versions": [_public_version(v) for v in versions], "used_by": used}


def list_for(user: dict) -> list[dict]:
    docs = db.query("SELECT * FROM documents WHERE user_id=? ORDER BY updated_at DESC", (user["id"],))
    return [get(user, d["id"]) for d in docs]


def version(user: dict, version_id: str) -> dict:
    v = db.query_one("SELECT * FROM document_versions WHERE id=? AND user_id=?", (version_id, user["id"]))
    if not v:
        raise NotFound("Document not found.")
    return v


def secure_url(user: dict, version_id: str) -> str:
    v = version(user, version_id)
    if not v["file_key"]:
        raise ProductError("This record has no uploaded file.")
    return storage.get_storage().secure_url(v["file_key"], v["id"])


def latest_versions(user_id: str) -> list[dict]:
    """Latest version of every vault document, with server-side fields (for Saarthi's checks)."""
    out = []
    for d in db.query("SELECT * FROM documents WHERE user_id=? ORDER BY updated_at DESC", (user_id,)):
        v = db.query_one("SELECT * FROM document_versions WHERE id=?", (d["latest_version_id"],))
        if v:
            out.append({"document_id": d["id"], "doc_type": d["doc_type"], "name": d["name"], "version_id": v["id"],
                        "version": v["version"], "status": v["status"], "fields": v["fields"] or {},
                        "checks": v["checks"] or {}, "uploaded_at": v["uploaded_at"]})
    return out
