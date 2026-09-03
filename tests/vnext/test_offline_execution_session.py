"""B0 session counters, immutable byte reuse, terminal stop and disk replay."""

import json
from dataclasses import asdict
from decimal import Decimal
import inspect
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.r4_b0_fixture_support import REPO_ROOT, SOURCE_PATH
from vnext.canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_file
from vnext.offline_execution_session import FileBinding, OfflineExecutionSession, OfflineExecutionGroup
from vnext.offline_execution_session import OfflinePriorRunSet
from vnext.offline_execution_session import OfflineSessionError
from vnext.offline_execution_session import OfflineOperationObserver
from vnext.r4_materialization import materialize_full_source, OfflineMaterializationError, PINNED_IMAGE_ID
from vnext.requirements import load_requirement_snapshot
from vnext.resource_limits import RESOURCE_LIMITS
from vnext.sources import resolve_repository_file
from vnext.table_grid import build_table_grid, TableGridError


class OfflineExecutionSessionTest(unittest.TestCase):
    def _session(self):
        data = (REPO_ROOT / SOURCE_PATH).read_bytes()
        return OfflineExecutionSession(
            repo_root=REPO_ROOT,
            source=FileBinding(SOURCE_PATH, sha256_bytes(content=data), len(data)),
            requirement_id="issue_28_v1",
            requirement_closure_hash="sha256:08994b0aa3324511ce655958fbe3c48fdcd873fa2d63a9bfe4de573046d519ac",
        )

    def test_prepare_once_six_children_and_one_independent_disk_replay(self):
        session = self._session()
        inputs = session.prepare()
        self.assertIs(inputs, session.prepare())
        for i in range(6):
            session.run_child(child_id="child:" + str(i), operation=lambda current: {
                "status": "PASSED", "same_immutable_object": current is inputs,
                "source_size": len(current.source_bytes),
            })
        cached_id = json.loads(inputs.derived_asset_bytes)["derived_asset_id"]

        def replay(root, binding, requirement_id, closure):
            data = (root / binding.path).read_bytes()
            self.assertEqual(binding.sha256, sha256_bytes(content=data))
            fresh = build_table_grid(html_bytes=data, parent_raw_asset_ids=["sha256:" + binding.sha256],
                                     storage_uri="offline://independent-final-disk")
            self.assertEqual(cached_id, fresh["derived_asset_id"])
            authority = load_requirement_snapshot(snapshot_dir=root / "requirements" / requirement_id)
            self.assertEqual(closure, authority["requirement_closure_hash"])
            return {"status": "PASSED", "derived_asset_id": fresh["derived_asset_id"]}

        session.final_disk_replay(replay=replay)
        report = session.report()
        self.assertEqual("FINALIZED", report["state"])
        for key in ("source_materializations", "derived_asset_builds", "parent_authority_builds", "final_independent_disk_replays"):
            self.assertEqual(1, report["operation_counts"][key])
        for key in ("full_prior_run_replays_per_child", "full_derived_asset_rebuilds_per_child", "provider_calls", "paid_model_calls", "sec_calls"):
            self.assertEqual(0, report["operation_counts"][key])
        with self.assertRaises(OfflineSessionError):
            session.final_disk_replay(replay=replay)

    def test_unknown_is_terminal_and_cannot_be_retried(self):
        session = self._session()
        session.prepare()
        with self.assertRaises(OfflineSessionError):
            session.run_child(child_id="unknown", operation=lambda _: {"status": "UNKNOWN"})
        with self.assertRaises(OfflineSessionError):
            session.run_child(child_id="later", operation=lambda _: {"status": "PASSED"})
        self.assertEqual("FAILED", session.report()["state"])

    def test_exact_file_hash_and_size_are_required(self):
        session = self._session()
        session.source = FileBinding(SOURCE_PATH, "0" * 64, session.source.size)
        with self.assertRaises(OfflineSessionError):
            session.prepare()
        self.assertEqual("FAILED", session.state)

    def test_deep_observer_counts_native_work_without_replacing_verifiers(self):
        session = self._session()
        with OfflineOperationObserver() as observed:
            session.prepare()
            session.prepare()
            for index in range(6):
                session.run_child(child_id=str(index), operation=lambda _: {"status": "PASS"})
        self.assertEqual(1, observed.counts["source_materializations"])
        self.assertEqual(1, observed.counts["derived_asset_builds"])
        self.assertEqual(1, observed.counts["requirement_builds"])
        self.assertEqual(1, observed.counts["parent_authority_builds"])
        self.assertEqual(1, len(observed.source_censuses))
        self.assertEqual(6, observed.source_censuses[0]["raw_source_cells"])
        self.assertEqual(3, observed.source_censuses[0]["table_count"])
        self.assertGreater(observed.counts["canonicalizations"], session.counts["canonicalizations"])
        self.assertGreater(observed.counts["semantic_hashes"], 0)
        self.assertEqual(0, observed.counts["native_prior_run_loads"])
        self.assertEqual(0, observed.counts["portable_prior_run_loads"])
        for key in ("provider_calls", "paid_model_calls", "sec_calls"):
            self.assertEqual(0, observed.counts[key])

    def test_nested_observer_counts_actual_full_json_decode_once(self):
        asset = build_table_grid(html_bytes=(REPO_ROOT / SOURCE_PATH).read_bytes(),
            parent_raw_asset_ids=["sha256:" + "a" * 64], storage_uri="offline://decode-count")
        encoded = canonical_json_bytes(value=asset)
        with OfflineOperationObserver() as outer:
            with OfflineOperationObserver() as inner:
                restored = json.loads(encoded)
            self.assertEqual(asset, restored)
            self.assertEqual(1, inner.counts["derived_asset_json_decodes"])
        self.assertEqual(1, outer.counts["derived_asset_json_decodes"])
        self.assertEqual(0, outer.counts["derived_asset_builds"])

    def test_crash_and_unknown_status_are_terminal_and_never_retried(self):
        for status in ("UNKNOWN", "PENDING", "FAILED", "CRASHED", "REUSED_SUCCESS", None):
            with self.subTest(status=status):
                session = self._session()
                session.prepare()
                with self.assertRaises(OfflineSessionError):
                    session.run_child(child_id="first", operation=lambda _: {"status": status})
                self.assertEqual("FAILED", session.state)
                with self.assertRaises(OfflineSessionError):
                    session.run_child(child_id="second", operation=lambda _: {"status": "PASS"})
                self.assertEqual(0, session.counts["final_independent_disk_replays"])

    def test_child_exception_never_allows_later_execution_or_replay(self):
        session = self._session()
        session.prepare()

        def crash(_):
            raise RuntimeError("synthetic local crash")

        with self.assertRaisesRegex(RuntimeError, "synthetic local crash"):
            session.run_child(child_id="crash", operation=crash)
        self.assertEqual("FAILED", session.state)
        with self.assertRaises(OfflineSessionError):
            session.final_disk_replay(replay=lambda *_: {"status": "PASSED"})

    def test_child_cannot_hide_a_real_full_source_rebuild_in_success(self):
        session = self._session()
        session.prepare()

        def rebuild(inputs):
            build_table_grid(
                html_bytes=inputs.source_bytes,
                parent_raw_asset_ids=["sha256:" + inputs.source_binding.sha256],
                storage_uri="offline://forbidden-per-child-rebuild",
            )
            return {"status": "PASSED"}

        with self.assertRaisesRegex(OfflineSessionError, "rebuilt or replayed"):
            session.run_child(child_id="rebuild", operation=rebuild)
        self.assertEqual("FAILED", session.state)
        self.assertEqual(2, session.report()["observed_operation_counts"]["derived_asset_builds"])

    def test_child_cannot_rebuild_full_requirement_authority(self):
        session = self._session()
        session.prepare()

        def rebuild(_):
            load_requirement_snapshot(snapshot_dir=REPO_ROOT / "requirements/issue_28_v1")
            return {"status": "PASSED"}

        with self.assertRaisesRegex(OfflineSessionError, "rebuilt or replayed"):
            session.run_child(child_id="authority-rebuild", operation=rebuild)
        self.assertEqual("FAILED", session.state)

    def test_disk_hash_pin_rejects_same_size_mutation_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            p = root / "source.bin"
            p.write_bytes(b"original")
            session = OfflineExecutionSession(
                repo_root=root, source=FileBinding("source.bin", sha256_bytes(content=b"original"), 8),
                requirement_id="issue_28_v1", requirement_closure_hash="sha256:" + "0" * 64,
            )
            self.assertEqual(b"original", session._read_exact(session.source))
            p.write_bytes(b"mutated!")
            with self.assertRaises(OfflineSessionError):
                session._read_exact(session.source)
            p.unlink()
            other = root / "other.bin"
            other.write_bytes(b"original")
            p.symlink_to(other)
            with self.assertRaises(OfflineSessionError):
                session._read_exact(session.source)
            self.assertEqual("FAILED", session.state)

    def test_guarded_materializer_does_not_pull_when_local_image_is_absent(self):
        data = (REPO_ROOT / SOURCE_PATH).read_bytes()
        failed = subprocess.CompletedProcess([], 1, stdout="", stderr="no local image")
        with patch("vnext.r4_materialization.subprocess.run", return_value=failed) as run:
            with self.assertRaisesRegex(OfflineMaterializationError, "no pull"):
                materialize_full_source(
                    repo_root=REPO_ROOT, source_path=SOURCE_PATH,
                    source_sha256=sha256_bytes(content=data), source_size=len(data),
                )
        self.assertEqual(1, run.call_count)
        self.assertEqual(["docker", "image", "inspect"], run.call_args.args[0][:3])

    def test_snapshot_entry_addition_is_terminal_even_if_later_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.bin").write_bytes(b"original")
            authority = root / "requirements"
            authority.mkdir()
            session = OfflineExecutionSession(
                repo_root=root, source=FileBinding("source.bin", sha256_bytes(content=b"original"), 8),
                requirement_id="issue_28_v1", requirement_closure_hash="sha256:" + "0" * 64,
            )
            session.state = "OPEN"
            session._authority_directory_pins[authority] = set()
            session._check_pins()
            extra = authority / "detached.json"
            extra.write_bytes(b"{}")
            with self.assertRaisesRegex(OfflineSessionError, "entry set changed"):
                session._check_pins()
            extra.unlink()
            with self.assertRaises(OfflineSessionError):
                session.run_child(child_id="after-restore", operation=lambda _: {"status": "PASS"})

    def test_revision_session_pins_all_parent_levels_and_retained_engine_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.bin").write_bytes(b"source")
            for identifier in ("issue_28_v2", "issue_28_v1", "issue_15_v1", "ai_first_v3_3_1"):
                snapshot = root / "requirements" / identifier
                snapshot.mkdir(parents=True)
                (snapshot / "binding.json").write_bytes(b"{}")
            engines = root / "scripts/vnext"
            engines.mkdir(parents=True)
            for name in ("engine_v3.py", "engine_v1.py", "engine_support.py"):
                (engines / name).write_bytes(b"# retained\n")
            parent = {"requirement_id": "issue_15_v1",
                      "baseline": {"parent_requirement_id": "ai_first_v3_3_1"}}
            parent = {"requirement_id": "issue_28_v1", "parent_snapshot": parent,
                      "baseline": {"validator": {"path": "scripts/vnext/engine_v1.py",
                                                  "dependencies": {"scripts/vnext/engine_support.py": {}}}}}
            current = {"requirement_id": "issue_28_v2", "parent_snapshot": parent,
                       "baseline": {"validator": {"path": "scripts/vnext/engine_v3.py", "dependencies": {}}},
                       "execution_authority": {"files": {}}}
            source = FileBinding("source.bin", sha256_bytes(content=b"source"), 6)
            for changed in ("requirements/issue_15_v1/binding.json", "scripts/vnext/engine_support.py"):
                with self.subTest(changed=changed):
                    session = OfflineExecutionSession(repo_root=root, source=source,
                        requirement_id="issue_28_v2", requirement_closure_hash="sha256:" + "a" * 64)
                    session._pin_authority_chain(current)
                    session.state = "OPEN"
                    session._check_pins()
                    self.assertEqual(4, len(session._authority_directory_pins))
                    original = (root / changed).read_bytes()
                    (root / changed).write_bytes(original + b" ")
                    with self.assertRaisesRegex(OfflineSessionError, "drift"):
                        session._check_pins()
                    (root / changed).write_bytes(original)
                    with self.assertRaises(OfflineSessionError):
                        session.run_child(child_id="after-restore", operation=lambda _: {"status": "PASS"})
                    self.assertEqual("FAILED", session.state)

    def test_unrecognized_materialization_mode_cannot_override_resource_caps(self):
        session = self._session()
        with self.assertRaises(OfflineSessionError):
            OfflineExecutionSession(
                repo_root=REPO_ROOT, source=session.source,
                requirement_id=session.requirement_id,
                requirement_closure_hash=session.requirement_closure_hash,
                materialization_mode="NO_LIMITS",
            )

    def test_worker_output_cannot_self_declare_pass_without_guard_and_binding(self):
        data = (REPO_ROOT / SOURCE_PATH).read_bytes()
        asset = build_table_grid(
            html_bytes=data, parent_raw_asset_ids=["sha256:" + sha256_bytes(content=data)],
            storage_uri="offline://test",
        )
        inspected = subprocess.CompletedProcess([], 0, stdout=PINNED_IMAGE_ID + "\n", stderr="")
        forged = subprocess.CompletedProcess([], 0, stdout=canonical_json_bytes(value=asset),
                                            stderr=b'{"status":"PASSED_OFFLINE_ONLY"}')
        with patch("vnext.r4_materialization.subprocess.run", side_effect=[inspected, forged]) as run:
            with self.assertRaisesRegex(OfflineMaterializationError, "identity/guard"):
                materialize_full_source(
                    repo_root=REPO_ROOT, source_path=SOURCE_PATH,
                    source_sha256=sha256_bytes(content=data), source_size=len(data),
                )
        command = run.call_args_list[1].args[0]
        self.assertIn("--pull=never", command)
        self.assertIn("--read-only", command)
        self.assertEqual("none", command[command.index("--network") + 1])
        self.assertEqual("536870912", command[command.index("--memory") + 1])
        self.assertEqual("536870912", command[command.index("--memory-swap") + 1])
        self.assertEqual("32", command[command.index("--pids-limit") + 1])

    def test_distinct_source_group_uses_one_aggregate_disk_callback(self):
        first = self._session()
        path = "tests/fixtures/vnext/sample_lodging.html"
        data = (REPO_ROOT / path).read_bytes()
        second = OfflineExecutionSession(
            repo_root=REPO_ROOT, source=FileBinding(path, sha256_bytes(content=data), len(data)),
            requirement_id=first.requirement_id, requirement_closure_hash=first.requirement_closure_hash,
        )
        for session in (first, second):
            session.prepare()
            session.run_child(child_id="synthetic-child", operation=lambda _: {"status": "PASSED"})
        group = OfflineExecutionGroup(sessions=[first, second])
        calls = []

        def replay(root, sources, requirement_id, closure):
            calls.append(sources)
            self.assertTrue(all(type(source) is FileBinding for source in sources))
            for source in sources:
                self.assertEqual(sha256_bytes(content=(root / source.path).read_bytes()), source.sha256)
            return {"status": "PASSED", "evidence_tier": "SYNTHETIC_GROUP_INTERFACE_ONLY"}

        group.final_disk_replay(replay=replay)
        self.assertEqual(1, len(calls))
        self.assertEqual(1, group.final_independent_disk_replays)
        self.assertEqual("FINALIZED", group.state)
        self.assertEqual(["FINALIZED", "FINALIZED"], [first.state, second.state])
        with self.assertRaises(OfflineSessionError):
            group.final_disk_replay(replay=replay)
        with self.assertRaises(OfflineSessionError):
            OfflineExecutionGroup(sessions=[first, first])

    def test_prior_history_requires_six_distinct_paths(self):
        binding = FileBinding("a", "0" * 64, 0)
        with self.assertRaises(OfflineSessionError):
            OfflinePriorRunSet(repo_root=REPO_ROOT, manifests=[binding])
        with self.assertRaises(OfflineSessionError):
            OfflinePriorRunSet(repo_root=REPO_ROOT, manifests=[binding] * 6)

    def test_prior_control_byte_drift_cannot_be_restored_into_ready_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "control.json"
            path.write_bytes(b"FROZEN")
            prior = OfflinePriorRunSet(repo_root=root, manifests=[
                FileBinding(str(i), "0" * 64, 0) for i in range(6)
            ])
            prior._pin("control.json")
            prior.state = "READY"
            prior.assert_unchanged()
            path.write_bytes(b"UNKNOWN")
            with self.assertRaises(OfflineSessionError):
                prior.assert_unchanged()
            path.write_bytes(b"FROZEN")
            with self.assertRaises(OfflineSessionError):
                prior.assert_unchanged()
            self.assertEqual("FAILED", prior.state)


