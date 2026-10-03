"""Explicit ordinary V13 OPEN material test; never part of the fast suite.

Run with NORMAL_RUN_MATERIAL_ROOT naming a fresh absolute external directory:
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts NORMAL_RUN_MATERIAL_ROOT=/tmp/new-dir \
    python3 -m unittest -v tests.vnext.test_normal_run_material

The installed Requirement closure is discovered at execution time. Real saved
sources create JPM A04 and Marriott D01 OPEN graphs; independent file copies
exercise the shared Spec/source/period gate. All first failures and materials
are retained. No provider, SEC acquisition, freeze or production write occurs.
"""
from contextlib import ExitStack
from datetime import date, timedelta
import copy
import os
from pathlib import Path
import shutil
import sys
import time
import traceback
import unittest
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vnext import normal_run_v2 as normal
from vnext import run_store
from vnext.calculator import calculate_metric
from vnext.canonical import canonical_json_bytes, content_hash, sha256_file, strict_json_file
from vnext.requirements import load_requirement_snapshot
from vnext.specs import compile_spec_file
from vnext.traits import repository_company_traits


def _save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value=value))


def _fresh_output(value):
    path = Path(value)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("NORMAL_RUN_MATERIAL_ROOT must be a fresh absolute external directory")
    path = path.resolve()
    if path == REPO_ROOT or REPO_ROOT in path.parents:
        raise ValueError("Normal Run material must be outside the source checkout")
    if path.exists() or any((p / "outputs/active_publication.json").exists()
                            for p in [path, *path.parents]):
        raise ValueError("Normal Run material cannot reuse an existing or publication directory")
    path.mkdir(parents=True, exist_ok=False)
    return path


def _protected():
    paths = ("outputs/active_publication.json", "outputs/validation_run_manifest.json",
             "outputs/metrics_matrix.csv", "outputs/metric_evidence.csv",
             "REPORT_十公司财务指标.md", "evidence/requests_log.csv",
             "evidence/requests_log_manifest.json")
    return {p: sha256_file(path=REPO_ROOT / p) if (REPO_ROOT / p).is_file() else None for p in paths}


