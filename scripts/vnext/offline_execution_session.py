"""Process-local, exact-file-bound offline work with no persistent cache.

Only immutable bytes cross the session interface. A session owns one source,
one full DerivedAsset and one Requirement construction. Final replay receives
disk locators, not cached objects, and is a separate mandatory operation.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import platform
import resource
import sys
import time
from typing import Callable, Dict, Mapping, Optional

from .canonical import canonical_json_bytes, sha256_bytes
from .requirements import load_requirement_snapshot
from .requirement_profile import validate_execution_authority
from .sources import resolve_repository_file
from .table_grid import build_table_grid


class OfflineSessionError(RuntimeError):
    """Fail closed on source drift, repeated children, UNKNOWN or replay drift."""


class OfflineOperationObserver:
    """Count actual Python operation entries without replacing any verifier.

    This is measurement and a dependency-call guard, not a same-process strong
    sandbox. The benchmark's process-tree/network boundary remains separate.
    No cached result, rewritten function or omitted semantic check is used.
    """

    _FUNCTIONS = {
        ("vnext.table_grid", "build_table_grid"): "derived_asset_builds",
        ("vnext.requirements", "load_requirement_snapshot"): "requirement_load_calls",
        ("vnext.requirement_profile_v1", "_load_profile_requirement_snapshot"): "requirement_builds",
        ("vnext.requirement_profile_v1", "_recorded_parent"): "parent_authority_builds",
        ("vnext.requirements", "_load_issue_15_snapshot"): "legacy_parent_authority_builds",
        ("vnext.canonical", "canonical_json_bytes"): "canonicalizations",
        ("vnext.canonical", "content_hash"): "semantic_hashes",
        ("vnext.canonical", "execution_semantics_hash"): "execution_semantics_hashes",
        ("vnext.run_store", "load_frozen_run"): "native_prior_run_loads",
        ("vnext.ratchet_release", "load_portable_qualification_run"): "portable_prior_run_loads",
        ("vnext.evidence", "check_evidence"): "evidence_checks",
        ("vnext.ai_adapter", "_open_provider_request"): "provider_calls",
        ("sec_http", "urlopen"): "sec_calls",
    }

    def __init__(self) -> None:
        self.counts = {key: 0 for key in set(self._FUNCTIONS.values())}
        self.counts.update(source_materializations=0, paid_model_calls=0)
        self._code_keys = {}
        self._active = False
        self.instrumentation_backend = "NOT_STARTED"
        self._monitoring_codes = []

    def _observe(self, frame, event, argument):
        if event != "call":
            return
        code = frame.f_code
        if code not in self._code_keys:
            module = frame.f_globals.get("__name__", "")
            key = self._FUNCTIONS.get((module, code.co_name))
            if module == "vnext.table_grid" and code.co_name == "__init__":
                if type(frame.f_locals.get("self")).__name__ == "_AllTablesParser":
                    key = "source_materializations"
            self._code_keys[code] = key
        key = self._code_keys[code]
        if key:
            self.counts[key] += 1
            if key in {"provider_calls", "sec_calls"}:
                raise OfflineSessionError("Offline operation attempted forbidden egress: " + key)

    def __enter__(self):
        if self._active or sys.getprofile() is not None:
            raise OfflineSessionError("Offline observation requires an exclusive profiler slot")
        self._active = True
        if hasattr(sys, "monitoring"):
            # 3.12+ can observe only these exact entrypoints. This avoids
            # profiling every cell/string helper and distorting wall time.
            monitor = sys.monitoring
            acquired = False
            try:
                monitor.use_tool_id(4, "secmetrics-offline-operations")
                acquired = True
                for (module_name, name), key in self._FUNCTIONS.items():
                    module = importlib.import_module(module_name)
                    code = getattr(module, name).__code__
                    self._code_keys[code] = key
                    self._monitoring_codes.append(code)
                parser = importlib.import_module("vnext.table_grid")._AllTablesParser
                code = parser.__init__.__code__
                self._code_keys[code] = "source_materializations"
                self._monitoring_codes.append(code)
                monitor.register_callback(4, monitor.events.PY_START, self._monitor_entry)
                for code in self._monitoring_codes:
                    monitor.set_local_events(4, code, monitor.events.PY_START)
            except BaseException:
                if acquired:
                    for code in self._monitoring_codes:
                        monitor.set_local_events(4, code, 0)
                    monitor.register_callback(4, monitor.events.PY_START, None)
                    monitor.free_tool_id(4)
                self._active = False
                raise
            self.instrumentation_backend = "SELECTIVE_SYS_MONITORING_PY_START"
        else:
            sys.setprofile(self._observe)
            self.instrumentation_backend = "SYS_SETPROFILE_FALLBACK"
        return self

    def _monitor_entry(self, code, offset):
        key = self._code_keys[code]
        self.counts[key] += 1
        if key in {"provider_calls", "sec_calls"}:
            raise OfflineSessionError("Offline operation attempted forbidden egress: " + key)

    def __exit__(self, error_type, error, traceback):
        if self.instrumentation_backend == "SELECTIVE_SYS_MONITORING_PY_START":
            monitor = sys.monitoring
            for code in self._monitoring_codes:
                monitor.set_local_events(4, code, 0)
            monitor.register_callback(4, monitor.events.PY_START, None)
            monitor.free_tool_id(4)
        else:
            sys.setprofile(None)
        self._active = False
        return False


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
                 requirement_id: str, requirement_closure_hash: str,
                 materialization_mode: str = "PRODUCTION_LIMITS") -> None:
        self.repo_root = repo_root
        self.source = source
        self.requirement_id = requirement_id
        self.requirement_closure_hash = requirement_closure_hash
        if materialization_mode not in {"PRODUCTION_LIMITS", "GUARDED_OFFLINE_RESEARCH"}:
            raise OfflineSessionError("Unknown offline materialization mode")
        self.materialization_mode = materialization_mode
        self.materialization_report: Optional[Dict[str, object]] = None
        self.state = "NEW"
        self._started = time.perf_counter()
        self._inputs = None
        self._children: Dict[str, bytes] = {}
        self._file_pins: Dict[FileBinding, bytes] = {}
        self._authority_files: Dict[FileBinding, bytes] = {}
        self._authority_directory_pins = {}
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
        try:
            path = resolve_repository_file(repo_root=self.repo_root,
                                           repo_relative_path=binding.path)
            content = path.read_bytes()
        except (OSError, ValueError) as error:
            self.state = "FAILED"
            raise OfflineSessionError("Session path is unreadable or unsafe: " + binding.path) from error
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
        try:
            return self._prepare_once()
        except BaseException:
            self.state = "FAILED"
            raise

    def _prepare_once(self) -> SessionInputs:
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
            directory = self.repo_root / "requirements" / identifier
            entries = list(directory.rglob("*"))
            self._authority_directory_pins[directory] = {
                path.relative_to(directory).as_posix() for path in entries
            }
            paths.extend(entries)
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
        if self.materialization_mode == "GUARDED_OFFLINE_RESEARCH":
            from .r4_materialization import materialize_full_source

            materialized = materialize_full_source(
                repo_root=self.repo_root, source_path=self.source.path,
                source_sha256=self.source.sha256, source_size=self.source.size,
            )
            self.materialization_report = materialized["report"]
            asset_bytes = materialized["asset_bytes"]
        else:
            asset = build_table_grid(
                html_bytes=source_bytes,
                parent_raw_asset_ids=["sha256:" + self.source.sha256],
                storage_uri="offline://full-derived-asset",
            )
            asset_bytes = self._canonical(asset)
        self.counts["derived_asset_builds"] += 1
        self._inputs = SessionInputs(
            source_bytes=source_bytes, derived_asset_bytes=asset_bytes,
            requirement_bytes=self._canonical(requirement), source_binding=self.source,
            requirement_closure_hash=self.requirement_closure_hash,
        )
        self.state = "OPEN"
        return self._inputs

    def _check_pins(self) -> None:
        self._read_exact(self.source)
        for directory, expected in self._authority_directory_pins.items():
            actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*")}
            if actual != expected:
                self.state = "FAILED"
                raise OfflineSessionError("Session Requirement directory entry set changed")
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
            if result.get("status") not in {"PASSED", "PASS", "PASSED_OFFLINE_ONLY"}:
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
            "counter_scope": "SESSION_BOUNDARIES_ONLY; deep operations require OfflineOperationObserver",
            "child_count": len(self._children),
            "wall_seconds": format(time.perf_counter() - self._started, ".6f"),
            "process_peak_rss_bytes": peak_bytes,
            "cache_scope": "PROCESS_LOCAL_EXACT_IMMUTABLE_BYTES_ONLY",
            "evidence_tier": "OFFLINE_INTERFACE_BASELINE",
            "qualification_credit": "NONE",
            "materialization_mode": self.materialization_mode,
            "materialization_report": self.materialization_report,
        }
