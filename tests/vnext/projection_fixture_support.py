"""Shared repository authority fixture for Projector/Publication scenarios."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from scripts.git_workspace import sanitized_git_environment
from tests.vnext.common import REPO_ROOT
from vnext.canonical import canonical_json_bytes, content_hash, sha256_file
from vnext.requirements import load_requirement_snapshot


def _write_registry(*, path: Path, rows: list, fieldnames: tuple) -> None:
    """Write the scoped registry with deterministic UTF-8 CSV bytes.

    Args:
        path: Registry destination.
        rows: Selected company rows.
        fieldnames: Exact original schema.
    """
    with path.open(mode="w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(fieldnames), lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _bind_scoped_baseline(*, repo_root: Path, snapshot_dir: Path) -> None:
    """Bind copied Requirement baseline digests to fixture snapshot bytes.

    Args:
        repo_root: Copied fixture repository.
        snapshot_dir: Independent metrics/evidence/Golden snapshot.
    """
    path = (
        repo_root
        / "requirements"
        / "ai_first_v3_3_1"
        / "baseline_manifest.json"
    )
    baseline = json.loads(path.read_text(encoding="utf-8"))
    for filename in (
        "metrics_matrix.csv", "metric_evidence.csv", "golden_results.csv",
    ):
        artifact = baseline["artifact_digests"]["outputs/" + filename]
        source = snapshot_dir / filename
        with source.open(encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream)
            fieldnames = next(reader)
            row_count = sum(1 for _row in reader)
        artifact.update(
            {
                "sha256": sha256_file(path=source),
                "size": source.stat().st_size,
                "row_count": row_count,
            }
        )
        if "fieldnames" in artifact:
            artifact["fieldnames"] = fieldnames
    path.write_bytes(canonical_json_bytes(value=baseline) + b"\n")


def _rebind_release_plan_chain(*, repo_root: Path) -> None:
    """Rebuild immutable R1/R2 identities for one scoped test repository.

    Args:
        repo_root: Temporary repository with finalized child authority bytes.

    Expected output:
        Both full plans, their parent content edge, and active index are exact.
    """
    registry_path = repo_root / "config" / "company_registry.csv"
    with registry_path.open(encoding="utf-8", newline="") as stream:
        company_ids = sorted(row["company_id"] for row in csv.DictReader(stream))
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements" / "issue_15_v1"
    )
    producer_path = (
        repo_root / "requirements" / "issue_15_v1"
        / "legacy_semantic_producer_inventory.json"
    )
    plans = []
    for plan_id in ("issue_15_zero_ai_r1", "issue_15_zero_ai_r2"):
        path = repo_root / "config" / "release_plans" / (plan_id + ".json")
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["requirement_closure_hash"] = requirement[
            "requirement_closure_hash"
        ]
        plan["authority_hashes"]["company_registry_sha256"] = sha256_file(
            path=registry_path
        )
        plan["authority_hashes"]["producer_inventory_sha256"] = sha256_file(
            path=producer_path
        )
        plan["cumulative_vnext_result_keys"] = [
            {"company_id": company_id, "metric_id": metric_id}
            for company_id in company_ids
            for metric_id in plan["cumulative_metric_ids"]
        ]
        if plans:
            plan["parent_release_plan_content_id"] = plans[0][
                "release_plan_content_id"
            ]
        body = {
            field: plan[field]
            for field in plan
            if field != "release_plan_content_id"
        }
        plan["release_plan_content_id"] = content_hash(value=body)
        path.write_bytes(canonical_json_bytes(value=plan) + b"\n")
        plans.append(plan)
    index_path = repo_root / "config" / "issue_15_release_plan.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["active_release_plan_content_id"] = plans[-1][
        "release_plan_content_id"
    ]
    for entry, plan in zip(index["release_plan_paths"], plans):
        entry["release_plan_content_id"] = plan["release_plan_content_id"]
    body = {
        field: index[field]
        for field in index
        if field != "release_plan_index_id"
    }
    index["release_plan_index_id"] = content_hash(value=body)
    index_path.write_bytes(canonical_json_bytes(value=index) + b"\n")


def _bind_issue15_scoped_registry(*, repo_root: Path) -> None:
    """Rebind Issue #15 plan chain after one-company fixture scoping."""
    _rebind_release_plan_chain(repo_root=repo_root)


