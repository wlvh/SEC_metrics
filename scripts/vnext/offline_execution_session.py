"""Process-local, exact-file-bound offline work with no persistent cache.

Only immutable bytes cross the session interface. A session owns one source,
one full DerivedAsset and one Requirement construction. Final replay receives
disk locators, not cached objects, and is a separate mandatory operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import platform
import resource
import time
from typing import Callable, Dict, Mapping

from .canonical import canonical_json_bytes, sha256_bytes
from .requirements import load_requirement_snapshot
from .requirement_profile import validate_execution_authority
from .sources import resolve_repository_file
from .table_grid import build_table_grid


class OfflineSessionError(RuntimeError):
    """Fail closed on source drift, repeated children, UNKNOWN or replay drift."""


@dataclass(frozen=True)
class FileBinding:
    """An immutable regular-file cache key; mtime is never authority."""

    path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class SessionInputs:
    """Immutable full inputs shared with offline child work."""

    source_bytes: bytes
    derived_asset_bytes: bytes
    requirement_bytes: bytes
    source_binding: FileBinding
    requirement_closure_hash: str


class OfflineExecutionSession:
    """Bound one process-local source session; never authorize network work."""

    def __init__(self, *, repo_root: Path, source: FileBinding,
                 requirement_id: str, requirement_closure_hash: str) -> None:
        self.repo_root = repo_root
        self.source = source
        self.requirement_id = requirement_id
        self.requirement_closure_hash = requirement_closure_hash
        self.state = "NEW"
        self._started = time.perf_counter()
        self._inputs = None
        self._children: Dict[str, bytes] = {}
        self._file_pins: Dict[FileBinding, bytes] = {}
        self._authority_files: Dict[FileBinding, bytes] = {}
        self.counts = {
            "source_materializations": 0, "derived_asset_builds": 0,
            "parent_authority_builds": 0, "prior_run_loads": 0,
            "full_prior_run_replays_per_child": 0,
            "full_derived_asset_rebuilds_per_child": 0,
            "canonicalizations": 0, "semantic_hashes": 0,
            "provider_calls": 0, "paid_model_calls": 0, "sec_calls": 0,
            "final_independent_disk_replays": 0,
        }

    def _read_exact(self, binding: FileBinding) -> bytes:
        path = resolve_repository_file(repo_root=self.repo_root,
                                       repo_relative_path=binding.path)
        content = path.read_bytes()
        if len(content) != binding.size or sha256_bytes(content=content) != binding.sha256:
            self.state = "FAILED"
            raise OfflineSessionError("Session exact path/hash/size drift: " + binding.path)
        return content

    def _canonical(self, value: Mapping) -> bytes:
        self.counts["canonicalizations"] += 1
        return canonical_json_bytes(value=value)

    def prepare(self) -> SessionInputs:
        """Materialize the full source and parent/Requirement exactly once."""
        if self.state == "OPEN":
            self._check_pins()
            return self._inputs
        if self.state != "NEW":
            raise OfflineSessionError("Session is terminal: " + self.state)
        source_bytes = self._read_exact(self.source)
        requirement = load_requirement_snapshot(
            snapshot_dir=self.repo_root / "requirements" / self.requirement_id,
        )
        self.counts["parent_authority_builds"] += 1
        if requirement["requirement_closure_hash"] != self.requirement_closure_hash:
            self.state = "FAILED"
            raise OfflineSessionError("Session Requirement closure differs")
        validate_execution_authority(repo_root=self.repo_root, requirement=requirement)
        # Pin the complete recorded snapshot family and execution-authority
        # inputs. A source/authority mutation never gets an mtime-based hit.
        snapshots = [self.requirement_id, requirement["parent_requirement_id"]]
        snapshots.append("ai_first_v3_3_1")
        paths = []
        for identifier in snapshots:
            paths.extend((self.repo_root / "requirements" / identifier).rglob("*"))
        paths.extend(self.repo_root / p for p in requirement["execution_authority"]["files"])
        paths.append(self.repo_root / requirement["baseline"]["validator"]["path"])
        for path in paths:
            if path.is_dir() and not path.is_symlink():
                continue
            relative = path.relative_to(self.repo_root).as_posix()
            regular = resolve_repository_file(repo_root=self.repo_root,
                                              repo_relative_path=relative)
            data = regular.read_bytes()
            binding = FileBinding(relative, sha256_bytes(content=data), len(data))
            self._authority_files[binding] = data
        self.counts["source_materializations"] += 1
        asset = build_table_grid(
            html_bytes=source_bytes,
            parent_raw_asset_ids=["sha256:" + self.source.sha256],
            storage_uri="offline://full-derived-asset",
        )
        self.counts["derived_asset_builds"] += 1
        self._inputs = SessionInputs(
            source_bytes=source_bytes, derived_asset_bytes=self._canonical(asset),
            requirement_bytes=self._canonical(requirement), source_binding=self.source,
            requirement_closure_hash=self.requirement_closure_hash,
        )
        self.state = "OPEN"
        return self._inputs

    def _check_pins(self) -> None:
        self._read_exact(self.source)
        for binding in self._authority_files:
            self._read_exact(binding)
        for binding in self._file_pins:
            self._read_exact(binding)

    def pin_prior_terminal_file(self, *, binding: FileBinding) -> bytes:
        """Pin exact prior-Run bytes once; this alone is not a Run replay PASS."""
        if self.state != "OPEN":
            raise OfflineSessionError("Prior-Run inventory requires an open session")
        content = self._read_exact(binding)
        if binding not in self._file_pins:
            self.counts["prior_run_loads"] += 1
            self._file_pins[binding] = content
        return self._file_pins[binding]

    def run_child(self, *, child_id: str,
                  operation: Callable[[SessionInputs], Mapping]) -> bytes:
        """Run a new offline child with immutable bytes and no implicit retry."""
        if self.state != "OPEN" or not child_id or child_id in self._children:
            raise OfflineSessionError("Child is repeated or session is not open")
        self._check_pins()
        self._children[child_id] = b"PENDING"
        try:
            result = operation(self._inputs)
            if result.get("status") in {"UNKNOWN", "PENDING", "FAILED"}:
                raise OfflineSessionError("Offline child did not reach a successful terminal")
            value = self._canonical(result)
            self._check_pins()
        except BaseException:
            self.state = "FAILED"
            raise
        self._children[child_id] = value
        return value

    def final_disk_replay(self, *, replay: Callable[[Path, FileBinding, str, str], Mapping]) -> bytes:
        """Require one independent disk replay; the callback gets no cached input."""
        if self.state != "OPEN" or self.counts["final_independent_disk_replays"]:
            raise OfflineSessionError("Final replay is not available")
        self._check_pins()
        self.counts["final_independent_disk_replays"] += 1
        try:
            result = replay(self.repo_root, self.source, self.requirement_id,
                            self.requirement_closure_hash)
            if result.get("status") != "PASSED":
                raise OfflineSessionError("Independent final disk replay failed")
            output = self._canonical(result)
            self._check_pins()
        except BaseException:
            self.state = "FAILED"
            raise
        self.state = "FINALIZED"
        return output

    def report(self) -> Dict[str, object]:
        """Expose observed wall/RSS and boundary-operation counters, not live credit."""
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_bytes = peak if platform.system() == "Darwin" else peak * 1024
        return {
            "state": self.state, "operation_counts": dict(self.counts),
            "child_count": len(self._children),
            "wall_seconds": format(time.perf_counter() - self._started, ".6f"),
            "process_peak_rss_bytes": peak_bytes,
            "cache_scope": "PROCESS_LOCAL_EXACT_IMMUTABLE_BYTES_ONLY",
            "evidence_tier": "OFFLINE_INTERFACE_BASELINE",
            "qualification_credit": "NONE",
        }
