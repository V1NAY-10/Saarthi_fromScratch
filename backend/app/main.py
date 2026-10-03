import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import config
from app.agents import orchestrator
from app.api import app_routes, applications, journeys, knowledge, partner, planner, saarthi, vault
from app.database import db, seed
from app.knowledge import retrieval
from app.product.journeys import NotFound, ProductError

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Saarthi API", description="AI operating layer for financial journeys", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

for r in (app_routes.router, journeys.router, knowledge.router, saarthi.router, partner.router, vault.router, applications.router, planner.router):
    app.include_router(r)


@app.exception_handler(ProductError)
def product_error(_: Request, e: ProductError):
    return JSONResponse(status_code=404 if isinstance(e, NotFound) else 400, content={"detail": str(e)})


@app.on_event("startup")
def startup():
    current = db.query_one("SELECT name FROM sqlite_master WHERE type='table' AND name='document_versions'")
    if not current or not db.query_one("SELECT id FROM funds LIMIT 1"):
        seed.seed()  # first run, or a database from an older schema: start a clean sandbox
    else:
        db.init_schema()
        seed.load_knowledge()  # the Markdown knowledge base may have changed
    retrieval.start_background_ingest()
    orchestrator.resume_stale()
    logging.getLogger("saarthi").info("Saarthi ready · demo_mode=%s · agent=%s", config.DEMO_MODE,
                                      "claude" if config.llm_enabled() else "deterministic")


@app.get("/api/health")
def healthcheck():
    return {"ok": True}
