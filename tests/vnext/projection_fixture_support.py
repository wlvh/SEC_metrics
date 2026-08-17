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
from vnext.canonical import canonical_json_bytes, sha256_file


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
    if baseline_snapshot_dir is not None:
        _bind_scoped_baseline(
            repo_root=repo_root, snapshot_dir=baseline_snapshot_dir,
        )
    _bind_scoped_legacy_inventory_to_git(repo_root=repo_root)
    return repo_root
