"""Build and publish the Issue #15 zero-AI release ratchet.

Purpose:
    R1 imports the verified legacy root as predecessor A, freezes the ten
    B01/B03 structured Runs from immutable SEC attempts, prepares successor B,
    and executes the required A -> B -> A -> B cold-start transaction.

Call relationships:
    ``tools/vnext_zero_ai_release.py`` calls :func:`publish_r1`.  Source-plan
    construction reuses ``batch_workflow`` and ``deterministic_router``;
    structured execution reuses the existing Run state machine; publication
    uses the private formal primitives that remain unavailable to generic
    callers.  Every persistent receipt is built from returned data rather than
    caller-asserted status.
"""

from __future__ import annotations

import csv
import io
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

from sec_http import request_log_manifest_payload

from git_workspace import sanitized_git_environment
from .batch_workflow import build_release_input_plan, request_attempt_binding
from .canonical import atomic_write_bytes, canonical_json_bytes, content_hash
from .canonical import parse_utc_timestamp, sha256_bytes, sha256_file
from .cutover import _freeze_structured_run
from .deterministic_router import adapt_accession_xbrl
from .deterministic_router import build_multi_source_release_input_plan
from .deterministic_router import source_role_plan, source_set_manifest
from .invocation_control import structured_only_result
from .publication import PublicationView, REQUIRED_BUNDLE_FILES
from .publication import ROOT_MIRROR_RELATIVE_PATHS, ZERO_AI_FORMAL_MANIFEST
from .publication import _commit_initial_publication_chain
from .publication import _commit_publication, _write_prepared_publication_bundle
from .publication import prepare_issue15_legacy_baseline_predecessor
from .publication import publication_layout, publication_state_snapshot
from .publication import rollback_publication, verify_publication_bundle
from .projection_independence import build_projection_independence_receipt
from .public_projection import assemble_public_rows, compare_public_rows
from .public_projection import COVERAGE_FIELDS, METRICS_FIELDS
from .public_projection import csv_bytes, render_coverage_rows
from .public_projection import load_public_projection_catalog
from .public_projection import projection_xbrl_concepts
from .public_projection import render_public_rows
from .requirements import load_requirement_snapshot
from .run_store import load_run_for_status
from .source_strategy import load_issue15_release_plan
from .sources import raw_blob_record, source_reference_record


R1_METRIC_IDS = ("B01", "B03")
R1_EXPECTED_COORDINATES = 20
R1_EXPECTED_LEGACY_ROWS = 18
R1_EXPECTED_NEW_KEYS = 2
R1_EXPECTED_PUBLIC_ROWS = 232
ZERO_AI_NOTE_START = "<!-- zero-ai-formal-publication:start -->"
ZERO_AI_NOTE_END = "<!-- zero-ai-formal-publication:end -->"
class ZeroAiReleaseError(ValueError):
    """Report a source, result, compatibility, or publication invariant."""


def _source_commit_binding(
    *, repo_root: Path, source_commit: str,
) -> Dict[str, str]:
    """Bind one reachable source commit and its exact Git tree object."""
    if (
        not isinstance(source_commit, str)
        or len(source_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_commit)
    ):
        raise ZeroAiReleaseError("Source commit must be a full SHA")
    environment = sanitized_git_environment()
    resolved = subprocess.run(
        args=["git", "rev-parse", source_commit + "^{commit}"],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )
    tree = subprocess.run(
        args=["git", "rev-parse", source_commit + "^{tree}"],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )
    ancestor = subprocess.run(
        args=["git", "merge-base", "--is-ancestor", source_commit, "HEAD"],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        env=environment,
    )
    resolved_commit = resolved.stdout.strip()
    source_tree_oid = tree.stdout.strip()
    if (
        resolved.returncode != 0
        or tree.returncode != 0
        or ancestor.returncode != 0
        or resolved_commit != source_commit
        or len(source_tree_oid) != 40
    ):
        raise ZeroAiReleaseError("Source commit is not a reachable Git ancestor")
    return {
        "source_commit": resolved_commit,
        "source_tree_oid": source_tree_oid,
    }


def _json_bytes(*, value: object) -> bytes:
    """Return canonical UTF-8 JSON with one terminal newline.

    Args:
        value: JSON-compatible value.

    Returns:
        Stable bytes used by content-addressed receipts.
    """
    return canonical_json_bytes(value=value) + b"\n"


def _utc_sequence(*, committed_at_utc: str) -> Tuple[str, str, str]:
    """Return ordered commit, rollback, and restore UTC timestamps.

    Args:
        committed_at_utc: Explicit initial transaction timestamp.

    Returns:
        Three ISO 8601 UTC values separated by one second.
    """
    parsed = parse_utc_timestamp(value=committed_at_utc)
    normalized = parsed.astimezone(timezone.utc)
    return tuple(
        (normalized + timedelta(seconds=offset))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
        for offset in range(3)
    )


def _csv_rows(*, content: bytes, fields: Sequence[str]) -> List[Dict[str, str]]:
    """Parse exact UTF-8 CSV bytes and require the expected header.

    Args:
        content: Candidate CSV bytes.
        fields: Exact ordered field names.

    Returns:
        Isolated string rows.
    """
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    except UnicodeDecodeError as error:
        raise ZeroAiReleaseError("Release CSV is not UTF-8") from error
    if tuple(reader.fieldnames or ()) != tuple(fields):
        raise ZeroAiReleaseError("Release CSV header differs")
    rows = [dict(row) for row in reader]
    if any(set(row) != set(fields) for row in rows):
        raise ZeroAiReleaseError("Release CSV row fields differ")
    return rows


def _append_csv_rows(
    *, original: bytes, fields: Sequence[str], rows: Sequence[Mapping[str, str]]
) -> bytes:
    """Append rows without rewriting any predecessor byte.

    Args:
        original: Frozen predecessor CSV bytes.
        fields: Exact ordered CSV header.
        rows: New rows using that header.

    Returns:
        Original byte prefix followed by deterministic UTF-8 rows.
    """
    if not original.endswith(b"\n"):
        raise ZeroAiReleaseError("Frozen CSV lacks a terminal newline")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=list(fields), lineterminator="\n",
    )
    for row in rows:
        if set(row) != set(fields):
            raise ZeroAiReleaseError("Appended CSV row fields differ")
        writer.writerow(dict(row))
    return original + stream.getvalue().encode("utf-8")


