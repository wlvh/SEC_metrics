"""Load repository-owned recorded fixtures for supported operator entrypoints.

The catalog is the only discovery authority.  It binds a fixture provenance
record, exact public SEC source bytes, target period, disclosure Spec, and
recorded Reader response.  Callers select only a safe fixture ID; they cannot
provide a replacement repository root or any business locator through the
operator shortcuts.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

from .canonical import CanonicalError, content_hash, sha256_file
from .canonical import strict_json_file


CATALOG_RELATIVE_PATH = Path(
    "fixtures/vnext/recorded/operator_fixture_catalog.json"
)
_RECORDED_ROOT = Path("fixtures/vnext/recorded")
_DISCLOSURE_ROOT = Path("catalog/disclosures")
_SAFE_FIXTURE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SHA256_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_CATALOG_FIELDS = {"catalog_id", "fixtures", "schema_version"}
_ENTRY_FIELDS = {
    "disclosure_spec_path",
    "disclosure_spec_sha256",
    "display_name",
    "fixture_id",
    "provenance_id",
    "provenance_repo_relative_path",
    "provenance_sha256",
    "source_media_type",
    "source_role",
    "target_period",
}
_PERIOD_FIELDS = {"fiscal_year", "period_end", "period_start"}
_PROVENANCE_FIELDS = {
    "accession",
    "company_id",
    "derived_asset_id",
    "document_name",
    "excerpt_path",
    "excerpt_sha256",
    "fixture_id",
    "fixture_provenance_id",
    "layout_characteristics",
    "request_attempt_id",
    "response_path",
    "response_sha256",
    "schema_version",
    "selection_reason",
    "source_repo_relative_path",
    "source_sha256",
    "source_url",
    "table_id",
}


class RecordedFixtureError(RuntimeError):
    """Carry a stable fixture-discovery code across CLI boundaries."""

    def __init__(self, *, code: str, message: str) -> None:
        """Create one fail-closed recorded-fixture error.

        Args:
            code: Machine-stable uppercase error code.
            message: Concise non-sensitive operator diagnostic.
        """
        super().__init__(message)
        self.code = code


def _repository_file(
    *, repo_root: Path, relative: str, allowed_root: Optional[Path],
) -> Path:
    """Resolve one catalog locator without traversal or symlink aliases.

    Args:
        repo_root: Module-owned repository authority from the public tool.
        relative: Portable repository-relative file locator.
        allowed_root: Optional required repository subdirectory.

    Returns:
        Existing regular file below the fixed repository.
    """
    locator = Path(relative)
    if (
        not relative
        or locator.is_absolute()
        or ".." in locator.parts
        or (
            allowed_root is not None
            and locator.parts[:len(allowed_root.parts)]
            != allowed_root.parts
        )
    ):
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_LOCATOR_INVALID",
            message="Recorded fixture locator is not repository-controlled.",
        )
    if repo_root.is_symlink() or not repo_root.is_dir():
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_REPOSITORY_INVALID",
            message="Recorded fixture repository authority is unsafe.",
        )

    # Every namespace component is checked because a safe final filename can
    # still escape through a symlinked parent directory.
    path = repo_root
    for component in locator.parts:
        path = path / component
        if path.is_symlink():
            raise RecordedFixtureError(
                code="RECORDED_FIXTURE_LOCATOR_INVALID",
                message="Recorded fixture locator contains an alias.",
            )
    try:
        path.resolve().relative_to(repo_root.resolve())
    except ValueError as error:
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_LOCATOR_INVALID",
            message="Recorded fixture locator escapes the repository.",
        ) from error
    if not path.is_file():
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_BYTES_MISSING",
            message="Recorded fixture file is absent.",
        )
    return path


def _strict_json(*, path: Path, code: str) -> Mapping[str, object]:
    """Read one strict JSON object and preserve a stable failure code.

    Args:
        path: Existing non-symlink JSON file.
        code: Stable error code for invalid JSON bytes.

    Returns:
        Strict JSON object mapping.
    """
    try:
        value = strict_json_file(path=path)
    except CanonicalError as error:
        raise RecordedFixtureError(
            code=code, message="Recorded fixture JSON is invalid.",
        ) from error
    if not isinstance(value, dict):
        raise RecordedFixtureError(
            code=code, message="Recorded fixture JSON must be an object.",
        )
    return value


def _validated_period(*, value: object) -> Dict[str, object]:
    """Validate one exact fiscal-period mapping from the catalog.

    Args:
        value: Candidate target-period object.

    Returns:
        Independent validated period mapping.
    """
    if (
        not isinstance(value, dict)
        or set(value) != _PERIOD_FIELDS
        or type(value["fiscal_year"]) is not int
        or type(value["period_start"]) is not str
        or type(value["period_end"]) is not str
    ):
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_CATALOG_INVALID",
            message="Recorded fixture target period is invalid.",
        )
    try:
        period_start = date.fromisoformat(value["period_start"])
        period_end = date.fromisoformat(value["period_end"])
    except ValueError as error:
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_CATALOG_INVALID",
            message="Recorded fixture target dates are invalid.",
        ) from error
    if period_start > period_end:
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_CATALOG_INVALID",
            message="Recorded fixture target period is reversed.",
        )
    return {
        "fiscal_year": value["fiscal_year"],
        "period_start": value["period_start"],
        "period_end": value["period_end"],
    }


def _validated_entry(*, value: object) -> Dict[str, object]:
    """Validate one exact catalog entry before reading referenced bytes.

    Args:
        value: Candidate fixture catalog row.

    Returns:
        Independent entry mapping with a validated target period.
    """
    if not isinstance(value, dict) or set(value) != _ENTRY_FIELDS:
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_CATALOG_INVALID",
            message="Recorded fixture catalog entry fields differ.",
        )
    strings = (
        "disclosure_spec_path",
        "display_name",
        "fixture_id",
        "provenance_repo_relative_path",
        "source_media_type",
        "source_role",
    )
    if (
        any(
            type(value[field]) is not str or not value[field]
            for field in strings
        )
        or _SAFE_FIXTURE_ID.fullmatch(str(value["fixture_id"])) is None
        or type(value["provenance_sha256"]) is not str
        or _SHA256.fullmatch(str(value["provenance_sha256"])) is None
        or type(value["disclosure_spec_sha256"]) is not str
        or _SHA256.fullmatch(str(value["disclosure_spec_sha256"])) is None
        or type(value["provenance_id"]) is not str
        or _SHA256_ID.fullmatch(str(value["provenance_id"])) is None
    ):
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_CATALOG_INVALID",
            message="Recorded fixture catalog entry values differ.",
        )
    return {**value, "target_period": _validated_period(
        value=value["target_period"],
    )}


def _load_catalog(
    *, repo_root: Path,
) -> Tuple[str, List[Dict[str, object]]]:
    """Load and verify the exact content-addressed fixture catalog.

    Args:
        repo_root: Fixed repository authority.

    Returns:
        Catalog identity and ordered validated entries.
    """
    path = _repository_file(
        repo_root=repo_root,
        relative=CATALOG_RELATIVE_PATH.as_posix(),
        allowed_root=_RECORDED_ROOT,
    )
    catalog = _strict_json(
        path=path, code="RECORDED_FIXTURE_CATALOG_INVALID",
    )
    if (
        set(catalog) != _CATALOG_FIELDS
        or catalog["schema_version"] != 1
        or not isinstance(catalog["fixtures"], list)
        or not catalog["fixtures"]
        or type(catalog["catalog_id"]) is not str
        or _SHA256_ID.fullmatch(str(catalog["catalog_id"])) is None
    ):
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_CATALOG_INVALID",
            message="Recorded fixture catalog fields differ.",
        )
    body = {
        "schema_version": catalog["schema_version"],
        "fixtures": catalog["fixtures"],
    }
    if content_hash(value=body) != catalog["catalog_id"]:
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_CATALOG_INVALID",
            message="Recorded fixture catalog identity differs.",
        )
    entries = [
        _validated_entry(value=value) for value in catalog["fixtures"]
    ]
    fixture_ids = [str(entry["fixture_id"]) for entry in entries]
    if fixture_ids != sorted(fixture_ids) or len(fixture_ids) != len(
        set(fixture_ids)
    ):
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_CATALOG_INVALID",
            message="Recorded fixture catalog order or exact set differs.",
        )
    return str(catalog["catalog_id"]), entries


def _load_provenance(
    *, repo_root: Path, entry: Mapping[str, object],
) -> Mapping[str, object]:
    """Verify provenance identity plus every referenced immutable byte.

    Args:
        repo_root: Fixed repository authority.
        entry: Validated catalog entry.

    Returns:
        Strict fixture provenance mapping.
    """
    path = _repository_file(
        repo_root=repo_root,
        relative=str(entry["provenance_repo_relative_path"]),
        allowed_root=_RECORDED_ROOT,
    )
    if sha256_file(path=path) != entry["provenance_sha256"]:
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_PROVENANCE_INVALID",
            message="Recorded fixture provenance bytes differ.",
        )
    provenance = _strict_json(
        path=path, code="RECORDED_FIXTURE_PROVENANCE_INVALID",
    )
    string_fields = _PROVENANCE_FIELDS - {
        "layout_characteristics", "schema_version",
    }
    if (
        set(provenance) != _PROVENANCE_FIELDS
        or provenance["schema_version"] != 1
        or provenance["fixture_id"] != entry["fixture_id"]
        or provenance["fixture_provenance_id"] != entry["provenance_id"]
        or any(
            type(provenance[field]) is not str or not provenance[field]
            for field in string_fields
        )
        or not isinstance(provenance["layout_characteristics"], list)
        or not provenance["layout_characteristics"]
        or any(
            type(item) is not str or not item
            for item in provenance["layout_characteristics"]
        )
    ):
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_PROVENANCE_INVALID",
            message="Recorded fixture provenance fields differ.",
        )
    provenance_body = {
        field: provenance[field]
        for field in provenance
        if field != "fixture_provenance_id"
    }
    if content_hash(value=provenance_body) != provenance[
        "fixture_provenance_id"
    ]:
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_PROVENANCE_INVALID",
            message="Recorded fixture provenance identity differs.",
        )

    # Source, response, and excerpt bytes are checked independently so a
    # self-consistent edited provenance cannot select new operational input.
    bindings = (
        (
            "source_repo_relative_path", "source_sha256", None, False,
        ),
        ("response_path", "response_sha256", _RECORDED_ROOT, True),
        ("excerpt_path", "excerpt_sha256", _RECORDED_ROOT, True),
    )
    for path_field, hash_field, allowed_root, strict_json in bindings:
        bound_path = _repository_file(
            repo_root=repo_root,
            relative=str(provenance[path_field]),
            allowed_root=allowed_root,
        )
        if (
            _SHA256.fullmatch(str(provenance[hash_field])) is None
            or sha256_file(path=bound_path) != provenance[hash_field]
        ):
            raise RecordedFixtureError(
                code="RECORDED_FIXTURE_BYTES_INVALID",
                message="Recorded fixture content hash differs.",
            )
        if strict_json:
            _strict_json(
                path=bound_path, code="RECORDED_FIXTURE_BYTES_INVALID",
            )
    if not str(provenance["source_url"]).startswith(
        "https://www.sec.gov/Archives/"
    ):
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_PROVENANCE_INVALID",
            message="Recorded fixture source is not an official SEC archive.",
        )
    return provenance


def _materialize_fixture(
    *, repo_root: Path, catalog_id: str, entry: Mapping[str, object],
) -> Dict[str, object]:
    """Join one catalog row to its verified operational inputs.

    Args:
        repo_root: Fixed repository authority.
        catalog_id: Verified catalog content identity.
        entry: Validated catalog entry.

    Returns:
        Normalized fixture fields and one substantive binding identity.
    """
    provenance = _load_provenance(repo_root=repo_root, entry=entry)
    disclosure_path = _repository_file(
        repo_root=repo_root,
        relative=str(entry["disclosure_spec_path"]),
        allowed_root=_DISCLOSURE_ROOT,
    )
    if sha256_file(path=disclosure_path) != entry[
        "disclosure_spec_sha256"
    ]:
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_BYTES_INVALID",
            message="Recorded fixture disclosure Spec hash differs.",
        )
    body = {
        "catalog_id": catalog_id,
        "fixture_id": entry["fixture_id"],
        "provenance_id": entry["provenance_id"],
        "provenance_sha256": entry["provenance_sha256"],
        "target_period": entry["target_period"],
        "source_sha256": provenance["source_sha256"],
        "response_sha256": provenance["response_sha256"],
        "disclosure_spec_sha256": entry["disclosure_spec_sha256"],
    }
    return {
        "catalog_id": catalog_id,
        "fixture_binding_id": content_hash(value=body),
        "fixture_id": entry["fixture_id"],
        "display_name": entry["display_name"],
        "provenance": {
            "id": entry["provenance_id"],
            "repo_relative_path": entry[
                "provenance_repo_relative_path"
            ],
            "sha256": entry["provenance_sha256"],
        },
        "company_id": provenance["company_id"],
        "target_period": dict(entry["target_period"]),
        "source": {
            "accession": provenance["accession"],
            "document_name": provenance["document_name"],
            "media_type": entry["source_media_type"],
            "repo_relative_path": provenance[
                "source_repo_relative_path"
            ],
            "request_attempt_id": provenance["request_attempt_id"],
            "role": entry["source_role"],
            "sha256": provenance["source_sha256"],
            "url": provenance["source_url"],
        },
        "disclosure": {
            "spec_path": entry["disclosure_spec_path"],
            "sha256": entry["disclosure_spec_sha256"],
        },
        "response": {
            "repo_relative_path": provenance["response_path"],
            "sha256": provenance["response_sha256"],
        },
        "excerpt": {
            "repo_relative_path": provenance["excerpt_path"],
            "sha256": provenance["excerpt_sha256"],
        },
        "selection_reason": provenance["selection_reason"],
        "layout_characteristics": list(
            provenance["layout_characteristics"]
        ),
    }


def list_recorded_fixtures(*, repo_root: Path) -> Dict[str, object]:
    """Return every verified recorded fixture in deterministic order.

    Args:
        repo_root: Fixed repository authority supplied by the supported tool.

    Returns:
        Catalog identity and fully byte-verified fixture records.
    """
    catalog_id, entries = _load_catalog(repo_root=repo_root)
    return {
        "catalog_id": catalog_id,
        "fixtures": [
            _materialize_fixture(
                repo_root=repo_root, catalog_id=catalog_id, entry=entry,
            )
            for entry in entries
        ],
    }


def load_recorded_fixture(
    *, repo_root: Path, fixture_id: str,
) -> Dict[str, object]:
    """Resolve one safe ID through the repository-owned catalog.

    Args:
        repo_root: Fixed repository authority supplied by the supported tool.
        fixture_id: Safe catalog identity selected by the operator.

    Returns:
        Fully verified operational fixture mapping.
    """
    if (
        type(fixture_id) is not str
        or _SAFE_FIXTURE_ID.fullmatch(fixture_id) is None
    ):
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_ID_INVALID",
            message="Recorded fixture ID is invalid.",
        )
    catalog_id, entries = _load_catalog(repo_root=repo_root)
    matches = [entry for entry in entries if entry["fixture_id"] == fixture_id]
    if not matches:
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_NOT_FOUND",
            message="Recorded fixture ID is not in the repository catalog.",
        )
    if len(matches) != 1:
        raise RecordedFixtureError(
            code="RECORDED_FIXTURE_CATALOG_INVALID",
            message="Recorded fixture ID is duplicated in the catalog.",
        )
    return _materialize_fixture(
        repo_root=repo_root, catalog_id=catalog_id, entry=matches[0],
    )
