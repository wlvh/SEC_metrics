"""Capture one real SEC layout and fixed DeepSeek response for qualification.

The command reads only the repository-owned candidate catalog, obtains the
primary filing through ``SecHttpClient``, builds the complete table-grid and
Reader request, invokes the effective D-01 DeepSeek transport once, and writes
an immutable recorded fixture.  ``vnext_qualification.py`` later replays that
fixture without network access through the normal Reader/Evidence/Review path.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Dict, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sec_http import (  # noqa: E402
    SecHttpClient,
    parse_request_log_rows,
    request_log_attempt_id,
    validate_request_log_manifest,
    write_repository_bytes_atomically,
)
from vnext.ai_adapter import AIAdapterError  # noqa: E402
from vnext.ai_adapter import capture_deepseek_reader_response  # noqa: E402
from vnext.canonical import (  # noqa: E402
    atomic_write_json,
    content_hash,
    sha256_file,
    strict_json_file,
    strict_json_loads,
)
from vnext.qualification import (  # noqa: E402
    LAYOUT_DIFFERENCE_KINDS,
    LAYOUT_REFERENCE_INDEX,
    _layout_signature,
)
from vnext.evidence import check_evidence  # noqa: E402
from vnext.reader import ReaderError, validate_reader_output  # noqa: E402
from vnext.reader_input import (  # noqa: E402
    build_reader_input_manifest,
    prepare_reader_request,
    required_reader_roles,
)
from vnext.sources import raw_blob_record, source_reference_record  # noqa: E402
from vnext.specs import SpecError, compile_spec_file  # noqa: E402
from vnext.table_grid import TableGridError, build_table_grid, resolve_cell  # noqa: E402


_CANDIDATE_PATH = REPO_ROOT / "fixtures/vnext/qualification_candidates.json"
_FIXTURE_ROOT = REPO_ROOT / "fixtures/vnext/layouts"
_SAFE_FIXTURE = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
_CANDIDATE_FIELDS = {
    "accession",
    "cik",
    "company_id",
    "company_traits",
    "disclosure_spec_path",
    "display_name",
    "document_name",
    "fixture_id",
    "qualification_role",
    "selection_reason",
    "source_media_type",
    "source_role",
    "source_url",
    "target_period",
}


class CaptureError(RuntimeError):
    """Carry a stable non-secret capture failure code."""

    def __init__(self, *, code: str, message: str) -> None:
        """Create a terse error that is safe to print in JSON output.

        Args:
            code: Stable uppercase machine code.
            message: Concise non-sensitive explanation.
        """
        super().__init__(message)
        self.code = code


def _candidate(*, fixture_id: str) -> Dict[str, object]:
    """Load one exact repository-owned qualification candidate.

    Args:
        fixture_id: Safe catalog identifier selected by the operator.

    Returns:
        Validated immutable candidate mapping.

    Raises:
        CaptureError: If catalog bytes, schema, or the requested identity are
            absent, unsafe, or ambiguous.
    """
    if (
        not fixture_id
        or any(character not in _SAFE_FIXTURE for character in fixture_id)
    ):
        raise CaptureError(
            code="QUALIFICATION_CAPTURE_ID_INVALID",
            message="Fixture identity is invalid",
        )
    if _CANDIDATE_PATH.is_symlink() or not _CANDIDATE_PATH.is_file():
        raise CaptureError(
            code="QUALIFICATION_CAPTURE_CATALOG_MISSING",
            message="Qualification candidate catalog is absent",
        )
    catalog = strict_json_file(path=_CANDIDATE_PATH)
    if (
        not isinstance(catalog, dict)
        or set(catalog) != {"candidates", "schema_version"}
        or catalog["schema_version"] != 1
        or not isinstance(catalog["candidates"], list)
    ):
        raise CaptureError(
            code="QUALIFICATION_CAPTURE_CATALOG_INVALID",
            message="Qualification candidate catalog fields are invalid",
        )
    matches = [
        value for value in catalog["candidates"]
        if isinstance(value, dict) and value["fixture_id"] == fixture_id
    ]
    if len(matches) != 1:
        raise CaptureError(
            code="QUALIFICATION_CAPTURE_CANDIDATE_NOT_FOUND",
            message="Qualification candidate is absent or ambiguous",
        )
    value = dict(matches[0])
    if (
        set(value) != _CANDIDATE_FIELDS
        or value["fixture_id"] != fixture_id
        or value["qualification_role"]
        not in {"SECOND_LAYOUT", "POST_FREEZE_HOLDOUT"}
        or any(
            type(value[field]) is not str or not value[field]
            for field in (
                "accession",
                "cik",
                "company_id",
                "disclosure_spec_path",
                "display_name",
                "document_name",
                "selection_reason",
                "source_media_type",
                "source_role",
                "source_url",
            )
        )
        or not isinstance(value["company_traits"], list)
        or value["company_traits"] != sorted(set(value["company_traits"]))
        or not value["company_traits"]
        or any(
            type(trait) is not str or not trait
            for trait in value["company_traits"]
        )
        or not isinstance(value["target_period"], dict)
        or set(value["target_period"])
        != {"fiscal_year", "period_end", "period_start"}
    ):
        raise CaptureError(
            code="QUALIFICATION_CAPTURE_CANDIDATE_INVALID",
            message="Qualification candidate fields are invalid",
        )
    return value


def _request_attempt_id(*, result: object) -> str:
    """Derive the exact append-only SEC attempt identity for one fetch.

    Args:
        result: Successful ``SecHttpClient.fetch`` result.

    Returns:
        Content-derived request attempt identity from the current ledger row.

    Raises:
        CaptureError: If the successful fetch cannot be uniquely matched to
            immutable body/header evidence in the ledger.
    """
    log_path = REPO_ROOT / "evidence/requests_log.csv"
    validate_request_log_manifest(log_path=log_path)
    snapshot = Path(str(result.local_path))
    try:
        relative = snapshot.relative_to(REPO_ROOT).as_posix()
    except ValueError as error:
        raise CaptureError(
            code="QUALIFICATION_CAPTURE_LEDGER_INVALID",
            message="SEC response path escapes repository",
        ) from error
    rows = parse_request_log_rows(text=log_path.read_text(encoding="utf-8"))
    matching_indices = [
        index for index, row in enumerate(rows)
        if row["source_url"] == result.url
        and row["status_code"] == "200"
        and row["repo_relative_path"] == relative
        and row["content_sha256"] == result.sha256
        and row["content_length"] == str(result.content_length)
        and row["error"] == ""
    ]
    if not matching_indices:
        raise CaptureError(
            code="QUALIFICATION_CAPTURE_LEDGER_INVALID",
            message="SEC request attempt is absent from the ledger",
        )
    # Identical SEC body retries intentionally share immutable bytes.  The
    # newest matching append is the attempt produced by this completed fetch.
    index = matching_indices[-1]
    return request_log_attempt_id(row_index=index, row=rows[index])


def _excerpt(
    *, derived_asset: Mapping[str, object], response: Mapping[str, object],
    raw_asset_id: str,
) -> Dict[str, object]:
    """Keep only model-addressed cells needed to replay layout differences.

    Args:
        derived_asset: Complete table-grid built from the SEC filing.
        response: Strict model JSON already validated against that grid.
        raw_asset_id: Exact raw filing identity for the excerpt binding.

    Returns:
        Stable de-duplicated excerpt of selected and scope evidence cells.
    """
    locators = []
    for candidate in response["candidates"]:
        locators.append(candidate["locator"])
        for evidence in candidate["scope_evidence_locators"]:
            locators.append(evidence["locator"])
    cells = {}
    for locator in locators:
        cell = resolve_cell(derived_asset=derived_asset, locator=locator)
        key = (
            cell["row_index"], cell["column_index"],
            cell["origin_row_index"], cell["origin_column_index"],
        )
        cells[key] = {
            "row_index": cell["row_index"],
            "column_index": cell["column_index"],
            "origin_row_index": cell["origin_row_index"],
            "origin_column_index": cell["origin_column_index"],
            "rowspan": cell["rowspan"],
            "colspan": cell["colspan"],
            "text": cell["text"],
        }
    return {
        "derived_asset_id": derived_asset["derived_asset_id"],
        "table_id": response["table_locator"]["table_id"],
        "source_raw_asset_id": raw_asset_id,
        "cells": [
            cells[key] for key in sorted(cells)
        ],
    }


def _layout_differences(
    *, excerpt: Mapping[str, object], response: Mapping[str, object],
) -> list[str]:
    """Derive, rather than declare, differences from the reference anchor.

    Args:
        excerpt: Candidate selected-cell excerpt.
        response: Candidate strict Reader response.

    Returns:
        Ordered difference kinds accepted by qualification replay.

    Raises:
        CaptureError: If the candidate is not materially different in at least
            two mechanically derived dimensions.
    """
    reference_index = strict_json_file(path=REPO_ROOT / LAYOUT_REFERENCE_INDEX)
    provenance_path = REPO_ROOT / Path(
        str(reference_index["provenance_repo_relative_path"])
    )
    provenance = strict_json_file(path=provenance_path)
    reference_excerpt = strict_json_file(
        path=REPO_ROOT / Path(str(provenance["excerpt_path"]))
    )
    reference_response = strict_json_file(
        path=REPO_ROOT / Path(str(provenance["response_path"]))
    )
    candidate_signature = _layout_signature(
        excerpt=excerpt, response=response,
    )
    reference_signature = _layout_signature(
        excerpt=reference_excerpt, response=reference_response,
    )
    if candidate_signature["roles"] != reference_signature["roles"]:
        raise CaptureError(
            code="QUALIFICATION_CAPTURE_ROLE_SET_INVALID",
            message="Reader role set differs from the disclosure contract",
        )
    differences = [
        kind for kind in sorted(LAYOUT_DIFFERENCE_KINDS)
        if candidate_signature["component_ids"][kind]
        != reference_signature["component_ids"][kind]
    ]
    if (
        candidate_signature["grid_id"] == reference_signature["grid_id"]
        or len(differences) < 2
    ):
        raise CaptureError(
            code="QUALIFICATION_CAPTURE_LAYOUT_INSUFFICIENT",
            message="SEC layout has fewer than two replayable differences",
        )
    return differences


def capture(*, fixture_id: str) -> Dict[str, object]:
    """Fetch, read, and persist one real qualification fixture.

    Args:
        fixture_id: Fixed candidate identifier from the repository catalog.

    Returns:
        Fixture, SEC ledger, and provider-envelope identities without secrets.

    Raises:
        CaptureError: On unsafe target state or failed source/model validation.
    """
    candidate = _candidate(fixture_id=fixture_id)
    fixture_root = _FIXTURE_ROOT / fixture_id
    if fixture_root.exists():
        raise CaptureError(
            code="QUALIFICATION_CAPTURE_FIXTURE_EXISTS",
            message="Qualification fixture already exists and is immutable",
        )
    working_source = (
        REPO_ROOT / "evidence/accession_materials/qualification"
        / fixture_id / str(candidate["document_name"])
    )
    client = SecHttpClient(
        workdir=REPO_ROOT,
        config_path=REPO_ROOT / "config/sec_config.json",
        log_path=REPO_ROOT / "evidence/requests_log.csv",
    )
    result = client.fetch(
        url=str(candidate["source_url"]),
        purpose="vnext_qualification_layout_capture",
        local_path=working_source,
    )
    if result.status_code != 200 or not result.sha256 or result.error:
        raise CaptureError(
            code="QUALIFICATION_CAPTURE_SEC_FETCH_FAILED",
            message="SEC filing fetch did not return a clean 200 response",
        )
    source_snapshot = Path(result.local_path)
    try:
        source_relative = source_snapshot.relative_to(REPO_ROOT).as_posix()
    except ValueError as error:
        raise CaptureError(
            code="QUALIFICATION_CAPTURE_SEC_PATH_INVALID",
            message="SEC immutable response path escapes repository",
        ) from error
    request_attempt_id = _request_attempt_id(result=result)
    raw_blob = raw_blob_record(
        repo_root=REPO_ROOT,
        repo_relative_path=source_relative,
        media_type=str(candidate["source_media_type"]),
    )
    source_reference = source_reference_record(
        raw_blob=raw_blob,
        company_id=str(candidate["company_id"]),
        source_url=str(candidate["source_url"]),
        accession=str(candidate["accession"]),
        document_name=str(candidate["document_name"]),
        source_role=str(candidate["source_role"]),
        request_attempt_id=request_attempt_id,
    )
    try:
        compiled_spec = compile_spec_file(
            path=REPO_ROOT / Path(str(candidate["disclosure_spec_path"])),
            dependency_specs={},
        )
        derived_asset = build_table_grid(
            html_bytes=source_snapshot.read_bytes(),
            parent_raw_asset_ids=[str(raw_blob["raw_asset_id"])],
            storage_uri=(
                "fixtures/vnext/layouts/{}/derived_asset.json".format(
                    fixture_id
                )
            ),
        )
        reader_manifest = build_reader_input_manifest(
            derived_asset=derived_asset,
            source_reference_ids=[
                str(source_reference["source_reference_id"])
            ],
        )
        prepared_request = prepare_reader_request(
            manifest=reader_manifest,
            derived_asset=derived_asset,
            compiled_spec=compiled_spec,
        )
        transport = capture_deepseek_reader_response(
            prepared_request=prepared_request,
        )
        response = strict_json_loads(
            text=transport.response_bytes.decode("utf-8")
        )
        candidate_record = validate_reader_output(
            response_text=transport.response_bytes.decode("utf-8"),
            attempt_id="attempt:qualification-capture:" + fixture_id,
            required_roles=required_reader_roles(compiled_spec=compiled_spec),
            source_reference_ids=[
                str(source_reference["source_reference_id"])
            ],
            derived_asset_ids=[str(derived_asset["derived_asset_id"])],
        )
        evidence = check_evidence(
            candidate=candidate_record,
            derived_asset=derived_asset,
            reader_manifest=reader_manifest,
            reader_payload_body=strict_json_loads(
                text=prepared_request.request_bytes.decode("utf-8")
            ),
            source_references=[source_reference],
            identity_constraints=compiled_spec["compiled"][
                "identity_constraints"
            ],
        )
        if evidence["status"] != "PASS":
            raise CaptureError(
                code="QUALIFICATION_CAPTURE_EVIDENCE_REJECTED",
                message="Reader response failed mechanical evidence checks",
            )
        excerpt = _excerpt(
            derived_asset=derived_asset,
            response=response,
            raw_asset_id=str(raw_blob["raw_asset_id"]),
        )
        layout_differences = _layout_differences(
            excerpt=excerpt, response=response,
        )
    except CaptureError:
        raise
    except (
        AIAdapterError, ReaderError, SpecError, TableGridError, UnicodeDecodeError,
        ValueError,
    ) as error:
        raise CaptureError(
            code="QUALIFICATION_CAPTURE_READER_FAILED",
            message="DeepSeek response did not form a replayable layout",
        ) from error
    if (
        transport.raw_response_bytes is None
        or transport.outbound_request_bytes is None
        or transport.output_schema_bytes is None
    ):
        raise CaptureError(
            code="QUALIFICATION_CAPTURE_TRANSPORT_INCOMPLETE",
            message="DeepSeek capture lacks required audit bytes",
        )
    fixture_root.mkdir(parents=True, exist_ok=False)
    source_path = fixture_root / "source.htm"
    response_path = fixture_root / "recorded_response.json"
    excerpt_path = fixture_root / "excerpt.json"
    raw_provider_path = fixture_root / "provider_response.json"
    outbound_path = fixture_root / "provider_request.json"
    schema_path = fixture_root / "provider_schema.json"
    write_repository_bytes_atomically(
        workdir=REPO_ROOT,
        path=source_path,
        content=source_snapshot.read_bytes(),
    )
    write_repository_bytes_atomically(
        workdir=REPO_ROOT,
        path=response_path,
        content=transport.response_bytes,
    )
    write_repository_bytes_atomically(
        workdir=REPO_ROOT,
        path=raw_provider_path,
        content=transport.raw_response_bytes,
    )
    write_repository_bytes_atomically(
        workdir=REPO_ROOT,
        path=outbound_path,
        content=transport.outbound_request_bytes,
    )
    write_repository_bytes_atomically(
        workdir=REPO_ROOT,
        path=schema_path,
        content=transport.output_schema_bytes,
    )
    atomic_write_json(path=excerpt_path, value=excerpt)
    fixture_relative = fixture_root.relative_to(REPO_ROOT)
    manifest = {
        "schema_version": 1,
        "fixture_id": fixture_id,
        "qualification_role": candidate["qualification_role"],
        "company_id": candidate["company_id"],
        "cik": candidate["cik"],
        "company_traits": candidate["company_traits"],
        "target_period": candidate["target_period"],
        "source_role": candidate["source_role"],
        "source_media_type": candidate["source_media_type"],
        "source_url": candidate["source_url"],
        "accession": candidate["accession"],
        "document_name": candidate["document_name"],
        "disclosure_spec_path": candidate["disclosure_spec_path"],
        "selection_reason": candidate["selection_reason"],
        "layout_differences": layout_differences,
        "request_attempt_id": request_attempt_id,
        "source_repo_relative_path": (
            fixture_relative / source_path.name
        ).as_posix(),
        "source_sha256": sha256_file(path=source_path),
        "recorded_response_repo_relative_path": (
            fixture_relative / response_path.name
        ).as_posix(),
        "recorded_response_sha256": sha256_file(path=response_path),
        "excerpt_repo_relative_path": (
            fixture_relative / excerpt_path.name
        ).as_posix(),
        "excerpt_sha256": sha256_file(path=excerpt_path),
    }
    capture_body = {
        "schema_version": 1,
        "fixture_id": fixture_id,
        "source_url": candidate["source_url"],
        "source_request_attempt_id": request_attempt_id,
        "source_sha256": sha256_file(path=source_path),
        "transport_observation": transport.observation.as_mapping(),
        "provider_request_id": transport.provider_request_id,
        "assistant_output_repo_relative_path": (
            fixture_relative / response_path.name
        ).as_posix(),
        "assistant_output_sha256": sha256_file(path=response_path),
        "provider_response_repo_relative_path": (
            fixture_relative / raw_provider_path.name
        ).as_posix(),
        "provider_response_sha256": sha256_file(path=raw_provider_path),
        "provider_request_repo_relative_path": (
            fixture_relative / outbound_path.name
        ).as_posix(),
        "provider_request_sha256": sha256_file(path=outbound_path),
        "provider_schema_repo_relative_path": (
            fixture_relative / schema_path.name
        ).as_posix(),
        "provider_schema_sha256": sha256_file(path=schema_path),
    }
    capture_receipt = {
        **capture_body,
        "capture_id": content_hash(value=capture_body),
    }
    atomic_write_json(
        path=fixture_root / "capture_receipt.json", value=capture_receipt,
    )
    atomic_write_json(path=fixture_root / "fixture_manifest.json", value=manifest)
    return {
        "status": "CAPTURED",
        "fixture_id": fixture_id,
        "fixture_manifest": (
            fixture_relative / "fixture_manifest.json"
        ).as_posix(),
        "request_attempt_id": request_attempt_id,
        "capture_id": capture_receipt["capture_id"],
        "layout_differences": layout_differences,
    }


def main(*, argv: Sequence[str]) -> int:
    """Run one fixture capture with stable non-secret terminal diagnostics.

    Args:
        argv: CLI tokens excluding the executable path.

    Returns:
        Zero only after a real SEC filing and DeepSeek response are persisted.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--fixture-id", required=True)
    arguments = parser.parse_args(list(argv))
    try:
        output = capture(fixture_id=arguments.fixture_id)
    except CaptureError as error:
        print(json.dumps({
            "status": "BLOCKED",
            "error_code": error.code,
            "message": str(error),
        }, ensure_ascii=False, sort_keys=True))
        if arguments.debug and error.__cause__ is not None:
            traceback.print_exception(
                type(error.__cause__),
                error.__cause__,
                error.__cause__.__traceback__,
                file=sys.stderr,
            )
        return 2
    except Exception as error:
        print(json.dumps({
            "status": "BLOCKED",
            "error_code": "QUALIFICATION_CAPTURE_FAILED",
            "message": "Qualification fixture capture failed",
            "details": {"error_class": type(error).__name__},
        }, ensure_ascii=False, sort_keys=True))
        if arguments.debug:
            traceback.print_exc(file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
