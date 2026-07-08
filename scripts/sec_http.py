"""HTTP client for audited SEC requests.

Purpose:
    Provide one configured path for SEC network access: User-Agent, global
    request pacing, retry policy, raw response persistence, and request logs.

Call relationships:
    Stage scripts call sec_pipeline.py.
    sec_pipeline.py creates SecHttpClient and calls fetch for every SEC URL.
"""

from __future__ import annotations

import csv
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class FetchResult:
    """Represent a single SEC HTTP attempt result.

    Args:
        url: Requested SEC URL.
        status_code: HTTP status code returned by SEC or 0 for transport
            failures.
        local_path: Path where raw bytes were written when available.
        sha256: SHA-256 digest of the response body, or empty string when no
            body was available.
        content_length: Response body size in bytes.
        headers_path: Path to the saved response headers JSON, or empty string.
        error: Transport or HTTP error text. Empty string means no error.

    Expected output:
        A small immutable data record that downstream code can cite in evidence.
    """

    url: str
    status_code: int
    local_path: str
    sha256: str
    content_length: int
    headers_path: str
    error: str


def load_config(*, config_path: Path) -> dict:
    """Load centralized SEC HTTP configuration.

    Args:
        config_path: UTF-8 JSON path with organization, contact_email,
            rate_limit_per_sec, max_retries, and backoff_initial_seconds.

    Returns:
        Parsed configuration dictionary.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"SEC config not found: {config_path}")
    with config_path.open(mode="r", encoding="utf-8") as file_obj:
        config = json.load(file_obj)
    required_keys = [
        "organization",
        "contact_email",
        "rate_limit_per_sec",
        "max_retries",
        "backoff_initial_seconds",
    ]
    for key in required_keys:
        if key not in config:
            raise KeyError(f"SEC config missing required key: {key}")
    return config


def utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(tz=timezone.utc).isoformat()


def ensure_parent(*, path: Path) -> None:
    """Create a file parent directory when it is missing.

    Args:
        path: File path whose parent should exist.

    Returns:
        None. The side effect is limited to directory creation.
    """
    path.parent.mkdir(parents=True, exist_ok=True)


class SecHttpClient:
    """Fetch SEC URLs with audit logging, rate limiting, and retry behavior.

    Args:
        workdir: Project root used to resolve config and evidence paths.
        config_path: Central SEC HTTP config path.
        log_path: CSV request log path.

    Expected output:
        fetch returns FetchResult and writes raw evidence files plus one log row
        per network attempt.
    """

    def __init__(self, *, workdir: Path, config_path: Path, log_path: Path) -> None:
        """Initialize the client from centralized config."""
        self.workdir = workdir
        self.config = load_config(config_path=config_path)
        self.log_path = log_path
        self.last_request_at = 0.0
        self.user_agent = (
            f"{self.config['organization']} {self.config['contact_email']}"
        )
        ensure_parent(path=self.log_path)
        if not self.log_path.exists():
            self._write_log_header()

    def fetch(self, *, url: str, purpose: str, local_path: Path) -> FetchResult:
        """Fetch a SEC URL, persist raw bytes, and return evidence metadata.

        Args:
            url: Official SEC endpoint URL.
            purpose: Short machine-readable reason for the request.
            local_path: Path where the response body should be saved.

        Returns:
            FetchResult containing status, paths, content length, and digest.
        """
        if not url.startswith("https://www.sec.gov/") and not url.startswith(
            "https://data.sec.gov/"
        ):
            raise ValueError(f"Only official SEC URLs are allowed: {url}")
        if not purpose:
            raise ValueError("purpose is required for request logging")

        max_retries = int(self.config["max_retries"])
        delay = float(self.config["backoff_initial_seconds"])
        retry_statuses = {403, 429, 500, 502, 503, 504}
        attempt = 0
        latest_result = FetchResult(
            url=url,
            status_code=0,
            local_path=str(local_path),
            sha256="",
            content_length=0,
            headers_path="",
            error="not_attempted",
        )

        while attempt <= max_retries:
            result = self._fetch_once(
                url=url,
                purpose=purpose,
                local_path=local_path,
                attempt=attempt,
            )
            latest_result = result
            if result.status_code not in retry_statuses:
                return result
            if attempt == max_retries:
                print(
                    f"SEC retry exhausted for {url}; "
                    f"status={result.status_code}; error={result.error}"
                )
                return result
            print(
                f"SEC retryable status {result.status_code} for {url}; "
                f"sleep_seconds={delay}"
            )
            time.sleep(delay)
            delay *= 2
            attempt += 1
        return latest_result

    def _fetch_once(
        self,
        *,
        url: str,
        purpose: str,
        local_path: Path,
        attempt: int,
    ) -> FetchResult:
        """Execute one HTTP attempt and log it.

        Args:
            url: Official SEC endpoint URL.
            purpose: Request purpose propagated to requests_log.csv.
            local_path: Body persistence path.
            attempt: Zero-based retry attempt number.

        Returns:
            FetchResult for this attempt.
        """
        self._pace_request()
        ensure_parent(path=local_path)
        request = Request(
            url=url,
            headers={
                "User-Agent": self.user_agent,
                "Accept-Encoding": "identity",
                "Accept": "application/json,text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=60) as response:
                body = response.read()
                status_code = int(response.status)
                headers = dict(response.headers.items())
                result = self._persist_result(
                    url=url,
                    status_code=status_code,
                    body=body,
                    headers=headers,
                    local_path=local_path,
                    error="",
                )
        except HTTPError as error:
            body = error.read()
            headers = dict(error.headers.items())
            result = self._persist_result(
                url=url,
                status_code=int(error.code),
                body=body,
                headers=headers,
                local_path=local_path,
                error=str(error),
            )
        except URLError as error:
            result = FetchResult(
                url=url,
                status_code=0,
                local_path=str(local_path),
                sha256="",
                content_length=0,
                headers_path="",
                error=str(error),
            )
        self._append_log_row(
            result=result,
            purpose=purpose,
            attempt=attempt,
        )
        return result

    def _pace_request(self) -> None:
        """Sleep when needed so the process stays within configured rate."""
        rate_limit = float(self.config["rate_limit_per_sec"])
        if rate_limit <= 0:
            raise ValueError("rate_limit_per_sec must be positive")
        min_interval = 1.0 / rate_limit
        elapsed = time.monotonic() - self.last_request_at
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_request_at = time.monotonic()

    def _persist_result(
        self,
        *,
        url: str,
        status_code: int,
        body: bytes,
        headers: dict,
        local_path: Path,
        error: str,
    ) -> FetchResult:
        """Write response body and headers to evidence files.

        Args:
            url: Official SEC endpoint URL.
            status_code: HTTP status returned by SEC.
            body: Raw response bytes.
            headers: Response headers.
            local_path: Body persistence path.
            error: Empty string for success, otherwise error text.

        Returns:
            FetchResult with digest and persisted paths.
        """
        sha256 = hashlib.sha256(body).hexdigest()
        local_path.write_bytes(body)
        headers_path = local_path.with_suffix(local_path.suffix + ".headers.json")
        headers_payload = {
            "url": url,
            "status_code": status_code,
            "headers": headers,
            "content_length": len(body),
            "sha256": sha256,
            "saved_at_utc": utc_now_iso(),
        }
        with headers_path.open(mode="w", encoding="utf-8") as file_obj:
            json.dump(headers_payload, file_obj, ensure_ascii=False, indent=2)
        return FetchResult(
            url=url,
            status_code=status_code,
            local_path=str(local_path),
            sha256=sha256,
            content_length=len(body),
            headers_path=str(headers_path),
            error=error,
        )

    def _write_log_header(self) -> None:
        """Initialize requests_log.csv with the required audit columns."""
        with self.log_path.open(mode="w", encoding="utf-8", newline="") as file_obj:
            writer = csv.writer(file_obj)
            writer.writerow(
                [
                    "timestamp_utc",
                    "method",
                    "url",
                    "status_code",
                    "purpose",
                    "local_path",
                    "headers_path",
                    "content_length",
                    "sha256",
                    "user_agent",
                    "retry_attempt",
                    "error",
                ]
            )

    def _append_log_row(
        self,
        *,
        result: FetchResult,
        purpose: str,
        attempt: int,
    ) -> None:
        """Append one request attempt to requests_log.csv."""
        with self.log_path.open(mode="a", encoding="utf-8", newline="") as file_obj:
            writer = csv.writer(file_obj)
            writer.writerow(
                [
                    utc_now_iso(),
                    "GET",
                    result.url,
                    result.status_code,
                    purpose,
                    result.local_path,
                    result.headers_path,
                    result.content_length,
                    result.sha256,
                    self.user_agent,
                    attempt,
                    result.error,
                ]
            )
