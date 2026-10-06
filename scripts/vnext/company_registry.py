"""Canonical company rows, without release or Run construction."""
import csv
from pathlib import Path
from typing import Dict, List
from .request_bindings import BatchWorkflowError

def _registry_rows(*, repo_root: Path) -> List[Dict[str, str]]:
    """Read the canonical company registry in stable order.

    Args:
        repo_root: Repository containing ``config/company_registry.csv``.

    Returns:
        Ordered company rows.
    """
    path = repo_root / "config" / "company_registry.csv"
    if path.is_symlink() or not path.is_file():
        raise BatchWorkflowError("Company registry is unsafe or absent")
    with path.open(mode="r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        if reader.fieldnames is None or not {
            "company_id",
            "display_name",
            "primary_cik",
        }.issubset(reader.fieldnames):
            raise BatchWorkflowError("Company registry fields are incomplete")
        rows = [dict(row) for row in reader]
    if not rows or len(rows) != len({row["company_id"] for row in rows}):
        raise BatchWorkflowError("Company registry identities are ambiguous")
    return rows
