"""Document Vault API. Every route is scoped to the signed-in user."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from app.api.deps import current_user
from app.database import db
from app.product import vault
from app.services import samples, storage

router = APIRouter(prefix="/api", tags=["vault"])


@router.get("/documents")
def list_documents(user=Depends(current_user)):
    return vault.list_for(user)


@router.post("/documents")
async def upload_document(file: UploadFile = File(...), doc_type: str | None = Form(default=None),
                          replace_document_id: str | None = Form(default=None), user=Depends(current_user)):
    data = await file.read(vault.MAX_BYTES + 1)
    return vault.upload(user, data, file.filename or "document", file.content_type or "", doc_type, replace_document_id)


@router.get("/documents/{doc_id}")
def get_document(doc_id: str, user=Depends(current_user)):
    return vault.get(user, doc_id)


@router.get("/documents/versions/{version_id}/url")
def document_url(version_id: str, user=Depends(current_user)):
    return {"url": vault.secure_url(user, version_id), "expires_in": 300}


@router.get("/documents/file/{version_id}")
def document_file(version_id: str, exp: int, sig: str):
    """Local-storage file delivery. Authorised by the signed, expiring URL from /url."""
    if not storage.verify_signature(version_id, exp, sig):
        raise HTTPException(403, "Link expired or invalid")
    v = db.query_one("SELECT * FROM document_versions WHERE id=?", (version_id,))
    st = storage.get_storage()
    if not v or not v["file_key"] or not isinstance(st, storage.LocalStorage):
        raise HTTPException(404, "File not found")
    return FileResponse(st.path(v["file_key"]), media_type=v["mime_type"], filename=v["original_name"],
                        headers={"Cache-Control": "private, no-store"})


@router.get("/samples")
def list_samples():
    return [{"kind": k, "label": label} for k, label in samples.SAMPLES.items()]


@router.get("/samples/{kind}")
def sample_document(kind: str, user=Depends(current_user)):
    if kind not in samples.SAMPLES:
        raise HTTPException(404, "Unknown sample")
    acc = db.query_one("SELECT * FROM accounts WHERE user_id=? AND status='VERIFIED' ORDER BY created_at", (user["id"],))
    data, filename = samples.generate(kind, user, acc)
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
