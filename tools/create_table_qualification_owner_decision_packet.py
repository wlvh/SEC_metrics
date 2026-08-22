"""Create the offline owner-decision packet for a frozen Stage-A table cycle.

The packet records unresolved D-07 and financial expanded-grid questions as
facts and options.  It never edits the Decision Register, changes a resource
limit, creates a qualification Run, or opens an SEC/provider transport.
"""

from __future__ import annotations

import argparse
import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from vnext.canonical import atomic_write_json, content_hash, sha256_file  # noqa: E402
from vnext.canonical import strict_json_file  # noqa: E402
from vnext.requirements import load_requirement_snapshot  # noqa: E402
from vnext.provider_runtime import load_provider_runtime_authority  # noqa: E402
from vnext.stage_a_snapshot import StageASnapshotError  # noqa: E402
from vnext.stage_a_snapshot import validate_stage_a_snapshot  # noqa: E402
from vnext.table_qualification_freeze import (  # noqa: E402
    TableQualificationFreezeError,
)
from vnext.table_qualification_freeze import (  # noqa: E402
    validate_table_qualification_freeze,
)


PACKET_ROOT = Path("artifacts/vnext/table_qualification_freeze/decision_packets")
PACKET_POINTER = Path(
    "artifacts/vnext/table_qualification_freeze/current_owner_decision_packet.json"
)