class R4ProductionResourcePolicyTest(unittest.TestCase):
    """Production parser ceiling: measured inputs, no runtime overrides."""

    @staticmethod
    def _expanded_cells_source(cells):
        tables = []
        while cells:
            chunk = min(cells, RESOURCE_LIMITS.max_cells_per_table)
            rows, columns = divmod(chunk, 200)
            if rows:
                tables.append('<table><tr><td rowspan="{}" colspan="200">x</td></tr></table>'.format(rows))
            if columns:
                tables.append('<table><tr><td colspan="{}">x</td></tr></table>'.format(columns))
            cells -= chunk
        return ("<html>" + "".join(tables) + "</html>").encode("utf-8")

    def test_only_total_cell_limit_changed_and_covers_measured_sources(self):
        receipt = strict_json_file(path=REPO_ROOT / "docs/r4_offline/performance_resource_measurement_initial.json")
        self.assertEqual(receipt["receipt_id"], content_hash(value={k: v for k, v in receipt.items() if k != "receipt_id"}))
        actual = asdict(RESOURCE_LIMITS)
        total = actual.pop("max_total_cells")
        self.assertEqual(actual, receipt["other_resource_limits"])
        maximum = max(max(row["raw_source_cells"], row["expanded_cells"]) for row in receipt["sources"])
        self.assertEqual(200229, maximum)
        self.assertEqual(((maximum + 9999) // 10000) * 10000, total)
        self.assertLessEqual(total, 250000)
        self.assertEqual(3, len(receipt["sources"]))

    def test_exact_cap_succeeds_and_cap_plus_one_fails(self):
        cap = RESOURCE_LIMITS.max_total_cells
        asset = build_table_grid(
            html_bytes=self._expanded_cells_source(cap),
            parent_raw_asset_ids=["sha256:" + "a" * 64], storage_uri="offline://cap-boundary",
        )
        self.assertEqual(cap, sum(t["row_count"] * t["column_count"] for t in asset["tables"]))
        with self.assertRaisesRegex(TableGridError, "resource budget exceeded"):
            build_table_grid(
                html_bytes=self._expanded_cells_source(cap + 1),
                parent_raw_asset_ids=["sha256:" + "a" * 64], storage_uri="offline://cap-plus-one",
            )

    def test_no_public_parser_or_worker_limit_override(self):
        self.assertEqual(set(inspect.signature(build_table_grid).parameters),
                         {"html_bytes", "parent_raw_asset_ids", "storage_uri"})
        self.assertEqual(set(inspect.signature(materialize_full_source).parameters),
                         {"repo_root", "source_path", "source_sha256", "source_size"})
        worker = (REPO_ROOT / "tools/r4_materialization_worker.py").read_text()
        self.assertNotIn("dataclasses.replace", worker)
        self.assertNotIn("table_grid.RESOURCE_LIMITS =", worker)
        self.assertNotIn("OFFLINE_MAX_TOTAL_CELLS", worker)


class ParsedXbrlReuseTest(unittest.TestCase):
    def test_owned_parse_reuses_native_claim_logic_without_reparsing(self):
        from tests.vnext.test_deterministic_router import fixture_sources
        from vnext.deterministic_router import adapt_accession_xbrl, adapt_accession_xbrl_from_parsed
        from vnext.deterministic_router import parse_accession_xbrl_source
        with tempfile.TemporaryDirectory() as directory:
            fixture = fixture_sources(root=Path(directory))
            args = dict(raw_bytes=fixture["bytes"]["accession"],
                        source_reference=fixture["references"]["accession"],
                        source_set_manifest=fixture["manifests"]["target_accession_instance"],
                        fact_names=["Assets"])
            expected = adapt_accession_xbrl(**args)
            with OfflineOperationObserver() as observed:
                parsed = parse_accession_xbrl_source(raw_bytes=args["raw_bytes"])
                for _ in range(2):
                    actual = adapt_accession_xbrl_from_parsed(parsed_source=parsed, **args)
                    self.assertEqual(expected, actual)
                    self.assertEqual(canonical_json_bytes(value=expected), canonical_json_bytes(value=actual))
            self.assertEqual(1, observed.counts["xbrl_context_parses"])
            self.assertEqual(1, observed.counts["xbrl_fact_parses"])
            self.assertEqual(2, observed.counts["native_xbrl_claim_evaluations"])
            with self.assertRaises(TypeError):
                parsed.contexts["FY"]["period_end"] = "2024-12-31"
            with self.assertRaises(TypeError):
                parsed.facts[0]["text"] = "999"

    def test_parsed_source_mismatch_and_forged_factory_fail(self):
        from tests.vnext.test_deterministic_router import fixture_sources
        from vnext.deterministic_router import adapt_accession_xbrl_from_parsed, parse_accession_xbrl_source
        from vnext.deterministic_router import ParsedAccessionXbrlSource, DeterministicRouterError
        with tempfile.TemporaryDirectory() as directory:
            fixture = fixture_sources(root=Path(directory)); raw = fixture["bytes"]["accession"]
            parsed = parse_accession_xbrl_source(raw_bytes=raw)
            args = dict(parsed_source=parsed, raw_bytes=raw,
                        source_reference=fixture["references"]["accession"],
                        source_set_manifest=fixture["manifests"]["target_accession_instance"], fact_names=["Assets"])
            with self.assertRaises(DeterministicRouterError):
                adapt_accession_xbrl_from_parsed(**{**args, "raw_bytes": raw + b" "})
            other = parse_accession_xbrl_source(raw_bytes=raw + b" ")
            with self.assertRaises(DeterministicRouterError):
                adapt_accession_xbrl_from_parsed(**{**args, "parsed_source": other})
            with self.assertRaises(DeterministicRouterError):
                ParsedAccessionXbrlSource(source_sha256="a" * 64, source_size=1, contexts={}, facts=[], factory=None)
            with self.assertRaises(DeterministicRouterError):
                parse_accession_xbrl_source(raw_bytes=bytearray(raw))


class OfflineBenchmarkBoundaryTest(unittest.TestCase):
    """CLI failures are boundary tests, never synthetic performance evidence."""

    def test_benchmark_output_cannot_overwrite_active_publication(self):
        target = REPO_ROOT / "outputs/active_publication.json"
        before = target.read_bytes()
        command = [sys.executable, str(REPO_ROOT / "tools/benchmark_r4_offline_session.py"),
                   "--benchmark", "--requirement-id", "issue_28_v2",
                   "--requirement-closure", "sha256:" + "0" * 64, "--output", str(target)]
        completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, timeout=10, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("must not overwrite runtime or authority paths", completed.stderr)
        self.assertEqual(before, target.read_bytes())

    def test_forged_workload_is_rejected_before_fixture_or_source_work(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            workload = temporary / "forged-workload.json"
            workload.write_text('{"workload_id":"sha256:' + "0" * 64 + '"}')
            output = temporary / "result.json"
            command = [sys.executable, str(REPO_ROOT / "tools/benchmark_r4_offline_session.py"),
                       "--worker-mode", "optimized", "--workload", str(workload), "--output", str(output)]
            completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, timeout=10, check=False)
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("Benchmark workload identity differs", completed.stderr)
            self.assertNotIn("preparing_source", completed.stdout)
            self.assertFalse(output.exists())


class RecordedOfflineBenchmarkTest(unittest.TestCase):
    """Check recorded measurement integrity, not rerun or manufacture timings."""

    def test_complete_recorded_gate_and_current_inputs_remain_bound(self):
        receipt = strict_json_file(path=REPO_ROOT / "docs/r4_offline/performance_session_benchmark.json")
        self.assertEqual(receipt["benchmark_receipt_id"],
            content_hash(value={k: v for k, v in receipt.items() if k != "benchmark_receipt_id"}))
        self.assertEqual("PASSED", receipt["status"])
        self.assertEqual(1, receipt["final_independent_disk_replay_executions"])
        self.assertEqual([0, 0, 0], receipt["provider_paid_sec_calls"])
        reports = receipt["reports"]
        self.assertEqual({"baseline", "optimized", "independent-replay"}, set(reports))
        self.assertEqual(3, len({r["worker_pid"] for r in reports.values()}))
        self.assertEqual(1, len({content_hash(value=r["interpreter"]) for r in reports.values()}))
        self.assertEqual(reports["baseline"]["results"], reports["optimized"]["results"])
        self.assertEqual(reports["baseline"]["results"], reports["independent-replay"]["results"])
        for report in reports.values():
            self.assertEqual(16, len(report["results"]))
            self.assertEqual("PASSED", report["status"])
            self.assertEqual([0, 0, 0], report["provider_paid_sec_calls"])
            self.assertEqual(content_hash(value=report["results"]), report["semantic_result_set_id"])
        final = Decimal(reports["independent-replay"]["process_wall_seconds"])
        baseline = Decimal(reports["baseline"]["process_wall_seconds"]) + final
        optimized = Decimal(reports["optimized"]["process_wall_seconds"]) + final
        self.assertEqual(baseline, Decimal(receipt["baseline_aggregate_seconds"]))
        self.assertEqual(optimized, Decimal(receipt["optimized_aggregate_seconds"]))
        self.assertEqual(baseline / optimized, Decimal(receipt["aggregate_improvement_factor"]))
        self.assertGreaterEqual(baseline / optimized, 10)
        self.assertEqual(96, reports["baseline"]["operation_counts"]["portable_prior_run_loads"])
        for mode in ("optimized", "independent-replay"):
            report = reports[mode]
            self.assertEqual(6, report["operation_counts"]["portable_prior_run_loads"])
            self.assertEqual(4, len(report["source_sessions"]))
            for session in report["source_sessions"]:
                for key in ("source_materializations", "derived_asset_builds", "derived_asset_json_decodes",
                            "requirement_builds", "revision_requirement_builds", "parent_authority_builds"):
                    self.assertEqual(1, session["preparation_counts"][key])
                for child in session["children"]:
                    for key in ("source_materializations", "derived_asset_builds", "derived_asset_json_decodes",
                                "requirement_builds", "revision_requirement_builds", "parent_authority_builds",
                                "portable_prior_run_loads", "xbrl_fact_parses", "xbrl_context_parses",
                                "provider_calls", "paid_model_calls", "sec_calls"):
                        self.assertEqual(0, child["operation_counts"][key], (mode, child["fixture_id"], key))
        self.assertEqual(reports["optimized"]["operation_counts"], reports["independent-replay"]["operation_counts"])
        for binding in receipt["workload"]["input_bindings"]:
            data = resolve_repository_file(repo_root=REPO_ROOT, repo_relative_path=binding["path"]).read_bytes()
            self.assertEqual(binding["size"], len(data), binding["path"])
            self.assertEqual(binding["sha256"], sha256_bytes(content=data), binding["path"])

    def test_streamed_progress_contains_the_exact_measured_case_set_and_times(self):
        receipt = strict_json_file(path=REPO_ROOT / "docs/r4_offline/performance_session_benchmark.json")
        path = REPO_ROOT / "docs/r4_offline/performance_session_benchmark.stdout.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        expected_ids = {r["fixture_id"] for r in receipt["workload"]["cases"]}
        for mode, report in receipt["reports"].items():
            completed = [row for row in rows if row.get("mode") == mode and "completed_fixture" in row]
            self.assertEqual(16, len(completed))
            self.assertEqual(expected_ids, {row["completed_fixture"] for row in completed})
            recorded = report["baseline_children"] if mode == "baseline" else [
                child for session in report["source_sessions"] for child in session["children"]]
            expected_times = {child["fixture_id"]: child["wall_seconds"] for child in recorded}
            self.assertEqual(expected_times,
                {row["completed_fixture"]: row["fixture_wall_seconds"] for row in completed})
        self.assertEqual(receipt["aggregate_improvement_factor"], rows[-1]["factor"])
        self.assertEqual(receipt["status"], rows[-1]["status"])