def _append_publication_note(
    *, original: bytes, release_stage: str,
    cumulative_metric_ids: Sequence[str], public_matrix_row_count: int,
) -> bytes:
    """Append one generated zero-AI status block to public Markdown.

    Args:
        original: Predecessor README or report bytes.
        release_stage: Ratchet stage represented by this bundle.
        cumulative_metric_ids: Exact active migrated metric set.
        public_matrix_row_count: Exact candidate matrix row count.

    Returns:
        UTF-8 Markdown with one non-duplicated generated status block.
    """
    try:
        text = original.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ZeroAiReleaseError("Public Markdown is not UTF-8") from error
    starts = text.count(ZERO_AI_NOTE_START)
    ends = text.count(ZERO_AI_NOTE_END)
    if starts != ends or starts > 1:
        raise ZeroAiReleaseError("Public zero-AI note is ambiguous")
    if starts == 1:
        start = text.index(ZERO_AI_NOTE_START)
        end = text.index(ZERO_AI_NOTE_END) + len(ZERO_AI_NOTE_END)
        if text[end:].strip():
            raise ZeroAiReleaseError("Public zero-AI note is not terminal")
        text = text[:start]
    block = """

{start}
## Issue #15 零 AI 正式发布

- release stage：`{stage}`
- cumulative migrated metric IDs：`{metrics}`
- public matrix rows：`{rows}`
- `real_model_provider_egress_count = 0`
- `paid_model_provider_call_count = 0`
- Issue #15 full acceptance：`NOT_RUN`（本 bundle 只证明当前零 AI ratchet）
- 当前版本必须由 `outputs/active_publication.json` 与对应 immutable bundle
  联合识别；本段不自报 publication ID。
{end}
""".format(
        start=ZERO_AI_NOTE_START,
        stage=release_stage,
        metrics=", ".join(cumulative_metric_ids),
        rows=public_matrix_row_count,
        end=ZERO_AI_NOTE_END,
    )
    return (text.rstrip() + block).encode("utf-8")


def _registry_rows(*, repo_root: Path) -> List[Dict[str, str]]:
    """Load the exact ten-company registry.

    Args:
        repo_root: Repository containing company authority.

    Returns:
        Ordered registry rows.
    """
    path = repo_root / "config" / "company_registry.csv"
    with path.open(mode="r", encoding="utf-8", newline="") as file_obj:
        rows = [dict(row) for row in csv.DictReader(file_obj)]
    if len(rows) != 10 or len({row["company_id"] for row in rows}) != 10:
        raise ZeroAiReleaseError("Company registry exact set differs")
    return rows


def _filing_identity(
    *, inventory_bytes: bytes, accession: str
) -> Tuple[str, str]:
    """Resolve one accession's exact form and filing date.

    Args:
        inventory_bytes: Pinned SEC submissions JSON bytes.
        accession: Filing accession selected by the release plan.

    Returns:
        Form type and ISO filing date.
    """
    descriptor = _filing_descriptor(
        inventory_bytes=inventory_bytes, accession=accession,
    )
    return str(descriptor["form"]), str(descriptor["filing_date"])


def _filing_descriptor(
    *, inventory_bytes: bytes, accession: str,
) -> Dict[str, str]:
    """Resolve one accession's form, date, and primary document."""
    try:
        payload = json.loads(inventory_bytes.decode("utf-8"))
        recent = payload["filings"]["recent"]
        accessions = recent["accessionNumber"]
        forms = recent["form"]
        dates = recent["filingDate"]
        primary_documents = recent["primaryDocument"]
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ZeroAiReleaseError("SEC submissions inventory is invalid") from error
    matches = [
        {
            "form": str(forms[index]),
            "filing_date": str(dates[index]),
            "primary_document": str(primary_documents[index]),
        }
        for index, candidate in enumerate(accessions)
        if candidate == accession
    ]
    if len(matches) != 1 or any(not value for value in matches[0].values()):
        raise ZeroAiReleaseError("Release accession is absent from submissions")
    return matches[0]


def _accession_instance_descriptor(
    *, repo_root: Path, company_id: str, cik: str,
    filing: Mapping[str, str],
) -> Dict[str, str]:
    """Resolve one submissions-declared 10-K to its local XBRL instance."""
    accession_digits = filing["accession"].replace("-", "")
    suffix = "_{}_{}".format(str(int(cik)), accession_digits)
    directories = [
        path
        for path in (repo_root / "evidence" / "accession_materials").iterdir()
        if path.is_dir() and path.name.endswith(suffix)
    ]
    if len(directories) != 1:
        raise ZeroAiReleaseError(
            "10-K accession directory is ambiguous: " + company_id
        )
    primary = str(filing["primary_document"])
    if "." not in primary:
        raise ZeroAiReleaseError("10-K primary document name is invalid")
    document_name = primary.rsplit(".", maxsplit=1)[0] + "_htm.xml"
    path = directories[0] / document_name
    if path.is_symlink() or not path.is_file():
        raise ZeroAiReleaseError("10-K XBRL instance is absent")
    return {
        "accession": filing["accession"],
        "document_name": document_name,
        "repo_relative_path": path.relative_to(repo_root).as_posix(),
        "source_url": (
            "https://www.sec.gov/Archives/edgar/data/{}/{}/{}".format(
                str(int(cik)), accession_digits, document_name,
            )
        ),
    }


