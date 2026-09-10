"""Process-local, exact-file-bound offline work with no persistent cache.

Only immutable bytes cross the session interface. A session owns one source,
one full DerivedAsset and one Requirement construction. Final replay receives
disk locators, not cached objects, and is a separate mandatory operation.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
import platform
import resource
import sys
import time
from typing import Callable, Dict, Mapping, Optional, Sequence

from .canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_loads
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
        ("vnext.requirement_profile_v3", "_load_profile_requirement_snapshot"): "revision_requirement_builds",
        ("vnext.requirement_profile_v1", "_recorded_parent"): "parent_authority_builds",
        ("vnext.requirements", "_load_issue_15_snapshot"): "legacy_parent_authority_builds",
        ("vnext.canonical", "canonical_json_bytes"): "canonicalizations",
        ("vnext.canonical", "content_hash"): "semantic_hashes",
        ("vnext.canonical", "execution_semantics_hash"): "execution_semantics_hashes",
        ("vnext.run_store", "load_frozen_run"): "native_prior_run_loads",
        ("vnext.ratchet_release", "load_portable_qualification_run"): "portable_prior_run_loads",
        ("vnext.evidence", "check_evidence"): "evidence_checks",
        ("vnext.table_payload", "encode_compact_table_payload"): "full_table_encodes",
        ("vnext.table_payload", "decode_compact_table_payload"): "full_table_decodes",
        ("vnext.deterministic_router", "_adapt_xbrl"): "native_xbrl_adaptations",
        ("vnext.deterministic_router", "adapt_accession_xbrl_from_parsed"): "native_xbrl_reevaluations",
        ("vnext.deterministic_router", "_claims_from_xbrl_parts"): "native_xbrl_claim_evaluations",
        ("vnext.r4_structured_sources", "build_pinned_fixture_source_set"): "fixture_source_set_builds",
        ("vnext.composite_scope", "index_source_structure"): "source_structure_scans",
        ("vnext.ai_adapter", "_open_provider_request"): "provider_calls",
        ("sec_http", "urlopen"): "sec_calls",
    }
    _PARSER_CLASSES = {
        ("vnext.deterministic_router", "_XbrlFactParser"): "xbrl_fact_parses",
        ("vnext.deterministic_router", "_XbrlContextParser"): "xbrl_context_parses",
        ("vnext.composite_scope", "_SourceStructure"): "source_structure_parses",
    }
    _active_observer = None

    def __init__(self) -> None:
        self.counts = {key: 0 for key in set(self._FUNCTIONS.values())}
        self.counts.update(source_materializations=0, paid_model_calls=0, derived_asset_json_decodes=0)
        self.counts.update({label: 0 for label in self._PARSER_CLASSES.values()})
        self._code_keys = {}
        self._active = False
        self.instrumentation_backend = "NOT_STARTED"
        self._monitoring_codes = []
        self.source_censuses = []
        self._shared_parent = None
        self._shared_before = None
        self._shared_census_start = 0

    def _capture_parser(self, parser):
        if type(parser).__name__ != "_AllTablesParser":
            raise OfflineSessionError("Observed source parser identity differs")
        self.source_censuses.append({
            "raw_source_cells": parser._total_raw_cell_count,
            "table_count": len(parser.tables),
            "raw_table_text_characters": parser._total_text_char_count,
        })

    def _observe(self, frame, event, argument):
        if (event == "return" and frame.f_globals.get("__name__") == "json"
                and frame.f_code.co_name == "loads" and isinstance(argument, dict)
                and argument.get("record_type") == "DERIVED_ASSET"):
            self.counts["derived_asset_json_decodes"] += 1
        if event == "return" and frame.f_globals.get("__name__") == "vnext.table_grid" and frame.f_code.co_name == "close":
            self._capture_parser(frame.f_locals.get("self"))
        if event != "call":
            return
        code = frame.f_code
        if code not in self._code_keys:
            module = frame.f_globals.get("__name__", "")
            key = self._FUNCTIONS.get((module, code.co_name))
            if module == "vnext.table_grid" and code.co_name == "__init__":
                if type(frame.f_locals.get("self")).__name__ == "_AllTablesParser":
                    key = "source_materializations"
            if code.co_name == "__init__":
                key = self._PARSER_CLASSES.get((module, type(frame.f_locals.get("self")).__name__), key)
            self._code_keys[code] = key
        key = self._code_keys[code]
        if key:
            self.counts[key] += 1
            if key in {"provider_calls", "sec_calls"}:
                raise OfflineSessionError("Offline operation attempted forbidden egress: " + key)

    def __enter__(self):
        if self._active:
            raise OfflineSessionError("Offline observation requires an exclusive profiler slot")
        if self._active_observer is not None:
            self._shared_parent = self._active_observer
            self._shared_before = dict(self._shared_parent.counts)
            self._shared_census_start = len(self._shared_parent.source_censuses)
            self.instrumentation_backend = self._shared_parent.instrumentation_backend
            self._active = True
            return self
        if sys.getprofile() is not None:
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
                for (module_name, name), key in self._PARSER_CLASSES.items():
                    code = getattr(importlib.import_module(module_name), name).__init__.__code__
                    self._code_keys[code] = key
                    self._monitoring_codes.append(code)
                parser = importlib.import_module("vnext.table_grid")._AllTablesParser
                code = parser.__init__.__code__
                self._code_keys[code] = "source_materializations"
                self._monitoring_codes.append(code)
                monitor.register_callback(4, monitor.events.PY_START, self._monitor_entry)
                for code in self._monitoring_codes:
                    monitor.set_local_events(4, code, monitor.events.PY_START)
                self._monitoring_codes.append(parser.close.__code__)
                monitor.register_callback(4, monitor.events.PY_RETURN, self._monitor_parser_return)
                monitor.set_local_events(4, parser.close.__code__, monitor.events.PY_RETURN)
                self._monitoring_codes.append(json.loads.__code__)
                monitor.set_local_events(4, json.loads.__code__, monitor.events.PY_RETURN)
            except BaseException:
                if acquired:
                    for code in self._monitoring_codes:
                        monitor.set_local_events(4, code, 0)
                    monitor.register_callback(4, monitor.events.PY_START, None)
                    monitor.register_callback(4, monitor.events.PY_RETURN, None)
                    monitor.free_tool_id(4)
                self._active = False
                raise
            self.instrumentation_backend = "SELECTIVE_SYS_MONITORING_PY_START"
        else:
            sys.setprofile(self._observe)
            self.instrumentation_backend = "SYS_SETPROFILE_FALLBACK"
        type(self)._active_observer = self
        return self

    def _monitor_entry(self, code, offset):
        key = self._code_keys[code]
        self.counts[key] += 1
        if key in {"provider_calls", "sec_calls"}:
            raise OfflineSessionError("Offline operation attempted forbidden egress: " + key)

    def _monitor_parser_return(self, code, offset, value):
        if code is json.loads.__code__:
            if isinstance(value, dict) and value.get("record_type") == "DERIVED_ASSET":
                self.counts["derived_asset_json_decodes"] += 1
            return
        self._capture_parser(sys._getframe(1).f_locals.get("self"))

    def __exit__(self, error_type, error, traceback):
        if self._shared_parent is not None:
            self.counts = {key: count - self._shared_before[key]
                           for key, count in self._shared_parent.counts.items()}
            self.source_censuses = list(self._shared_parent.source_censuses[self._shared_census_start:])
            self._active = False
            return False
        if self.instrumentation_backend == "SELECTIVE_SYS_MONITORING_PY_START":
            monitor = sys.monitoring
            for code in self._monitoring_codes:
                monitor.set_local_events(4, code, 0)
            monitor.register_callback(4, monitor.events.PY_START, None)
            monitor.register_callback(4, monitor.events.PY_RETURN, None)
            monitor.free_tool_id(4)
        else:
            sys.setprofile(None)
        self._active = False
        type(self)._active_observer = None
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


class OfflinePriorRunSet:
    """Replay immutable main history once, then rehash its exact disk closure.

    The set stores file/content identities and small terminal summaries only;
    it does not cache or reuse provider responses. It never returns live
    authorization. A changed/added/removed file latches FAILED even if restored.
    """

    def __init__(self, *, repo_root: Path, manifests: Sequence[FileBinding]) -> None:
        if len(manifests) < 6 or len({b.path for b in manifests}) != len(manifests):
            raise OfflineSessionError("Prior performance workload needs six distinct Run manifests")
        self.repo_root = repo_root
        self.manifests = tuple(manifests)
        self.state = "NEW"
        self._files = {}
        self._directory_entries = {}
        self._summary_bytes = b""
        self.observed_operation_counts = {}

    def _pin(self, relative):
        path = resolve_repository_file(repo_root=self.repo_root, repo_relative_path=relative)
        data = path.read_bytes()
        self._files[relative] = FileBinding(relative, sha256_bytes(content=data), len(data))

    def prepare(self) -> bytes:
        if self.state == "READY":
            self.assert_unchanged()
            return self._summary_bytes
        if self.state != "NEW":
            raise OfflineSessionError("Prior Run set is terminal")
        from .ratchet_release import load_portable_qualification_run

        rows = []
        try:
            with OfflineOperationObserver() as observed:
                for binding in self.manifests:
                    if not binding.path.startswith("artifacts/vnext/qualification/cycles/") or not binding.path.endswith("/manifest.json"):
                        raise OfflineSessionError("Prior Run is outside immutable qualification history")
                    manifest_path = resolve_repository_file(repo_root=self.repo_root, repo_relative_path=binding.path)
                    data = manifest_path.read_bytes()
                    if len(data) != binding.size or sha256_bytes(content=data) != binding.sha256:
                        raise OfflineSessionError("Prior Run manifest differs from the pinned main input")
                    manifest, records, _ = load_portable_qualification_run(manifest_path.parent, self.repo_root)
                    if manifest["status"] != "FROZEN":
                        raise OfflineSessionError("Prior Run is not a verified terminal")
                    rows.append({
                        "manifest": {"path": binding.path, "sha256": binding.sha256, "size": binding.size},
                        "run_id": manifest["run_id"], "content_manifest_hash": manifest["content_manifest_hash"],
                        "audit_manifest_hash": manifest["audit_manifest_hash"], "status": "FROZEN",
                    })
                    cycle_dir = manifest_path.parents[2]
                    if cycle_dir not in self._directory_entries:
                        entries = set()
                        for path in cycle_dir.rglob("*"):
                            if path.is_symlink():
                                raise OfflineSessionError("Prior cycle closure contains a symlink")
                            entries.add(path.relative_to(cycle_dir).as_posix())
                            if path.is_file():
                                self._pin(path.relative_to(self.repo_root).as_posix())
                            elif not path.is_dir():
                                raise OfflineSessionError("Prior cycle closure contains a special file")
                        self._directory_entries[cycle_dir] = entries
                    for record in records:
                        if record["record_type"] == "RAW_BLOB":
                            self._pin(record["storage_uri"])
                    for relative in manifest["spec_file_hashes"]:
                        self._pin(relative)
                if len({row["run_id"] for row in rows}) != len(rows):
                    raise OfflineSessionError("Prior history contains duplicate Run identities")
                body = {"terminals": rows, "qualification_credit": "NONE_PERFORMANCE_INPUT_ONLY"}
                self._summary_bytes = canonical_json_bytes(value={**body, "prior_run_set_id": content_hash(value=body)})
            self.observed_operation_counts = dict(observed.counts)
            self.state = "READY"
            self.assert_unchanged()
            return self._summary_bytes
        except BaseException:
            self.state = "FAILED"
            raise

    def assert_unchanged(self) -> None:
        if self.state != "READY":
            raise OfflineSessionError("Prior Run set is not verified")
        try:
            for directory, expected in self._directory_entries.items():
                current = {p.relative_to(directory).as_posix() for p in directory.rglob("*")}
                if current != expected:
                    raise OfflineSessionError("Prior cycle file set changed; recovery is not implicit")
            for relative, binding in self._files.items():
                path = resolve_repository_file(repo_root=self.repo_root, repo_relative_path=relative)
                data = path.read_bytes()
                if len(data) != binding.size or sha256_bytes(content=data) != binding.sha256:
                    raise OfflineSessionError("Prior Run/source/control bytes changed")
        except BaseException:
            self.state = "FAILED"
            raise


class OfflineExecutionSession:
    """Bound one process-local source session; never authorize network work."""

    def __init__(self, *, repo_root: Path, source: FileBinding,
                 requirement_id: str, requirement_closure_hash: str,
                 materialization_mode: str = "PRODUCTION_LIMITS") -> None:
        self.repo_root = repo_root
        self.source = source
        self.requirement_id = requirement_id
        self.requirement_closure_hash = requirement_closure_hash
        if materialization_mode not in {"PRODUCTION_LIMITS", "GUARDED_PRODUCTION_PARSER"}:
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
        self._observed_counts = dict(OfflineOperationObserver().counts)

    def _measure(self, operation):
        """Observe real work even if a benchmark already owns the observer."""
        active = OfflineOperationObserver._active_observer
        if active is None:
            with OfflineOperationObserver():
                return self._measure(operation)
        before = dict(active.counts)
        try:
            return operation()
        finally:
            for key, count in active.counts.items():
                self._observed_counts[key] += count - before[key]

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

    def _pin_authority_chain(self, requirement: Mapping) -> None:
        """Pin the already-verified chain, not just one immediate parent.

        A revision may add another parent layer. Walking the returned
        immutable authority tree avoids rebuilding it and keeps every old
        snapshot/retained engine dependency in the child drift guard.
        """
        snapshots, engine_paths = set(), set()
        current = requirement
        while current is not None:
            identifier = current["requirement_id"]
            if identifier in snapshots:
                raise OfflineSessionError("Session authority contains a repeated parent")
            snapshots.add(identifier)
            baseline = current["baseline"]
            validator = baseline.get("validator")
            if validator is not None:
                engine_paths.add(validator["path"])
                engine_paths.update(validator["dependencies"])
            # The retained issue_15 reconstruction intentionally does not
            # rebuild its foundation adapter, but still records its identity.
            recorded_foundation = baseline.get("parent_requirement_id")
            if recorded_foundation is not None:
                snapshots.add(recorded_foundation)
            current = current.get("parent_snapshot")
        paths = []
        for identifier in sorted(snapshots):
            directory = self.repo_root / "requirements" / identifier
            if not directory.is_dir() or directory.is_symlink():
                raise OfflineSessionError("Session authority snapshot is unavailable or unsafe")
            entries = list(directory.rglob("*"))
            self._authority_directory_pins[directory] = {
                path.relative_to(directory).as_posix() for path in entries
            }
            paths.extend(entries)
        paths.extend(self.repo_root / p for p in requirement["execution_authority"]["files"])
        paths.extend(self.repo_root / p for p in sorted(engine_paths))
        for path in paths:
            if path.is_dir() and not path.is_symlink():
                continue
            relative = path.relative_to(self.repo_root).as_posix()
            regular = resolve_repository_file(repo_root=self.repo_root,
                                              repo_relative_path=relative)
            data = regular.read_bytes()
            binding = FileBinding(relative, sha256_bytes(content=data), len(data))
            self._authority_files[binding] = data

    def prepare(self) -> SessionInputs:
        """Materialize the full source and parent/Requirement exactly once."""
        if self.state == "OPEN":
            self._check_pins()
            return self._inputs
        if self.state != "NEW":
            raise OfflineSessionError("Session is terminal: " + self.state)
        try:
            return self._measure(self._prepare_once)
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
        # A source/authority mutation never gets an mtime-based cache hit.
        self._pin_authority_chain(requirement)
        self.counts["source_materializations"] += 1
        if self.materialization_mode == "GUARDED_PRODUCTION_PARSER":
            from .r4_materialization import materialize_full_source

            materialized = materialize_full_source(
                repo_root=self.repo_root, source_path=self.source.path,
                source_sha256=self.source.sha256, source_size=self.source.size,
            )
            self.materialization_report = materialized["report"]
            asset_bytes = materialized["asset_bytes"]
            for key, count in materialized["report"]["observed_operation_counts"].items():
                self._observed_counts[key] += count
        else:
            asset = build_table_grid(
                html_bytes=source_bytes,
                parent_raw_asset_ids=["sha256:" + self.source.sha256],
                storage_uri="offline://full-derived-asset/" + self.source.sha256,
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
        before = dict(self._observed_counts)
        try:
            def execute():
                result = operation(self._inputs)
                if result.get("status") not in {"PASSED", "PASS", "PASSED_OFFLINE_ONLY"}:
                    raise OfflineSessionError("Offline child did not reach a successful terminal")
                return self._canonical(result)

            value = self._measure(execute)
            for key in ("source_materializations", "derived_asset_builds", "requirement_builds",
                        "revision_requirement_builds",
                        "parent_authority_builds", "requirement_load_calls", "legacy_parent_authority_builds",
                        "native_prior_run_loads", "portable_prior_run_loads"):
                if self._observed_counts[key] != before[key]:
                    raise OfflineSessionError("Child rebuilt or replayed full immutable authority: " + key)
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
            "observed_operation_counts": dict(self._observed_counts),
            "counter_scope": "BOUNDARY_COUNTS_PLUS_ACTUAL_SELECTIVE_NATIVE_OPERATION_COUNTS",
            "child_count": len(self._children),
            "wall_seconds": format(time.perf_counter() - self._started, ".6f"),
            "process_peak_rss_bytes": peak_bytes,
            "cache_scope": "PROCESS_LOCAL_EXACT_IMMUTABLE_BYTES_ONLY",
            "evidence_tier": "OFFLINE_INTERFACE_BASELINE",
            "qualification_credit": "NONE",
            "materialization_mode": self.materialization_mode,
            "materialization_report": self.materialization_report,
        }


class OfflineExecutionGroup:
    """Coordinate source sessions with exactly one aggregate fresh disk replay."""

    def __init__(self, *, sessions: Sequence[OfflineExecutionSession]) -> None:
        if (not sessions or any(type(s) is not OfflineExecutionSession for s in sessions)
                or len({s.source for s in sessions}) != len(sessions)):
            raise OfflineSessionError("Offline group needs distinct source sessions")
        first = sessions[0]
        if any((s.repo_root, s.requirement_id, s.requirement_closure_hash) != (
                first.repo_root, first.requirement_id, first.requirement_closure_hash) for s in sessions):
            raise OfflineSessionError("Offline group crosses repository/Requirement authority")
        self.sessions = tuple(sessions)
        self.state = "OPEN"
        self.final_independent_disk_replays = 0

    def final_disk_replay(self, *, replay: Callable) -> bytes:
        if self.state != "OPEN" or self.final_independent_disk_replays:
            raise OfflineSessionError("Aggregate final replay is not available")
        first = self.sessions[0]
        try:
            for session in self.sessions:
                if session.state != "OPEN" or session.counts["final_independent_disk_replays"]:
                    raise OfflineSessionError("A grouped source session is not open")
                session._check_pins()
            self.final_independent_disk_replays += 1
            # No cached source/asset/task object crosses this seam.
            result = replay(first.repo_root, tuple(s.source for s in self.sessions),
                            first.requirement_id, first.requirement_closure_hash)
            if result.get("status") != "PASSED":
                raise OfflineSessionError("Independent aggregate disk replay failed")
            encoded = canonical_json_bytes(value=result)
            for session in self.sessions:
                session._check_pins()
                session.state = "FINALIZED"
            self.state = "FINALIZED"
            return encoded
        except BaseException:
            self.state = "FAILED"
            for session in self.sessions:
                session.state = "FAILED"
            raise
