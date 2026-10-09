"""Shared strict CSV output for ordinary results; standard-library only.

This module formats already computed rows. It imports no publication,
qualification or cutover machinery; it grants no result acceptance.
"""
import csv
import io


METRIC_FIELDS = (
    "company", "cik", "metric_id", "metric_name", "value", "unit",
    "status", "source_class", "formula", "period_start", "period_end",
    "fiscal_year", "fiscal_period", "accession", "form", "filed_date",
    "concept_or_section", "context_or_dimension", "confidence", "notes",
)


EVIDENCE_FIELDS = (
    "company", "cik", "metric_id", "source_url", "repo_relative_path",
    "content_sha256", "accession", "document_name", "concept_or_section",
    "context_or_dimension", "unit", "period_start", "period_end",
    "value_raw", "value_normalized", "evidence_quote",
    "extraction_method", "parser_version",
)


class PublicationError(RuntimeError):
    """Report incomplete bundles, CAS loss, tamper, or commit failure."""


def _csv_bytes(*, rows: list, fieldnames: tuple) -> bytes:
    """Serialize one exact publication CSV deterministically.

    Args:
        rows: Ordered exact-schema string mappings.
        fieldnames: Required output column order.

    Returns:
        UTF-8 CSV bytes with stable line endings.
    """
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=list(fieldnames),
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    for row in rows:
        if set(row) != set(fieldnames):
            raise PublicationError("Generated publication CSV schema differs")
        writer.writerow({field: row[field] for field in fieldnames})
    return output.getvalue().encode("utf-8")

