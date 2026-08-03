"""Load report inputs only from one already pinned PublicationView.

The module does not repair data, call AI, open SEC connections, or write
authoritative artifacts. A future Cutover report generator can consume the
returned exact bytes without falling back to mutable repository-root files.
"""

from __future__ import annotations

from typing import Dict

from .publication import PublicationView


REPORT_INPUT_FILES = (
    "coverage_matrix.csv",
    "golden_results.csv",
    "metric_evidence.csv",
    "metrics_matrix.csv",
    "repair_validation_results.csv",
    "stratified_audit.csv",
    "validation_run_manifest.json",
)


def load_report_inputs(
    *, publication_view: PublicationView
) -> Dict[str, bytes]:
    """Read every report input from exactly one immutable publication.

    Args:
        publication_view: Pinned and verified publication boundary.

    Returns:
        Required relative paths mapped to verified bytes.
    """
    return {
        relative: publication_view.read_bytes(relative_path=relative)
        for relative in REPORT_INPUT_FILES
    }