def _source_reference(
    *, repo_root: Path, company_id: str, repo_relative_path: str,
    source_url: str, accession: str, document_name: str, source_role: str,
    media_type: str,
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """Build one immutable-attempt-backed SourceReference.

    Args:
        repo_root: Repository containing raw bytes and request ledger.
        company_id: Logical company identity.
        repo_relative_path: Existing exact SEC response path.
        source_url: Exact official SEC URL.
        accession: Filing or pinned inventory identity.
        document_name: SEC document name.
        source_role: Deterministic plan role.
        media_type: Explicit RawBlob media type.

    Returns:
        SourceReference and complete immutable locator binding.
    """
    raw = raw_blob_record(
        repo_root=repo_root,
        repo_relative_path=repo_relative_path,
        media_type=media_type,
    )
    binding = request_attempt_binding(
        repo_root=repo_root,
        source_url=source_url,
        content_sha256=str(raw["raw_asset_id"]).split(":", maxsplit=1)[1],
        accession=accession,
        document_name=document_name,
    )
    if binding["request_locator_kind"] != "IMMUTABLE_ATTEMPT":
        raise ZeroAiReleaseError("Formal zero-AI source is not immutable")
    reference = source_reference_record(
        raw_blob=raw,
        company_id=company_id,
        source_url=source_url,
        accession=accession,
        document_name=document_name,
        source_role=source_role,
        request_attempt_id=str(binding["request_attempt_id"]),
    )
    return reference, binding


def _r1_source_plan(
    *, repo_root: Path, legacy_snapshot_dir: Path,
) -> Tuple[
    Dict[str, object], List[Dict[str, object]], Dict[str, object],
    List[Dict[str, object]],
]:
    """Build the R1 ``sources[]`` plan and transient Run inputs.

    Args:
        repo_root: Repository authority root.
        legacy_snapshot_dir: Frozen legacy public snapshot.

    Returns:
        Multi-source plan, scalar-compatible structured Run inputs, locator
        proof index, and projection-only deterministic XBRL claims.
    """
    issue_plan = load_issue15_release_plan(
        repo_root=repo_root, release_plan_id="issue_15_zero_ai_r1",
    )
    if tuple(issue_plan["cumulative_metric_ids"]) != R1_METRIC_IDS:
        raise ZeroAiReleaseError("R1 cumulative metric exact set differs")
    projection_catalog = load_public_projection_catalog(
        repo_root=repo_root, expected_metric_ids=R1_METRIC_IDS,
    )
    projection_concepts = projection_xbrl_concepts(
        catalog=projection_catalog,
    )
    if not projection_concepts:
        raise ZeroAiReleaseError("R1 projection XBRL concepts are absent")
    run_plan = build_release_input_plan(
        repo_root=repo_root, legacy_snapshot_dir=legacy_snapshot_dir,
    )
    registry = {
        row["company_id"]: row for row in _registry_rows(repo_root=repo_root)
    }
    references = []
    manifests = []
    company_rows = []
    locator_proofs = {}
    projection_claims = []
    for company in run_plan["companies"]:
        company_id = str(company["company_id"])
        sources = []
        if company["mode"] == "COMPANYFACTS":
            source = company["companyfacts_source"]
            company_reference, company_binding = _source_reference(
                repo_root=repo_root,
                company_id=company_id,
                repo_relative_path=str(source["repo_relative_path"]),
                source_url=str(source["source_url"]),
                accession=str(source["accession"]),
                document_name=str(source["document_name"]),
                source_role="companyfacts",
                media_type="application/json",
            )
            cik = str(int(registry[company_id]["primary_cik"])).zfill(10)
            inventory_name = "CIK{}.json".format(cik)
            inventory_path = "evidence/submissions/" + inventory_name
            inventory_url = (
                "https://data.sec.gov/submissions/" + inventory_name
            )
            inventory_bytes = (repo_root / inventory_path).read_bytes()
            inventory_reference, inventory_binding = _source_reference(
                repo_root=repo_root,
                company_id=company_id,
                repo_relative_path=inventory_path,
                source_url=inventory_url,
                accession="SUBMISSIONS-{}".format(
                    company["target_period"]["fiscal_year"]
                ),
                document_name=inventory_name,
                source_role="sec_submissions_inventory",
                media_type="application/json",
            )
            filing = _filing_descriptor(
                inventory_bytes=inventory_bytes,
                accession=str(source["accession"]),
            )
            form = str(filing["form"])
            filed = str(filing["filing_date"])
            manifest = source_set_manifest(
                company_id=company_id,
                source_role="companyfacts",
                form_types=[form],
                fiscal_or_date_window={
                    "period_start": filed,
                    "period_end": filed,
                },
                discovery_policy="PINNED_SUBMISSIONS_EXACT_FILING_V1",
                inventory_source_reference=inventory_reference,
                inventory_bytes=inventory_bytes,
                ordered_source_references=[company_reference],
                cutoff_timestamp_or_pinned_submissions_attempt=str(
                    inventory_reference["request_attempt_id"]
                ),
            )
            instance_descriptor = _accession_instance_descriptor(
                repo_root=repo_root,
                company_id=company_id,
                cik=registry[company_id]["primary_cik"],
                filing={
                    "accession": str(source["accession"]),
                    "primary_document": str(filing["primary_document"]),
                },
            )
            instance_reference, instance_binding = _source_reference(
                repo_root=repo_root,
                company_id=company_id,
                repo_relative_path=instance_descriptor["repo_relative_path"],
                source_url=instance_descriptor["source_url"],
                accession=instance_descriptor["accession"],
                document_name=instance_descriptor["document_name"],
                source_role="public_projection_accession_instance",
                media_type="application/xml",
            )
            instance_manifest = source_set_manifest(
                company_id=company_id,
                source_role="public_projection_accession_instance",
                form_types=[form],
                fiscal_or_date_window={
                    "period_start": filed,
                    "period_end": filed,
                },
                discovery_policy="PINNED_SUBMISSIONS_EXACT_FILING_V1",
                inventory_source_reference=inventory_reference,
                inventory_bytes=inventory_bytes,
                ordered_source_references=[instance_reference],
                cutoff_timestamp_or_pinned_submissions_attempt=str(
                    inventory_reference["request_attempt_id"]
                ),
            )
            instance_bytes = (
                repo_root / instance_descriptor["repo_relative_path"]
            ).read_bytes()
            projection_claims.extend(
                adapt_accession_xbrl(
                    raw_bytes=instance_bytes,
                    source_reference=instance_reference,
                    source_set_manifest=instance_manifest,
                    fact_names=projection_concepts,
                )
            )
            references.extend(
                [inventory_reference, company_reference, instance_reference]
            )
            manifests.extend([manifest, instance_manifest])
            sources.append(
                source_role_plan(
                    manifest=manifest, source_mode="STRUCTURED_JSON",
                )
            )
            sources.append(
                source_role_plan(
                    manifest=instance_manifest,
                    source_mode="ACCESSION_XBRL",
                )
            )
            locator_proofs[str(inventory_reference["source_reference_id"])] = {
                **inventory_binding,
                "source_reference": inventory_reference,
            }
            locator_proofs[str(company_reference["source_reference_id"])] = {
                **company_binding,
                "source_reference": company_reference,
            }
            locator_proofs[str(instance_reference["source_reference_id"])] = {
                **instance_binding,
                "source_reference": instance_reference,
            }
        elif company["mode"] != "STRUCTURAL_ONLY":
            raise ZeroAiReleaseError("R1 structured Run mode is invalid")
        company_rows.append(
            {
                "company_id": company_id,
                "result_metric_ids": list(R1_METRIC_IDS),
                "sources": sources,
                "target_period": dict(company["target_period"]),
            }
        )
    multi_source = build_multi_source_release_input_plan(
        release_plan_id=str(issue_plan["release_plan"]["release_plan_id"]),
        release_plan_content_id=str(issue_plan["release_plan_content_id"]),
        requirement_id="issue_15_v1",
        authority_hashes=issue_plan["authority_hashes"],
        companies=company_rows,
        source_references=references,
        source_set_manifests=manifests,
        event_route_catalog_sha256=sha256_file(
            path=repo_root / "catalog" / "event_routes.json"
        ),
    )
    return (
        multi_source,
        list(run_plan["companies"]),
        locator_proofs,
        projection_claims,
    )


def _freeze_r1_runs(
    *, repo_root: Path, workspace_dir: Path, plan: Mapping[str, object],
    run_companies: Sequence[Mapping[str, object]],
) -> Tuple[
    List[Dict[str, object]], Dict[str, bytes], List[Dict[str, object]],
]:
    """Freeze and verify the ten structured R1 Runs.

    Args:
        repo_root: Repository authority root.
        workspace_dir: Persistent repository-owned R1 workspace.
        plan: Exact multi-source input plan.
        run_companies: Repository-derived structured Run inputs.

    Returns:
        Coordinate bindings, immutable Run files, and exact projection records.
    """
    run_root = workspace_dir / "runs"
    run_root.mkdir(parents=True, exist_ok=True)
    coordinates = []
    internal_files = {}
    projection_records = []
    for company in run_companies:
        company_id = str(company["company_id"])
        run_dir = run_root / company_id
        _freeze_structured_run(
            repo_root=repo_root,
            run_dir=run_dir,
            company=company,
            plan_id=str(plan["release_input_plan_id"]),
            execute_live=True,
        )
        manifest, records, decisions = load_run_for_status(
            run_dir=run_dir, repo_root=repo_root,
        )
        if manifest["status"] != "FROZEN" or decisions:
            raise ZeroAiReleaseError("R1 Run is not deterministic and frozen")
        projection_records.extend(dict(record) for record in records)
        results = {
            str(record["metric_id"]): record
            for record in records
            if record["record_type"] == "METRIC_RESULT"
            and record["metric_id"] in R1_METRIC_IDS
        }
        traces = {
            str(record["trace_id"]): record
            for record in records
            if record["record_type"] == "EXECUTION_TRACE"
        }
        if set(results) != set(R1_METRIC_IDS):
            raise ZeroAiReleaseError("R1 Run result exact set differs")
        for metric_id in R1_METRIC_IDS:
            result = results[metric_id]
            trace_id = str(result["trace_id"])
            if trace_id not in traces:
                raise ZeroAiReleaseError("R1 Result lacks ExecutionTrace")
            coordinates.append(
                {
                    "company_id": company_id,
                    "metric_id": metric_id,
                    "result_id": result["result_id"],
                    "trace_id": trace_id,
                    "applicability": result["applicability"],
                    "publication": result["publication"],
                    "quality": result["quality"],
                    "value": result["value"],
                    "unit": result["unit"],
                    "run_id": manifest["run_id"],
                }
            )
        for path in sorted(run_dir.rglob("*")):
            if path.is_symlink() or (path.exists() and not path.is_file()):
                if path.is_dir():
                    continue
                raise ZeroAiReleaseError("R1 Run namespace is unsafe")
            relative = path.relative_to(run_dir).as_posix()
            internal_files[
                "internal/runs/{}/{}".format(company_id, relative)
            ] = path.read_bytes()
    coordinates.sort(key=lambda row: (row["company_id"], row["metric_id"]))
    if len(coordinates) != R1_EXPECTED_COORDINATES:
        raise ZeroAiReleaseError("R1 coordinate count differs")
    return coordinates, internal_files, projection_records


def _coordinate_periods(
    *, coordinates: Sequence[Mapping[str, object]],
    run_companies: Sequence[Mapping[str, object]],
) -> List[Dict[str, object]]:
    """Attach explicit target periods to coordinate receipt rows.

    Args:
        coordinates: Result bindings from frozen Runs.
        run_companies: Exact plan companies carrying target periods.

    Returns:
        Coordinate rows with period fields needed by public projection.
    """
    periods = {
        str(company["company_id"]): company["target_period"]
        for company in run_companies
    }
    output = []
    for coordinate in coordinates:
        row = dict(coordinate)
        target = periods[str(row["company_id"])]
        row["fiscal_year"] = target["fiscal_year"]
        row["period_start"] = target["period_start"]
        row["period_end"] = target["period_end"]
        output.append(row)
    return output


def _public_key_proof(*, metrics_bytes: bytes) -> Tuple[int, str]:
    """Return public row count and exact company/metric key-set hash.

    Args:
        metrics_bytes: Candidate public matrix.

    Returns:
        Row count and canonical key-set identity.
    """
    rows = _csv_rows(content=metrics_bytes, fields=METRICS_FIELDS)
    keys = sorted(
        (
            {"company": row["company"], "metric_id": row["metric_id"]}
            for row in rows
        ),
        key=lambda row: (row["company"], row["metric_id"]),
    )
    if len(keys) != len({(row["company"], row["metric_id"]) for row in keys}):
        raise ZeroAiReleaseError("Public matrix contains duplicate keys")
    return len(rows), content_hash(value=keys)


def _receipt(*, body: Mapping[str, object], identity_field: str) -> Dict[str, object]:
    """Attach one canonical content identity to a receipt body.

    Args:
        body: Exact receipt fields excluding identity.
        identity_field: Content-addressed identity field name.

    Returns:
        Receipt with its identity.
    """
    return {**dict(body), identity_field: content_hash(value=dict(body))}


def _retirement_receipt(
    *, repo_root: Path, cumulative_metric_ids: Sequence[str],
    publication_stage: str, projection_closure_id: str,
) -> Dict[str, object]:
    """Bind migrated metric scopes to the WB-1 frozen producer inventory.

    Args:
        repo_root: Repository containing the immutable Issue #15 inventory.
        cumulative_metric_ids: Exact metric scopes retired by this release.
        publication_stage: Ratchet stage that makes retirement effective.
        projection_closure_id: Independent migrated-row renderer proof.

    Returns:
        Content-addressed publication-bound retirement receipt.
    """
    path = (
        repo_root
        / "requirements"
        / "issue_15_v1"
        / "legacy_semantic_producer_inventory.json"
    )
    try:
        inventory = json.loads(path.read_text(encoding="utf-8"))
        producers = inventory["producers"]
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ZeroAiReleaseError("WB-1 producer inventory is invalid") from error
    metric_ids = set(cumulative_metric_ids)
    retired_scopes = []
    for producer in producers:
        if not isinstance(producer, dict) or not {
            "producer_id", "kind", "covered_metric_ids",
        }.issubset(producer):
            raise ZeroAiReleaseError("WB-1 producer record is invalid")
        if producer["kind"] != "SEMANTIC_PRODUCER":
            continue
        scoped = sorted(metric_ids.intersection(producer["covered_metric_ids"]))
        if scoped:
            retired_scopes.append(
                {
                    "producer_id": producer["producer_id"],
                    "retired_metric_ids": scoped,
                }
            )
    retired_scopes.sort(key=lambda row: str(row["producer_id"]))
    if not retired_scopes:
        raise ZeroAiReleaseError("Zero-AI producer retirement set is empty")
    body = {
        "schema_version": 1,
        "record_type": "PUBLICATION_BOUND_RETIREMENT_RECEIPT",
        "status": "PASSED",
        "publication_stage": publication_stage,
        "cumulative_metric_ids": sorted(metric_ids),
        "frozen_inventory_sha256": sha256_file(path=path),
        "projection_closure_id": projection_closure_id,
        "projection_independence": build_projection_independence_receipt(
            repo_root=repo_root,
        ),
        "retired_producer_scopes": retired_scopes,
    }
    return _receipt(body=body, identity_field="retirement_receipt_id")


def _internal_bindings(
    *, files: Mapping[str, bytes]
) -> Dict[str, Dict[str, object]]:
    """Bind every non-marker internal file by bytes and size.

    Args:
        files: Internal bundle files excluding the zero-AI marker.

    Returns:
        Sorted path binding mapping.
    """
    return {
        path: {"sha256": sha256_bytes(content=files[path]), "size": len(files[path])}
        for path in sorted(files)
    }


def _ledger_binding(
    *, repo_root: Path, plan: Mapping[str, object],
    locator_proofs: Mapping[str, object],
) -> Tuple[Dict[str, object], bytes]:
    """Build the formal immutable request-prefix binding.

    Args:
        repo_root: Repository containing the complete request ledger.
        plan: Multi-source release input plan.
        locator_proofs: Immutable locator proof by SourceReference identity.

    Returns:
        Publication ledger binding and portable provenance bytes.
    """
    source_ids = sorted(
        str(reference["source_reference_id"])
        for reference in plan["source_references"]
    )
    if source_ids != sorted(locator_proofs):
        raise ZeroAiReleaseError("Zero-AI locator proof exact set differs")
    attempts = sorted(
        {
            str(locator_proofs[source_id]["request_attempt_id"])
            for source_id in source_ids
        }
    )
    source_proofs = []
    locator_classes = sorted(
        {
            str(locator_proofs[source_id]["request_locator_kind"])
            for source_id in source_ids
        }
    )
    for source_id in source_ids:
        proof = locator_proofs[source_id]
        source_proof = {
            "source_reference_id": source_id,
            "request_attempt_id": proof["request_attempt_id"],
            "locator_class": proof["request_locator_kind"],
            "body_path": proof["request_repo_relative_path"],
            "body_sha256": proof["request_body_sha256"],
            "body_size": proof["request_body_size"],
            "headers_path": proof["request_headers_repo_relative_path"],
            "headers_sha256": proof["request_headers_sha256"],
            "headers_size": proof["request_headers_size"],
        }
        if proof["request_locator_kind"] == "IMMUTABLE_GIT_BLOB":
            required_git = {
                "git_body_blob_oid",
                "git_commit",
                "git_headers_blob_oid",
            }
            if not required_git.issubset(proof):
                raise ZeroAiReleaseError("Git-blob locator proof is incomplete")
            source_proof.update(
                {field: proof[field] for field in sorted(required_git)}
            )
        source_proofs.append(source_proof)
    log_manifest = request_log_manifest_payload(
        log_path=repo_root / "evidence" / "requests_log.csv"
    )
    proof_body = {
        "schema_version": 1,
        "record_type": "ZERO_AI_REQUEST_LOCATOR_PROVENANCE",
        "release_input_plan_id": plan["release_input_plan_id"],
        "request_locator_classes": locator_classes,
        "source_proofs": source_proofs,
    }
    provenance = _receipt(
        body=proof_body, identity_field="request_locator_proof_id",
    )
    binding = {
        "request_locator_classes": locator_classes,
        "request_locator_proof_id": provenance["request_locator_proof_id"],
        "request_locator_tier": "FULL_VALIDATION",
        "requests_log_prefix_sha256": log_manifest["content_sha256"],
        "row_count": log_manifest["row_count"],
        "source_reference_ids": source_ids,
        "used_request_attempt_ids": attempts,
    }
    return binding, _json_bytes(value=provenance)


def _prepare_r1_successor(
    *, repo_root: Path, predecessor: Mapping[str, object],
    source_commit: str, committed_at_utc: str,
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """Prepare the formal R1 successor and its evidence summary.

    Args:
        repo_root: Formal publication and authority root.
        predecessor: Verified imported legacy PublicationManifest A.
        source_commit: Clean committed implementation SHA.
        committed_at_utc: Explicit R1 validation time.

    Returns:
        Prepared PublicationManifest B and complete receipt summary.
    """
    source_binding = _source_commit_binding(
        repo_root=repo_root, source_commit=source_commit,
    )
    layout = publication_layout(publication_root=repo_root)
    predecessor_dir = (
        Path(layout["publications_dir"]) / str(predecessor["publication_id"])
    )
    verified_predecessor = verify_publication_bundle(bundle_dir=predecessor_dir)
    if verified_predecessor != dict(predecessor):
        raise ZeroAiReleaseError("R1 predecessor changed after import")
    public_files = {
        relative: (predecessor_dir / relative).read_bytes()
        for relative in sorted(REQUIRED_BUNDLE_FILES)
    }
    plan, run_companies, locator_proofs, projection_claims = _r1_source_plan(
        repo_root=repo_root, legacy_snapshot_dir=repo_root / "outputs",
    )
    workspace = repo_root / "artifacts" / "vnext" / "zero_ai_release" / "r1"
    coordinates, run_files, projection_records = _freeze_r1_runs(
        repo_root=repo_root,
        workspace_dir=workspace,
        plan=plan,
        run_companies=run_companies,
    )
    coordinates = _coordinate_periods(
        coordinates=coordinates, run_companies=run_companies,
    )
    registry_rows = _registry_rows(repo_root=repo_root)
    legacy_rows = _csv_rows(
        content=public_files["metrics_matrix.csv"], fields=METRICS_FIELDS,
    )
    rendered = render_public_rows(
        repo_root=repo_root,
        metric_ids=R1_METRIC_IDS,
        registry_rows=registry_rows,
        coordinates=coordinates,
        records=projection_records,
        source_references=plan["source_references"],
        filing_inventory=[],
        projection_claims=projection_claims,
    )
    compatibility = compare_public_rows(
        rendered_rows=[
            row for row in rendered["rows"]
            if (row["company"], row["metric_id"]) in {
                (legacy["company"], legacy["metric_id"])
                for legacy in legacy_rows
                if legacy["metric_id"] in set(R1_METRIC_IDS)
            }
        ],
        frozen_legacy_rows=[
            row for row in legacy_rows if row["metric_id"] in set(R1_METRIC_IDS)
        ],
        approved_deltas=rendered["approved_deltas"],
        approved_delta_authority_hash=rendered[
            "approved_delta_authority_hash"
        ],
    )
    assembled_metrics = assemble_public_rows(
        predecessor_rows=legacy_rows,
        rendered_rows=rendered["rows"],
        metric_ids=R1_METRIC_IDS,
    )
    public_files["metrics_matrix.csv"] = csv_bytes(
        rows=assembled_metrics,
        fields=METRICS_FIELDS,
    )
    predecessor_coverage = _csv_rows(
        content=public_files["coverage_matrix.csv"], fields=COVERAGE_FIELDS,
    )
    assembled_coverage = assemble_public_rows(
        predecessor_rows=predecessor_coverage,
        rendered_rows=render_coverage_rows(rendered_rows=rendered["rows"]),
        metric_ids=R1_METRIC_IDS,
    )
    public_files["coverage_matrix.csv"] = csv_bytes(
        rows=assembled_coverage,
        fields=COVERAGE_FIELDS,
    )
    row_count, key_hash = _public_key_proof(
        metrics_bytes=public_files["metrics_matrix.csv"]
    )
    if row_count != R1_EXPECTED_PUBLIC_ROWS:
        raise ZeroAiReleaseError("R1 public matrix row count differs")
    for markdown_path in ("README_RUN.md", "REPORT_十公司财务指标.md"):
        public_files[markdown_path] = _append_publication_note(
            original=public_files[markdown_path],
            release_stage="R1",
            cumulative_metric_ids=R1_METRIC_IDS,
            public_matrix_row_count=row_count,
        )
    strict_hash = compatibility["strict_compatibility_hash"]
    projection_closure = _receipt(
        body={
            "schema_version": 1,
            "record_type": "ZERO_AI_PUBLIC_PROJECTION_CLOSURE",
            "release_stage": "R1",
            "renderer_semantic_version": rendered[
                "renderer_semantic_version"
            ],
            "projection_catalog_sha256": rendered[
                "projection_catalog_sha256"
            ],
            "rendered_row_set_hash": rendered["rendered_row_set_hash"],
            "row_bindings": rendered["row_bindings"],
            "compatibility": compatibility,
        },
        identity_field="projection_closure_id",
    )
    coordinate_body = {
        "schema_version": 1,
        "record_type": "ZERO_AI_COORDINATE_INDEX",
        "release_stage": "R1",
        "release_input_plan_id": plan["release_input_plan_id"],
        "coordinates": coordinates,
    }
    coordinate_index = _receipt(
        body=coordinate_body, identity_field="batch_manifest_id",
    )
    invocation = structured_only_result(
        repo_root=repo_root,
        workspace_dir=workspace,
        release_input_plan_id=str(plan["release_input_plan_id"]),
        cumulative_metric_ids=R1_METRIC_IDS,
        result_coordinate_count=R1_EXPECTED_COORDINATES,
    )
    retirement = _retirement_receipt(
        repo_root=repo_root,
        cumulative_metric_ids=R1_METRIC_IDS,
        publication_stage="R1",
        projection_closure_id=str(
            projection_closure["projection_closure_id"]
        ),
    )
    issue_release = load_issue15_release_plan(
        repo_root=repo_root, release_plan_id="issue_15_zero_ai_r1",
    )
    ratchet_transition = issue_release["ratchet_transitions"][0]
    ledger_binding, locator_bytes = _ledger_binding(
        repo_root=repo_root, plan=plan, locator_proofs=locator_proofs,
    )
    internal_files = {
        **run_files,
        "internal/release_input_plan.json": _json_bytes(value=plan),
        "internal/coordinate_index.json": _json_bytes(value=coordinate_index),
        "internal/request_locator_provenance.json": locator_bytes,
        "internal/issue15_release_plan.json": (
            repo_root / "config" / "release_plans"
            / "issue_15_zero_ai_r1.json"
        ).read_bytes(),
        "internal/retirement_receipt.json": _json_bytes(value=retirement),
        "internal/public_projection_closure.json": _json_bytes(
            value=projection_closure
        ),
        "internal/structured_only_invocation.json": _json_bytes(value=invocation),
    }
    issue_requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements" / "issue_15_v1"
    )
    projection_body = {
        "schema_version": 1,
        "record_type": "ZERO_AI_PROJECTION_MANIFEST",
        "status": "PUBLISHABLE",
        "release_stage": "R1",
        "release_input_plan_id": plan["release_input_plan_id"],
        "batch_manifest_id": coordinate_index["batch_manifest_id"],
        "previous_publication_id": predecessor["publication_id"],
        "cumulative_metric_ids": list(R1_METRIC_IDS),
        "result_coordinate_count": R1_EXPECTED_COORDINATES,
        "replaced_legacy_row_count": R1_EXPECTED_LEGACY_ROWS,
        "new_public_key_count": R1_EXPECTED_NEW_KEYS,
        "public_matrix_row_count": row_count,
        "public_key_set_hash": key_hash,
        "strict_compatibility_hash": strict_hash,
        "projection_closure_id": projection_closure[
            "projection_closure_id"
        ],
        "requirement_closure_hash": issue_requirement[
            "requirement_closure_hash"
        ],
    }
    projection = _receipt(
        body=projection_body, identity_field="projection_manifest_id",
    )
    migration = _receipt(
        body={
            "schema_version": 1,
            "record_type": "ZERO_AI_STRICT_COMPATIBILITY_RECEIPT",
            "status": "PASSED",
            "release_stage": "R1",
            "projection_manifest_id": projection["projection_manifest_id"],
            "replaced_legacy_row_count": R1_EXPECTED_LEGACY_ROWS,
            "new_public_key_count": R1_EXPECTED_NEW_KEYS,
            "parent_release_plan_content_id": ratchet_transition[
                "parent_release_plan_content_id"
            ],
            "removed_metric_ids": ratchet_transition[
                "removed_metric_ids"
            ],
            "removed_public_keys": [],
            "removed_vnext_result_keys": ratchet_transition[
                "removed_vnext_result_keys"
            ],
            "unretired_legacy_producer_ids": ratchet_transition[
                "unretired_legacy_producer_ids"
            ],
            "projection_closure_id": projection_closure[
                "projection_closure_id"
            ],
            "compared_key_count": compatibility["compared_key_count"],
            "compared_field_count": compatibility[
                "compared_field_count"
            ],
            "per_field_counts": compatibility["per_field_counts"],
            "unexpected_delta_exact_set": compatibility[
                "unexpected_delta_exact_set"
            ],
            "approved_delta_exact_set": compatibility[
                "approved_delta_exact_set"
            ],
            "approved_delta_authority_hash": compatibility[
                "approved_delta_authority_hash"
            ],
            "canonical_comparison_matrix_hash": compatibility[
                "canonical_comparison_matrix_hash"
            ],
            "vnext_rendered_row_set_hash": compatibility[
                "vnext_rendered_row_set_hash"
            ],
            "frozen_legacy_row_set_hash": compatibility[
                "frozen_legacy_row_set_hash"
            ],
            "strict_compatibility_hash": strict_hash,
            "public_key_set_hash": key_hash,
            "retirement_receipt_id": retirement["retirement_receipt_id"],
        },
        identity_field="strict_compatibility_receipt_id",
    )
    validation_body = {
        "schema_version": 1,
        "record_type": "ZERO_AI_PUBLICATION_VALIDATION_RECEIPT",
        "status": "PASSED",
        "release_stage": "R1",
        "projection_manifest_id": projection["projection_manifest_id"],
        "batch_manifest_id": coordinate_index["batch_manifest_id"],
        "checks": [
            "IMMUTABLE_SOURCE_ATTEMPTS",
            "RESULT_TRACE_EXACT_SET",
            "STRICT_COMPATIBILITY",
            "FIELD_LEVEL_PUBLIC_PROJECTION",
            "PUBLIC_KEY_UNION",
            "STRUCTURED_ONLY_ZERO_PROVIDER",
        ],
        "counters": dict(invocation["counters"]),
        "validated_at_utc": committed_at_utc,
    }
    validation = _receipt(
        body=validation_body, identity_field="validation_receipt_id",
    )
    public_files["projection_manifest.json"] = _json_bytes(value=projection)
    public_files["legacy_invariant_migration_receipt.json"] = _json_bytes(
        value=migration
    )
    public_files["publication_validation_receipt.json"] = _json_bytes(
        value=validation
    )
    public_files["validation_run_manifest.json"] = _json_bytes(
        value={
            "run_id": str(coordinate_index["batch_manifest_id"]),
            "source_commit": source_commit,
            "started_at_utc": committed_at_utc,
            "mode": "LIGHT_REVIEW_MODE",
            "refreshed_artifacts": sorted(
                [
                    "coverage_matrix.csv",
                    "legacy_invariant_migration_receipt.json",
                    "metrics_matrix.csv",
                    "projection_manifest.json",
                    "publication_validation_receipt.json",
                    "validation_run_manifest.json",
                ]
            ),
            "not_refreshed_artifacts": [
                "issue_15_full_acceptance.not_run"
            ],
            "result": "PASSED_WITH_CAVEATS",
        }
    )
    public_hashes = {
        relative: sha256_bytes(content=public_files[relative])
        for relative in sorted(REQUIRED_BUNDLE_FILES)
    }
    marker_body = {
        "schema_version": 2,
        "record_type": "ZERO_AI_FORMAL_RELEASE_RECEIPT",
        "status": "PASSED",
        "release_stage": "R1",
        "source_commit": source_binding["source_commit"],
        "source_tree_oid": source_binding["source_tree_oid"],
        "release_input_plan_id": plan["release_input_plan_id"],
        "batch_manifest_id": coordinate_index["batch_manifest_id"],
        "projection_manifest_id": projection["projection_manifest_id"],
        "validation_receipt_id": validation["validation_receipt_id"],
        "previous_publication_id": predecessor["publication_id"],
        "cumulative_metric_ids": list(R1_METRIC_IDS),
        "result_coordinate_count": R1_EXPECTED_COORDINATES,
        "replaced_legacy_row_count": R1_EXPECTED_LEGACY_ROWS,
        "new_public_key_count": R1_EXPECTED_NEW_KEYS,
        "public_matrix_row_count": row_count,
        "public_key_set_hash": key_hash,
        "strict_compatibility_hash": strict_hash,
        "projection_closure_id": projection_closure[
            "projection_closure_id"
        ],
        "requirement_closure_hash": issue_requirement[
            "requirement_closure_hash"
        ],
        "issue15_release_plan_id": issue_release["release_plan"][
            "release_plan_id"
        ],
        "issue15_release_plan_content_id": issue_release[
            "release_plan_content_id"
        ],
        "issue15_release_plan_sha256": issue_release[
            "release_plan_sha256"
        ],
        "source_locator_classes": ["IMMUTABLE_ATTEMPT"],
        "invocation_observation_id": invocation[
            "invocation_observation_id"
        ],
        "counters": dict(invocation["counters"]),
        "public_artifact_hashes": public_hashes,
        "internal_files": _internal_bindings(files=internal_files),
    }
    marker = _receipt(
        body=marker_body, identity_field="zero_ai_release_receipt_id",
    )
    files = {
        **public_files,
        **internal_files,
        ZERO_AI_FORMAL_MANIFEST: _json_bytes(value=marker),
    }
    parent_requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements" / "ai_first_v3_3_1"
    )
    successor = _write_prepared_publication_bundle(
        publications_dir=Path(layout["publications_dir"]),
        files=files,
        requirement_hashes=parent_requirement["hashes"],
        batch_manifest_id=str(coordinate_index["batch_manifest_id"]),
        projection_manifest_id=str(projection["projection_manifest_id"]),
        validation_receipt_id=str(validation["validation_receipt_id"]),
        ledger_binding=ledger_binding,
        previous_publication_id=str(predecessor["publication_id"]),
    )
    summary = {
        "release_stage": "R1",
        "source_commit": source_binding["source_commit"],
        "source_tree_oid": source_binding["source_tree_oid"],
        "release_input_plan_id": plan["release_input_plan_id"],
        "batch_manifest_id": coordinate_index["batch_manifest_id"],
        "projection_manifest_id": projection["projection_manifest_id"],
        "validation_receipt_id": validation["validation_receipt_id"],
        "zero_ai_release_receipt_id": marker["zero_ai_release_receipt_id"],
        "public_matrix_row_count": row_count,
        "public_key_set_hash": key_hash,
        "strict_compatibility_hash": strict_hash,
        "retirement_receipt_id": retirement["retirement_receipt_id"],
        "invocation_observation_id": invocation[
            "invocation_observation_id"
        ],
        "counters": dict(invocation["counters"]),
        "retirement_receipt": retirement,
    }
    return successor, summary