def _git(*, repo_root: Path, arguments: list[str]) -> str:
    """Run one local test-repository Git command with isolated metadata.

    Args:
        repo_root: Temporary repository owning the fixture authority.
        arguments: Git arguments excluding the executable name.

    Returns:
        UTF-8 standard output without trailing whitespace.

    Raises:
        AssertionError: If the test fixture cannot establish its baseline tree.
    """
    completed = subprocess.run(
        args=["git", *arguments],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        encoding="utf-8",
        env=sanitized_git_environment(),
    )
    if completed.returncode != 0:
        raise AssertionError(
            "Fixture Git command failed: {}".format(
                completed.stderr.strip() or completed.stdout.strip()
            )
        )
    return completed.stdout.strip()


def _bind_scoped_legacy_inventory_to_git(*, repo_root: Path) -> None:
    """Create a local frozen Git baseline for legacy inventory regressions.

    Args:
        repo_root: Temporary copied repository used by projector tests.

    Returns:
        None.

    The production inventory refers to an earlier immutable commit.  The
    isolated fixture needs the same relationship without borrowing the real
    repository's object store, so it commits copied source bytes first and
    then points its Requirement metadata at that local immutable tree.
    """
    _git(repo_root=repo_root, arguments=["init", "--quiet"])
    _git(repo_root=repo_root, arguments=["add", "--all"])
    _git(
        repo_root=repo_root,
        arguments=[
            "-c", "user.name=SEC Metrics Test",
            "-c", "user.email=sec-metrics-test@example.invalid",
            "commit", "--quiet", "-m", "frozen legacy baseline",
        ],
    )
    baseline_commit = _git(
        repo_root=repo_root, arguments=["rev-parse", "HEAD"],
    )
    inventory_path = (
        repo_root / "requirements" / "ai_first_v3_3_1"
        / "legacy_path_inventory.json"
    )
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory["baseline_commit"] = baseline_commit
    inventory["source_files"] = {
        relative: sha256_file(path=repo_root / relative)
        for relative in (
            "config/metric_applicability.yaml",
            "scripts/sec_pipeline.py",
        )
    }
    inventory_path.write_bytes(canonical_json_bytes(value=inventory) + b"\n")

    baseline_path = (
        repo_root / "requirements" / "ai_first_v3_3_1"
        / "baseline_manifest.json"
    )
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline["repository_commit"] = baseline_commit
    baseline["legacy_path_inventory_sha256"] = sha256_file(
        path=inventory_path,
    )
    baseline_path.write_bytes(canonical_json_bytes(value=baseline) + b"\n")


