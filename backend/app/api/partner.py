"""Sandbox partner HTTP surface (read + retry). These endpoints return each partner's raw dialect
(un-normalized) - the same functions Saarthi's connectors call."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.partners import simulators

router = APIRouter(prefix="/partner", tags=["mock partners"])


class RefBody(BaseModel):
    ref: str


class StatusBody(RefBody):
    status: str


def _partner(pid: str, op: str):
    try:
        p = simulators.get(pid)
    except simulators.PartnerError as e:
        raise HTTPException(404, str(e))
    if not hasattr(p, op):
        raise HTTPException(405, f"{pid} does not support {op}")
    return getattr(p, op)


def _run(fn, **kw):
    try:
        return fn(**kw)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.get("/{pid}/journey/{ref}")
def journey(pid: str, ref: str):
    return _run(_partner(pid, "get_journey"), ref=ref)


@router.post("/{pid}/diagnose")
def diagnose(pid: str, body: RefBody):
    return _run(_partner(pid, "diagnose"), ref=body.ref)


@router.post("/{pid}/retry")
def retry(pid: str, body: RefBody):
    return _run(_partner(pid, "retry"), ref=body.ref)


@router.post("/{pid}/update-status")
def update_status(pid: str, body: StatusBody):
    return _run(_partner(pid, "update_status"), ref=body.ref, status=body.status)
