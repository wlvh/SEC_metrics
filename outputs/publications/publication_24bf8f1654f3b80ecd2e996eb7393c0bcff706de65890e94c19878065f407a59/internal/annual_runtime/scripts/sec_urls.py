"""Build SEC official endpoint URLs for the single-year metrics spike.

Purpose:
    Keep all endpoint formatting in one place so callers pass explicit data
    such as CIK and accession and never duplicate URL string rules.

Call relationships:
    Stage scripts call functions in sec_pipeline.py.
    sec_pipeline.py calls these URL builders before sec_http.SecHttpClient.fetch.
"""

SEC_WEB_BASE = "https://www.sec.gov"
SEC_DATA_BASE = "https://data.sec.gov"


def cik10(*, cik: int) -> str:
    """Return a ten-digit CIK string required by SEC data endpoints.

    Args:
        cik: Positive integer CIK. Range is the SEC assigned integer space.

    Returns:
        Ten-character zero-padded CIK string.

    Expected output:
        A positive integer CIK returns a ten-character zero-padded string.
    """
    if cik <= 0:
        raise ValueError(f"CIK must be positive, got {cik}")
    return f"{cik:010d}"


def accession_no_dash(*, accession: str) -> str:
    """Return accession without dashes for SEC archive paths.

    Args:
        accession: SEC accession in dashed format.

    Returns:
        Accession with dashes removed.
    """
    if not accession:
        raise ValueError("accession is required")
    return accession.replace("-", "")


def company_tickers_exchange_url() -> str:
    """Return the official SEC company ticker association endpoint URL."""
    return f"{SEC_WEB_BASE}/files/company_tickers_exchange.json"


def submissions_url(*, cik: int) -> str:
    """Return the official SEC submissions endpoint URL for one CIK."""
    return f"{SEC_DATA_BASE}/submissions/CIK{cik10(cik=cik)}.json"


def submissions_file_url(*, file_name: str) -> str:
    """Return a SEC submissions supplemental file URL.

    Args:
        file_name: Name from submissions.filings.files.

    Returns:
        Official SEC supplemental submissions JSON URL.
    """
    if not file_name:
        raise ValueError("file_name is required")
    return f"{SEC_DATA_BASE}/submissions/{file_name}"


def companyfacts_url(*, cik: int) -> str:
    """Return the official SEC companyfacts endpoint URL for one CIK."""
    return f"{SEC_DATA_BASE}/api/xbrl/companyfacts/CIK{cik10(cik=cik)}.json"


def companyconcept_url(*, cik: int, taxonomy: str, concept: str) -> str:
    """Return the official SEC companyconcept endpoint URL for one concept.

    Args:
        cik: Positive integer CIK.
        taxonomy: SEC taxonomy segment, for example "us-gaap".
        concept: XBRL concept local name, for example "AssetsCurrent".

    Returns:
        SEC companyconcept URL.
    """
    if not taxonomy:
        raise ValueError("taxonomy is required")
    if not concept:
        raise ValueError("concept is required")
    return (
        f"{SEC_DATA_BASE}/api/xbrl/companyconcept/"
        f"CIK{cik10(cik=cik)}/{taxonomy}/{concept}.json"
    )


def accession_directory_url(*, cik: int, accession: str) -> str:
    """Return the SEC archive directory index URL for one accession."""
    return (
        f"{SEC_WEB_BASE}/Archives/edgar/data/{cik}/"
        f"{accession_no_dash(accession=accession)}/index.json"
    )


def accession_document_url(*, cik: int, accession: str, document_name: str) -> str:
    """Return a SEC archive document URL for one accession document."""
    if not document_name:
        raise ValueError("document_name is required")
    return (
        f"{SEC_WEB_BASE}/Archives/edgar/data/{cik}/"
        f"{accession_no_dash(accession=accession)}/{document_name}"
    )


def hdr_sgml_url(*, cik: int, accession: str) -> str:
    """Return the SEC archive hdr.sgml URL for one accession."""
    return accession_document_url(
        cik=cik,
        accession=accession,
        document_name=f"{accession}.hdr.sgml",
    )


def filing_detail_url(*, cik: int, accession: str) -> str:
    """Return the SEC filing detail HTML page URL for one accession."""
    return accession_document_url(
        cik=cik,
        accession=accession,
        document_name=f"{accession}-index.html",
    )


def filing_summary_url(*, cik: int, accession: str) -> str:
    """Return the SEC FilingSummary.xml URL for one accession."""
    return accession_document_url(
        cik=cik,
        accession=accession,
        document_name="FilingSummary.xml",
    )