def _rebind_issue15_parent(*, repo_root: Path) -> None:
    """Rebind child transfer metadata to the scoped parent snapshot.

    Args:
        repo_root: Temporary repository whose parent baseline was localized.

    Expected output:
        Issue #15 retains a fully verified parent chain inside the isolated
        test repository without borrowing objects from the real checkout.
    """
    parent_dir = repo_root / "requirements" / "ai_first_v3_3_1"
    issue_dir = repo_root / "requirements" / "issue_15_v1"
    parent = load_requirement_snapshot(snapshot_dir=parent_dir)

    inventory_path = issue_dir / "legacy_semantic_producer_inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory["parent_legacy_inventory_sha256"] = parent["hashes"][
        "legacy_path_inventory_sha256"
    ]
    inventory_path.write_bytes(canonical_json_bytes(value=inventory) + b"\n")
    transfer_path = issue_dir / "transfer_manifest.json"
    transfer = json.loads(transfer_path.read_text(encoding="utf-8"))
    transfer["parent_requirement_closure_hash"] = parent[
        "requirement_closure_hash"
    ]
    transfer["parent_requirement_hashes"] = parent["hashes"]
    for relative, binding in transfer["parent_snapshot_files"].items():
        source = parent_dir / relative
        binding["sha256"] = sha256_file(path=source)
        binding["size"] = source.stat().st_size
    transfer_path.write_bytes(canonical_json_bytes(value=transfer) + b"\n")

    baseline_path = issue_dir / "baseline_manifest.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline["parent_requirement_closure_hash"] = parent[
        "requirement_closure_hash"
    ]
    baseline["parent_requirement_hashes"] = parent["hashes"]
    for relative, path in (
        ("legacy_semantic_producer_inventory.json", inventory_path),
        ("transfer_manifest.json", transfer_path),
    ):
        binding = baseline["snapshot_files"][relative]
        binding["sha256"] = sha256_file(path=path)
        binding["size"] = path.stat().st_size
    baseline_path.write_bytes(canonical_json_bytes(value=baseline) + b"\n")
    _rebind_release_plan_chain(repo_root=repo_root)


def scoped_repository(
    *, workspace: Path, baseline_snapshot_dir: Optional[Path] = None
) -> Path:
    """Create a one-company repository with unchanged production authority.

    Args:
        workspace: Empty fixture workspace.
        baseline_snapshot_dir: Optional frozen fixture legacy snapshot.

    Returns:
        Repository root whose registry contains only the fixture company.
    """
    repo_root = workspace / "repo"
    repo_root.mkdir()
    for relative in ("catalog", "config", "fixtures", "requirements"):
        shutil.copytree(REPO_ROOT / relative, repo_root / relative)
    foundation = json.loads(
        (
            REPO_ROOT
            / "requirements"
            / "issue_15_v1"
            / "foundation_verification_receipt.json"
        ).read_text(encoding="utf-8")
    )
    for binding in foundation["receipt_bindings"]:
        source = REPO_ROOT / binding["path"]
        destination = repo_root / binding["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    policy = json.loads(
        (
            repo_root / "config" / "validation_source_policy.json"
        ).read_text(encoding="utf-8")
    )
    for relative in policy["acceptance_source_files"]:
        source = REPO_ROOT / relative
        destination = repo_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    fixture = (
        "tests/fixtures/vnext/companyfacts_b03_crosscheck/"
        "CIK0000078003.json"
    )
    destination = repo_root / fixture
    destination.parent.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / fixture, destination)
    shutil.copytree(
        REPO_ROOT / "scripts" / "vnext",
        repo_root / "scripts" / "vnext",
    )
    for source in sorted((REPO_ROOT / "scripts").glob("*.py")):
        shutil.copy2(source, repo_root / "scripts" / source.name)
    (repo_root / "tools").mkdir()
    for filename in (
        "check_no_company_literals.py", "check_vnext_semantics.py",
        "run_acceptance.py", "vnext_review.py",
    ):
        shutil.copy2(
            REPO_ROOT / "tools" / filename,
            repo_root / "tools" / filename,
        )
    registry_path = repo_root / "config" / "company_registry.csv"
    with registry_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = [row for row in reader if row["company_id"] == "pfizer"]
        fieldnames = tuple(reader.fieldnames or ())
    if len(rows) != 1:
        raise AssertionError("Scoped registry fixture is ambiguous")
    _write_registry(
        path=registry_path, rows=rows, fieldnames=fieldnames,
    )
    _bind_issue15_scoped_registry(repo_root=repo_root)
    if baseline_snapshot_dir is not None:
        _bind_scoped_baseline(
            repo_root=repo_root, snapshot_dir=baseline_snapshot_dir,
        )
    _bind_scoped_legacy_inventory_to_git(repo_root=repo_root)
    _rebind_issue15_parent(repo_root=repo_root)
    return repo_root