class _SourceTableCounter(HTMLParser):
    """Count source tables/cells for an owner packet without building a grid."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.table_count = 0
        self.source_cell_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.table_count += 1
        elif tag in {"td", "th"}:
            self.source_cell_count += 1


def _packet_history(*, repo_root: Path) -> list[str]:
    """Return only validated historical packet identities from local bytes."""
    root = repo_root / PACKET_ROOT
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Owner decision packet namespace is unsafe")
    values = []
    for path in sorted(root.glob("*.json")):
        if path.is_symlink() or not path.is_file():
            raise ValueError("Owner decision packet history entry is unsafe")
        value = strict_json_file(path=path)
        if (
            type(value) is not dict
            or value.get("record_type")
            != "TABLE_QUALIFICATION_OWNER_DECISION_PACKET"
            or type(value.get("owner_decision_packet_id")) is not str
        ):
            raise ValueError("Owner decision packet history entry is invalid")
        body = {
            field: value[field]
            for field in value
            if field != "owner_decision_packet_id"
        }
        if value["owner_decision_packet_id"] != content_hash(value=body):
            raise ValueError("Owner decision packet history identity differs")
        values.append(str(value["owner_decision_packet_id"]))
    return values


def _receipt(*, repo_root: Path) -> Dict[str, object]:
    """Load the current receipt only after full local freeze revalidation."""
    status = validate_table_qualification_freeze(repo_root=repo_root)
    pointer = strict_json_file(
        path=repo_root / "config/table_qualification_freeze.json",
    )
    if type(pointer) is not dict or type(pointer.get("receipt_path")) is not str:
        raise ValueError("Table qualification freeze pointer is invalid")
    path = repo_root / str(pointer["receipt_path"])
    if path.is_symlink() or not path.is_file():
        raise ValueError("Table qualification freeze receipt is unsafe")
    receipt = strict_json_file(path=path)
    if (
        type(receipt) is not dict
        or receipt.get("table_qualification_freeze_receipt_id")
        != status["receipt_id"]
        or receipt.get("qualification_cycle_id")
        != status["qualification_cycle_id"]
    ):
        raise ValueError("Table qualification freeze receipt differs")
    return dict(receipt)


def build_owner_decision_packet(
    *, repo_root: Path, generated_at_utc: str,
) -> Dict[str, object]:
    """Mechanically assemble the current unresolved-owner-decision packet."""
    receipt = _receipt(repo_root=repo_root)
    stage_a = validate_stage_a_snapshot(repo_root=repo_root)
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/issue_15_v1",
    )
    d07 = requirement["effective_decisions"]["D-07"]
    d07_hash = content_hash(value=d07)
    wb4 = receipt["wb4_compact_transport"]
    measurements = list(wb4["qualification_task_measurements"])
    financial = [
        row for row in measurements
        if row["family_id"] == "financial_statement"
    ]
    lodging = [
        row for row in measurements
        if row["family_id"] == "lodging_kpi_table"
    ]
    if not financial or not lodging or receipt["d07_decision_required"] is not True:
        raise ValueError("Owner decision packet requires current blocked measurements")
    history = _packet_history(repo_root=repo_root)
    financial_source = financial[0]
    source_path = repo_root / str(
        financial_source["development_source_repo_relative_path"]
    )
    if source_path.is_symlink() or not source_path.is_file():
        raise ValueError("Financial development source is unsafe")
    source_bytes = source_path.read_bytes()
    counter = _SourceTableCounter()
    counter.feed(source_bytes.decode("utf-8"))
    runtime = load_provider_runtime_authority(
        repo_root=repo_root,
        provider=str(receipt["provider_state"]["provider"]),
        model=str(receipt["provider_state"]["model"]),
        api=str(receipt["provider_state"]["api"]),
    )
    body = {
        "schema_version": 2,
        "record_type": "TABLE_QUALIFICATION_OWNER_DECISION_PACKET",
        "generated_at_utc": generated_at_utc,
        "decision_register_modified": False,
        "implementation_choice_made": False,
        "supersedes_owner_decision_packet_ids": sorted(history),
        "freeze_binding": {
            "freeze_receipt_id": receipt[
                "table_qualification_freeze_receipt_id"
            ],
            "freeze_receipt_sha256": sha256_file(
                path=repo_root / str(
                    strict_json_file(
                        path=repo_root / "config/table_qualification_freeze.json",
                    )["receipt_path"]
                ),
            ),
            "qualification_cycle_id": receipt["qualification_cycle_id"],
            "semantic_freeze_commit": receipt["freeze_commit"],
            "matrix_sha256": wb4["d07_authority"]["matrix_sha256"],
            "catalog_sha256": receipt["wb6_task_contracts"]["catalog_sha256"],
            "stage_a_snapshot_id": stage_a["stage_a_snapshot_id"],
        },
        "financial_expanded_grid_resource": {
            "development_source": {
                "source_repo_relative_path": financial_source[
                    "development_source_repo_relative_path"
                ],
                "source_sha256": financial_source["source_sha256"],
                "source_id": financial_source["source_id"],
            },
            "source_bytes": len(source_bytes),
            "table_count": counter.table_count,
            "source_cell_count": counter.source_cell_count,
            "expanded_cell_count_or_failure": {
                "status": "NOT_AVAILABLE_RESOURCE_LIMIT",
                "failure_reason": financial_source["resource_limit_reason"],
                "expanded_reader_payload_bytes": financial_source[
                    "expanded_reader_payload_bytes"
                ],
            },
            "measurements": financial,
            "current_status": "NOT_AVAILABLE_RESOURCE_LIMIT",
            "full_grid_constraint": (
                "All document tables and cells remain local Evidence Authority; "
                "no selector, prefilter, slice router, partial parser, or "
                "production resource-limit change was made."
            ),
            "owner_options": [
                {"option_id": "A", "requires_owner_decision": True,
                 "description": "Replace the development source with one whose complete expanded grid fits current policy."},
                {"option_id": "B", "requires_owner_decision": True,
                 "description": "Measure memory/time and raise or redesign the local full-grid resource envelope without omitting tables or cells."},
                {"option_id": "C", "requires_owner_decision": True,
                 "description": "Change live-ready family policy or a family-scoped gate with explicit qualification semantics."},
                {"option_id": "D", "requires_owner_decision": True,
                 "description": "Keep the current global stop."},
            ],
        },
        "token_estimator_and_d07_authority": {
            "effective_d07_record_hash": d07_hash,
            "effective_d07_choice": d07["choice"],
            "d07_decision_required": receipt["d07_decision_required"],
            "d07_authority": wb4["d07_authority"],
            "maximum_context_tokens": runtime["maximum_context_tokens"],
            "maximum_estimated_input_tokens": wb4[
                "maximum_estimated_input_tokens"
            ],
            "lodging_measurements": lodging,
            "financial_measurements": financial,
            "actual_prompt_tokens": "NOT_RUN",
            "contract_precondition": (
                "CONTRACT.md D-07 requires real prompt_tokens evidence before "
                "a new D-07 tip may introduce a selector; this packet creates no "
                "tip and selects no estimator policy."
            ),
            "family_scoped_readiness_question": (
                "Whether any(...) D-07 blocking remains global or becomes "
                "family-scoped is an owner policy choice; no implementation "
                "choice was made."
            ),
            "owner_options": [
                {"option_id": "A", "requires_owner_decision": True,
                 "description": "Create a D-07 tip that names the oversized estimator authority."},
                {"option_id": "B", "requires_owner_decision": True,
                 "description": "Change the matrix threshold and bind it to an explicitly selected estimator."},
                {"option_id": "C", "requires_owner_decision": True,
                 "description": "Authorize one qualification-plan-controlled measurement ordinal to obtain actual_prompt_tokens."},
                {"option_id": "D", "requires_owner_decision": True,
                 "description": "Keep the current stop."},
            ],
        },
    }
    return {**body, "owner_decision_packet_id": content_hash(value=body)}


def write_owner_decision_packet(
    *, repo_root: Path, generated_at_utc: str,
) -> Dict[str, object]:
    """Write one content-addressed packet and its non-authoritative index."""
    packet = build_owner_decision_packet(
        repo_root=repo_root,
        generated_at_utc=generated_at_utc,
    )
    packet_path = repo_root / PACKET_ROOT / (
        packet["owner_decision_packet_id"].split(":", maxsplit=1)[1] + ".json"
    )
    if packet_path.exists():
        if packet_path.is_symlink() or not packet_path.is_file() or (
            strict_json_file(path=packet_path) != packet
        ):
            raise ValueError("Owner decision packet destination differs")
    else:
        atomic_write_json(path=packet_path, value=packet)
    pointer_body = {
        "schema_version": 1,
        "record_type": "TABLE_QUALIFICATION_OWNER_DECISION_PACKET_POINTER",
        "owner_decision_packet_id": packet["owner_decision_packet_id"],
        "packet_path": packet_path.relative_to(repo_root).as_posix(),
        "superseded_owner_decision_packet_ids": packet[
            "supersedes_owner_decision_packet_ids"
        ],
    }
    atomic_write_json(path=repo_root / PACKET_POINTER, value=pointer_body)
    return {
        **packet,
        "packet_path": packet_path.relative_to(repo_root).as_posix(),
        "pointer_path": PACKET_POINTER.as_posix(),
    }


def main(*, argv: Sequence[str]) -> int:
    """Parse local-only packet generation arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated-at-utc", required=True)
    arguments = parser.parse_args(list(argv))
    try:
        packet = write_owner_decision_packet(
            repo_root=REPO_ROOT,
            generated_at_utc=arguments.generated_at_utc,
        )
    except (StageASnapshotError, TableQualificationFreezeError, ValueError) as error:
        print(json.dumps({"status": "BLOCKED", "message": str(error)}, sort_keys=True))
        return 2
    print(json.dumps({
        "status": "OWNER_DECISION_PACKET_WRITTEN",
        "owner_decision_packet_id": packet["owner_decision_packet_id"],
        "packet_path": packet["packet_path"],
        "qualification_cycle_id": packet["freeze_binding"]["qualification_cycle_id"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
