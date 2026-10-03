"""Partner connectors + normalization layer.

Every partner call goes through `call()`, which records the raw request/response
and converts the partner's dialect into one standard shape:

    {partner_id, partner_name, state, raw_code, raw_message}

state is one of SUCCESS | FAILED | PENDING | VERIFIED
"""
from app.database import db
from app.partners import simulators

_OK_CODES = {"DEBIT_OK", "BAV_OK", "MANDATE_OK", "IMPS_SUCCESS", "ACK"}


def _normalize(pid: str, op: str, raw: dict) -> dict:
    code, msg, state = None, None, "PENDING"
    p = simulators.PARTNERS.get(pid) or simulators.get(pid)
    if isinstance(p, simulators.SandboxBank) and p.dialect == "nach":
        code, msg = raw.get("respCode"), raw.get("respMsg")
        flag = raw.get("txnStatus") or raw.get("bavStatus")
        if flag:
            state = {"S": "SUCCESS", "F": "FAILED", "P": "PENDING"}[flag]
            if raw.get("bavStatus") == "S":
                state = "VERIFIED"
        elif code == "00":
            state = "SUCCESS"
        if code == "00":
            code = None
    elif isinstance(p, simulators.SandboxBank):
        st = raw.get("status") or {}
        code, msg = st.get("code"), st.get("desc")
        if code in _OK_CODES:
            state = "VERIFIED" if code == "BAV_OK" else "SUCCESS"
            code = None
        elif code:
            state = "FAILED"
    elif type(p).__name__ == "ApplicationPartner" and op == "diagnose":
        state, code = "PENDING", None
    elif type(p).__name__ == "ApplicationPartner":
        if p.dialect == "nested":
            st = raw.get("status") or {}
            code, msg, appstate = st.get("code"), st.get("desc"), st.get("state")
        else:
            code, msg, appstate = raw.get("reasonCode"), raw.get("reasonText"), raw.get("appStatus")
            if code == "00":
                code = None
        if appstate in ("DISBURSED", "ISSUED", "VERIFIED"):
            state, code = "SUCCESS", None
        elif appstate == "PENDING":
            state = "PENDING"
        elif appstate in ("REJECTED", "ERROR"):
            state = "FAILED"
        else:
            state, code = "PENDING", None
    elif pid == "aa":
        code, state = raw.get("status"), "SUCCESS" if raw.get("status") == "DATA_READY" else "FAILED"
    elif pid == "nsdl":
        code = raw.get("pan_status")
        state = "VERIFIED" if code == "E" else "FAILED"
    else:
        state = "SUCCESS" if raw.get("ack") else "PENDING"
    partner = db.query_one("SELECT name FROM partners WHERE id=?", (pid,))
    from app.knowledge import registry
    return {"partner_id": pid, "partner_name": partner["name"] if partner else registry.partner_name(pid), "state": state,
            "raw_code": code, "raw_message": msg}


def call(pid: str, op: str, journey_id: str | None = None, **kwargs) -> dict:
    partner = simulators.get(pid)
    raw = getattr(partner, op)(**kwargs)
    norm = _normalize(pid, op, raw)
    db.insert("partner_responses", {"journey_id": journey_id, "partner_id": pid, "endpoint": op,
                                    "request": kwargs, "raw": raw, "normalized": norm, "ts": db.now_iso()})
    endpoint = f"GET /partner/{pid}/journey/{kwargs.get('ref')}" if op == "get_journey" \
        else f"POST /partner/{pid}/{op.replace('_', '-')}"
    return {"raw": raw, "normalized": norm, "endpoint": endpoint}