def _read_back_proof(
    *, repo_root: Path, expected_publication_id: str,
) -> Dict[str, object]:
    """Read every active file through PublicationView and compare mirrors.

    Args:
        repo_root: Formal publication root.
        expected_publication_id: Successor expected to be active.

    Returns:
        Content-addressed immutable read-back proof.
    """
    view = PublicationView.open(publication_root=repo_root)
    if view.publication_id != expected_publication_id:
        raise ZeroAiReleaseError("Zero-AI active publication differs")
    marker = json.loads(
        view.read_bytes(relative_path=ZERO_AI_FORMAL_MANIFEST).decode("utf-8")
    )
    artifact_hashes = {}
    for relative in sorted(REQUIRED_BUNDLE_FILES):
        content = view.read_bytes(relative_path=relative)
        mirror = repo_root / ROOT_MIRROR_RELATIVE_PATHS[relative]
        if mirror.read_bytes() != content:
            raise ZeroAiReleaseError("Zero-AI root mirror differs")
        artifact_hashes[relative] = sha256_bytes(content=content)
    state = publication_state_snapshot(publication_root=repo_root)
    if state["active_publication_id"] != expected_publication_id:
        raise ZeroAiReleaseError("Zero-AI state snapshot differs")
    body = {
        "schema_version": 1,
        "record_type": "ZERO_AI_IMMUTABLE_READ_BACK_PROOF",
        "status": "PASSED",
        "publication_id": expected_publication_id,
        "artifact_hashes": artifact_hashes,
        "mirror_hashes": state["mirror_hashes"],
        "counters": dict(marker["counters"]),
    }
    return _receipt(body=body, identity_field="read_back_proof_id")