class NormalRunMaterialTest(unittest.TestCase):
    """One opt-in batch shares expensive genuine baselines across file probes."""

    def _first_failure(self, row):
        path = self.output / "first-failure.json"
        if not path.exists():
            with path.open("xb") as handle:
                handle.write(canonical_json_bytes(value=row))

    def _index(self):
        _save(self.output / "index.json", {"requirement_id": normal.REQUIREMENT_ID,
            "requirement_closure": self.requirement["requirement_closure_hash"],
            "cases": self.cases, "new_calls": {"provider": 0, "paid": 0, "sec": 0},
            "freeze_attempts": self.freeze_attempts, "network_attempts": self.network_attempts})

    def _record_case(self, name, action, expected_errors=()):
        self.stage = "PREPARE"
        row = {"case": name, "expected": "REJECT" if expected_errors else "PASS"}
        started = time.monotonic()
        try:
            self.assertEqual(self.identity, self._hash_identity(), "Installed code changed during material batch")
            row["details"] = action()
            row.update(outcome="ACCEPTED", passed=not expected_errors)
        except Exception as error:
            # A setup/assertion/JSONL bug is not evidence of semantic rejection.
            recognized = isinstance(error, (ValueError, run_store.RunStoreError))
            expected = (bool(expected_errors) and self.stage == "REPLAY" and recognized
                        and any(message in str(error) for message in expected_errors))
            row.update(outcome="REJECTED", passed=expected, stage=self.stage,
                       error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
        row["seconds"] = "{:.3f}".format(time.monotonic() - started)
        self.cases.append(row)
        _save(self.output / "outcomes" / (name + ".json"), row)
        if not row["passed"]:
            self._first_failure(row)
        self._index()
        print("{}: {} (expected met: {})".format(name, row["outcome"], row["passed"]), flush=True)
        return row["passed"]

    def _hash_identity(self):
        return {relative: sha256_file(path=REPO_ROOT / relative) for relative in self.identity_paths}

    def _replay(self, data, run):
        self.stage = "REPLAY"
        manifest, records, decisions = run_store._mechanically_replay_open_run(
            repo_root=data, run_dir=run, require_complete_results=True)
        self.assertEqual("OPEN", manifest["status"])
        self.assertEqual("OPEN", strict_json_file(path=run / "manifest.json")["status"])
        return manifest, records, decisions

    def _baseline(self, company, metric):
        case_root = self.output / "baselines" / (company + "-" + metric)
        data, run = case_root / "data", case_root / "run"
        self.stage = "INSTALL"
        installed = normal.install_normal_inputs(data_root=data, company_id=company, metric_id=metric)
        _save(case_root / "installed-input-binding.json", installed["input_binding"])
        self.stage = "CREATE_OPEN_RUN"
        created = normal.create_normal_run(data_root=data, run_dir=run, company_id=company,
                                          metric_id=metric, freeze=False)
        self.run_paths.append(run)
        self.assertEqual("OPEN", created["manifest"]["status"])
        manifest, records, decisions = self._replay(data, run)
        results = [r for r in records if r["record_type"] == "METRIC_RESULT"]
        self.assertEqual(1, len(results))
        result = results[0]
        self.assertEqual(("EXACT", "PUBLISHED"), (result["quality"], result["publication"]))
        self.assertEqual(("2025-01-01", "2025-12-31"),
                         (result["period_start"], result["period_end"]))
        self.assertEqual(3, len(manifest["source_references"]))
        self.assertFalse(any(r["record_type"] in {"AI_EXTRACTION_ATTEMPT", "R4_SCOPED_EXTRACTION_ATTEMPT"}
                             for r in records))
        if metric == "A04":
            self.assertEqual("0.025", result["value"])
            self.assertEqual([], decisions)
        else:
            self.assertEqual("TEXT_V1", result["value_kind"])
            self.assertEqual(34, len(result["text_payload"]["items"]))
            self.assertEqual(4774, len(result["value"]))
            self.assertEqual(["SYSTEM"], [d["reviewer_type"] for d in decisions])
        self.baselines[metric] = (data, run)
        _save(case_root / "positive-result.json", result)
        return {"run_id": manifest["run_id"], "result_id": result["result_id"],
            "status": manifest["status"], "spec_file_hashes": manifest["spec_file_hashes"],
            "target_period": manifest["target_period"], "source_count": len(manifest["source_references"]),
            "review_count": len(decisions), "result_quality": result["quality"]}

    def _mutate_run(self, metric, name, change):
        data, original = self.baselines[metric]
        run = self.output / "attacks" / (metric + "-" + name) / "run"
        run.parent.mkdir(parents=True)
        shutil.copytree(original, run)
        self.run_paths.append(run)
        manifest = strict_json_file(path=run / "manifest.json")
        change(manifest, data, run)
        _save(run / "manifest.json", manifest)
        loaded, _, _ = self._replay(data, run)
        return {"unexpected_run_id": loaded["run_id"]}

    @staticmethod
    def _remove_reference_record(manifest, data, run):
        # canonical_json_bytes already ends with a newline; add exactly one.
        from vnext.canonical import strict_json_loads
        records = [strict_json_loads(text=line) for line in (run / "records.jsonl").read_text().splitlines()]
        removed = next(r for r in records if r["record_type"] == "SOURCE_REFERENCE")
        records.remove(removed)
        (run / "records.jsonl").write_bytes(b"".join(
            canonical_json_bytes(value=r).rstrip(b"\n") + b"\n" for r in records))
        _save(run.parent / "removed-reference-record.json", removed)

    def _old_ai_spec_graph(self):
        original_data, _ = self.baselines["D01"]
        case_root = self.output / "attacks" / "old-ai-spec-structural"
        data, run = case_root / "data", case_root / "run"
        shutil.copytree(original_data, data)
        case = normal._prepare_case(data_root=data, company_id="marriott_international", metric_id="A03")
        old_path = "catalog/r4_v2/A03_liquidity_coverage_ratio.md"
        self.assertTrue((data / old_path).is_file(), "Imported authority lacks the historical attack Spec")
        old_spec = compile_spec_file(path=data / old_path, dependency_specs={})
        self.assertEqual("ai_table", old_spec["compiled"]["source_mode"])
        self.assertNotIn(old_path, self.policy["metric_spec_paths"]["A03"])
        forged = copy.deepcopy(case)
        forged.update(compiled_spec=old_spec, spec_path=old_path)
        forged["input_binding"].update(spec_path=old_path,
            spec_closure_hash=old_spec["spec_closure_hash"], spec_file_sha256=sha256_file(path=data / old_path))
        forged["input_binding"]["input_binding_id"] = content_hash(value={k: v for k, v in
            forged["input_binding"].items() if k != "input_binding_id"})
        binding = normal._binding(forged, self.requirement)
        key = content_hash(value=binding)[7:]
        _save(data / "normal_current_bindings" / (key + ".json"), binding)
        prepared = case["input_binding"]["prepared_input"]
        scope = dict(old_spec["compiled"]["required_claims"])
        period = case["target_period"]
        target = {"company_id": "marriott_international", "entity": prepared["entity"],
            "accession": prepared["filing"]["accessionNumber"],
            "period_start": period["period_start"], "period_end": period["period_end"],
            "scope": scope, "scope_key": content_hash(value=scope)}
        traits = repository_company_traits(repo_root=data, company_id="marriott_international")
        result, trace, observations = calculate_metric(compiled_spec=old_spec, target=target,
            company_traits=traits, structured_facts=[], verified_observations=[])
        self.assertEqual(("N_A_STRUCTURAL", "PUBLISHED"), (result["applicability"], result["publication"]))
        self.assertEqual([], observations)
        run_store.create_run(run_dir=run, run_id=normal.PREFIX + key,
            company_id="marriott_international", company_traits=traits,
            target_period=period, source_references=case["references"], missing_required_source_roles=[],
            spec_file_hashes={old_path: sha256_file(path=data / old_path)},
            requirement_hashes=self.requirement["hashes"], requirement_id=normal.REQUIREMENT_ID,
            requirement_closure_hash=self.requirement["requirement_closure_hash"],
            artifact_requirement_generation="EXPLICIT_REQUIREMENT_V1")
        self.run_paths.append(run)
        for record in [*case["records"], trace, result]:
            run_store.append_run_record(run_dir=run, record=record)
        _save(case_root / "forged-input-description.json", {"old_spec": old_path,
            "source_mode": "ai_table", "binding": binding, "result": result, "trace": trace,
            "note": "Self-consistent old-Spec N_A graph with genuine sources, no stale-result shortcut"})
        loaded, _, _ = self._replay(data, run)
        return {"unexpected_run_id": loaded["run_id"]}

    def test_current_open_graphs_and_shared_authority_boundaries(self):
        destination = os.environ.get("NORMAL_RUN_MATERIAL_ROOT")
        if not destination:
            raise RuntimeError("NORMAL_RUN_MATERIAL_ROOT must name a fresh external directory")
        self.output = _fresh_output(destination)
        self.cases, self.baselines, self.run_paths = [], {}, []
        self.freeze_attempts, self.network_attempts = [], []
        protected = _protected()
        active = [True]

        def audit(event, arguments):
            if active[0] and event.startswith("socket."):
                self.network_attempts.append(event)
                raise AssertionError("Normal Run material forbids network: " + event)

        def no_freeze(*args, **kwargs):
            self.freeze_attempts.append("validate_and_freeze_run")
            raise AssertionError("Normal Run material must remain OPEN")

        sys.addaudithook(audit)
        old_bytecode = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            with ExitStack() as stack:
                stack.enter_context(patch.object(normal, "validate_and_freeze_run", no_freeze))
                stack.enter_context(patch.object(run_store, "validate_and_freeze_run", no_freeze))
                self.requirement = load_requirement_snapshot(
                    snapshot_dir=REPO_ROOT / "requirements" / normal.REQUIREMENT_ID)
                self.assertEqual("PROFILE_DRIVEN_V13", self.requirement["requirement_generation"])
                self.policy = strict_json_file(path=REPO_ROOT / normal.POLICY_PATH)
                paths = set(self.requirement["execution_authority"]["files"]) | set(self.policy["rule_paths"])
                paths.update({"scripts/vnext/run_store.py", "scripts/vnext/normal_run_v2.py",
                              "scripts/vnext/requirement_profile_v13.py"})
                paths.update(str(p.relative_to(REPO_ROOT)) for p in
                    (REPO_ROOT / "requirements" / normal.REQUIREMENT_ID).iterdir() if p.is_file())
                self.identity_paths = sorted(paths)
                self.identity = self._hash_identity()
                _save(self.output / "execution.json", {"requirement_id": normal.REQUIREMENT_ID,
                    "requirement_closure": self.requirement["requirement_closure_hash"],
                    "python": sys.executable, "pid": os.getpid(),
                    "argv": getattr(sys, "orig_argv", sys.argv), "output": str(self.output),
                    "file_hashes": self.identity, "protected_before": protected,
                    "source_policy": "PREEXISTING_SAVED_ACQUISITIONS_ONLY", "new_calls": [0, 0, 0]})
                for company, metric in (("jpmorgan_chase", "A04"), ("marriott_international", "D01")):
                    self._record_case("valid-" + metric,
                        lambda company=company, metric=metric: self._baseline(company, metric))
                extra_paths = self.policy["metric_spec_paths"]["A11"]
                self.assertEqual(1, len(extra_paths))
                extra = extra_paths[0]
                for metric in ("A04", "D01"):
                    if metric not in self.baselines:
                        continue  # Its failed baseline is retained; the batch cannot pass.
                    changes = (
                        ("missing-spec", lambda m, d, r: m.update(spec_file_hashes={}),
                         ("NORMAL_CURRENT_RUN_ONE_SPEC_REQUIRED", "ReviewUnit Spec is absent from repository")),
                        ("extra-spec", lambda m, d, r: m["spec_file_hashes"].update({extra: sha256_file(path=d / extra)}),
                         ("NORMAL_CURRENT_RUN_ONE_SPEC_REQUIRED",)),
                        ("missing-manifest-source", lambda m, d, r: m.update(source_references=m["source_references"][1:]),
                         ("NORMAL_CURRENT_SOURCE_SPEC_OR_TARGET_CHANGED",)),
                        ("missing-source-reference-record", self._remove_reference_record,
                         ("NORMAL_CURRENT_SOURCE_RECORD_SET_CHANGED",)),
                        ("changed-period", lambda m, d, r: m.update(target_period={**m["target_period"],
                            "period_start": (date.fromisoformat(m["target_period"]["period_start"]) + timedelta(days=1)).isoformat()}),
                         ("NORMAL_CURRENT_SOURCE_SPEC_OR_TARGET_CHANGED",)),
                    )
                    for name, change, errors in changes:
                        self._record_case(metric + "-" + name,
                            lambda metric=metric, name=name, change=change: self._mutate_run(metric, name, change), errors)
                if "D01" in self.baselines:
                    self._record_case("old-ai-spec-structural-graph", self._old_ai_spec_graph,
                                      ("NORMAL_CURRENT_SPEC_ROUTE_NOT_ENABLED",))
                self.assertEqual(13, len(self.cases), "A required baseline or attack was not executed")
                self.assertEqual(self.identity, self._hash_identity(), "Installed code changed during material batch")
                self.assertEqual(protected, _protected(), "Formal state or original request ledger changed")
                for run in self.run_paths:
                    self.assertEqual("OPEN", strict_json_file(path=run / "manifest.json")["status"])
                self.assertEqual([], self.freeze_attempts)
                self.assertEqual([], self.network_attempts)
                self.assertTrue(all(r["passed"] for r in self.cases), "See retained outcomes and first-failure.json")
                _save(self.output / "summary.json", {"status": "PASSED_OPEN_RUN_MATERIAL",
                    "requirement_closure": self.requirement["requirement_closure_hash"],
                    "case_count": 13, "valid_open_graphs": 2, "rejected_file_scenarios": 11,
                    "code_unchanged": True, "protected_state_unchanged": True,
                    "new_frozen_runs": 0, "new_calls": [0, 0, 0]})
        except Exception as error:
            failure = {"status": "FAILED_MATERIAL_BATCH", "error_type": type(error).__name__,
                       "error": str(error), "traceback": traceback.format_exc(),
                       "protected_state_unchanged": protected == _protected(),
                       "freeze_attempts": self.freeze_attempts, "network_attempts": self.network_attempts}
            self._first_failure(failure)
            _save(self.output / "batch-failure.json", failure)
            raise
        finally:
            active[0] = False
            sys.dont_write_bytecode = old_bytecode


if __name__ == "__main__":
    unittest.main()
