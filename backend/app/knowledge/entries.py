"""Compatibility view over the Markdown knowledge base (knowledge/ at the repo root).

The knowledge itself lives in Markdown; see app/knowledge/registry.py. These
names are kept so existing engines and the sandbox banks keep working."""
from app.knowledge import registry

BANK_NAMES = {"axis": "Axis Bank", "icici": "ICICI Bank", "hdfc": "HDFC Bank", "sbi": "SBI"}


class _BankCodes(dict):
    """BANK_CODES[bank][failure_type] -> that bank's code, resolved from the registry."""

    def __missing__(self, bank):
        return {ft: c for (pid, ft), c in registry.load()["by_type"].items() if pid == bank}


BANK_CODES = _BankCodes()