def _persist_receipt_set(
    *, repo_root: Path, receipts: Mapping[str, Mapping[str, object]],
    counters: Mapping[str, object],
) -> Dict[str, object]:
    """Persist content-addressed R1 receipts and one stable role index.

    Args:
        repo_root: Repository output root.
        receipts: Receipt role to exact object mapping.

    Returns:
        Stable index binding every receipt path and byte digest.
    """
    receipt_dir = repo_root / "outputs" / "zero_ai_release_receipts" / "r1"
    if receipt_dir.is_symlink() or (
        receipt_dir.exists() and not receipt_dir.is_dir()
    ):
        raise ZeroAiReleaseError("R1 receipt directory is unsafe")
    receipt_dir.mkdir(parents=True, exist_ok=True)
    bindings = {}
    for role in sorted(receipts):
        content = _json_bytes(value=receipts[role])
        digest = sha256_bytes(content=content)
        path = receipt_dir / "{}.json".format(digest)
        if path.exists() and path.read_bytes() != content:
            raise ZeroAiReleaseError("R1 content-addressed receipt differs")
        if not path.exists():
            atomic_write_bytes(path=path, content=content)
        bindings[role] = {
            "path": path.relative_to(repo_root).as_posix(),
            "sha256": digest,
            "size": len(content),
        }
    index_body = {
        "schema_version": 1,
        "record_type": "ZERO_AI_R1_RECEIPT_INDEX",
        "status": "PASSED",
        "receipts": bindings,
        "counters": dict(counters),
    }
    index = _receipt(body=index_body, identity_field="receipt_index_id")
    atomic_write_bytes(
        path=receipt_dir / "index.json", content=_json_bytes(value=index),
    )
    return index


def publish_r1(
    *, repo_root: Path, source_commit: str, committed_at_utc: str,
) -> Dict[str, object]:
    """Execute the formal R1 cold-start publication and rollback drill.

    Args:
        repo_root: Repository-owned formal publication root.
        source_commit: Clean committed implementation SHA bound by validation.
        committed_at_utc: Explicit first switch and validation UTC time.

    Returns:
        Final active identity, public key proof, counters, and receipt index.
    """
    if not isinstance(source_commit, str) or len(source_commit) != 40:
        raise ZeroAiReleaseError("R1 source commit must be a full SHA")
    commit_time, rollback_time, restore_time = _utc_sequence(
        committed_at_utc=committed_at_utc
    )
    layout = publication_layout(publication_root=repo_root)
    if Path(layout["pointer_path"]).exists():
        raise ZeroAiReleaseError("R1 cold-start requires no active pointer")
    predecessor = prepare_issue15_legacy_baseline_predecessor(
        publication_root=repo_root,
        repo_root=repo_root,
        legacy_root=repo_root,
    )
    successor, summary = _prepare_r1_successor(
        repo_root=repo_root,
        predecessor=predecessor,
        source_commit=source_commit,
        committed_at_utc=commit_time,
    )
    retirement = summary.pop("retirement_receipt")
    initial = _commit_initial_publication_chain(
        publication_root=repo_root,
        legacy_predecessor_publication_id=str(predecessor["publication_id"]),
        successor_publication_id=str(successor["publication_id"]),
        committed_at_utc=commit_time,
    )
    active_proof = _read_back_proof(
        repo_root=repo_root,
        expected_publication_id=str(successor["publication_id"]),
    )
    rollback_pointer = rollback_publication(
        publication_root=repo_root,
        target_publication_id=str(predecessor["publication_id"]),
        expected_active_publication_id=str(successor["publication_id"]),
        committed_at_utc=rollback_time,
    )
    rollback_view = PublicationView.open(publication_root=repo_root)
    if rollback_view.publication_id != predecessor["publication_id"]:
        raise ZeroAiReleaseError("R1 rollback did not reactivate A")
    restore_pointer = _commit_publication(
        publication_root=repo_root,
        publication_id=str(successor["publication_id"]),
        expected_active_publication_id=str(predecessor["publication_id"]),
        committed_at_utc=restore_time,
    )
    restore_proof = _read_back_proof(
        repo_root=repo_root,
        expected_publication_id=str(successor["publication_id"]),
    )
    receipt_index = _persist_receipt_set(
        repo_root=repo_root,
        counters=summary["counters"],
        receipts={
            "predecessor": predecessor,
            "successor_publication": successor,
            "active_terminal": initial["active_pointer"],
            "rollback_terminal": rollback_pointer,
            "restore_terminal": restore_pointer,
            "initial_read_back": active_proof,
            "restore_read_back": restore_proof,
            "retirement": retirement,
        },
    )
    return {
        **summary,
        "predecessor_publication_id": predecessor["publication_id"],
        "active_publication_id": successor["publication_id"],
        "receipt_index_id": receipt_index["receipt_index_id"],
        "receipt_index_path": "outputs/zero_ai_release_receipts/r1/index.json",
        "committed_at_utc": commit_time,
        "rolled_back_at_utc": rollback_time,
        "restored_at_utc": restore_time,
    }
