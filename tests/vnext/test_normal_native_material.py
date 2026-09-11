"""Actual normal-candidate freeze and fresh-process replay from saved originals.

Run explicitly with NORMAL_NATIVE_MATERIAL_ROOT pointing to a new external
directory. This material suite is not a mock or a default fast-suite entry.
Failures retain their stage, files and traceback for investigation.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import traceback
import unittest
from unittest.mock import patch
import socket

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree(root):
    return {p.relative_to(root).as_posix(): _hash(p)
            for p in sorted(root.rglob("*")) if p.is_file()}


def _save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _protected():
    paths = ["outputs/active_publication.json", "outputs/validation_run_manifest.json",
             "outputs/metrics_matrix.csv", "outputs/metric_evidence.csv",
             "REPORT_十公司财务指标.md", "evidence/requests_log.csv",
             "evidence/requests_log_manifest.json"]
    return {p: _hash(REPO_ROOT / p) for p in paths}


def _fingerprint(data_root, run_dir, manifest, records, decisions):
    from vnext.canonical import content_hash
    result = next(r for r in records if r["record_type"] == "METRIC_RESULT")
    raw = {r["raw_asset_id"]: r for r in records if r["record_type"] == "RAW_BLOB"}
    sources = [{"source_reference": reference,
                "storage_uri": raw[reference["raw_asset_id"]]["storage_uri"],
                "body_sha256": _hash(data_root / raw[reference["raw_asset_id"]]["storage_uri"])}
               for reference in manifest["source_references"]]
    return {"run_id": manifest["run_id"], "target_period": manifest["target_period"],
            "requirement_closure_hash": manifest["requirement_closure_hash"],
            "result": result, "sources": sources, "review_decisions": decisions,
            "record_graph_hash": content_hash(value=records),
            "records_file_sha256": _hash(run_dir / "records.jsonl"),
            "review_decisions_file_sha256": _hash(run_dir / "review_decisions.jsonl"),
            "review_assets": _tree(run_dir / "review") if (run_dir / "review").exists() else {},
            "source_data_tree": _tree(data_root)}


def _cold_main(arguments):
    data_root, run_dir, expected_path, output_path = map(Path, arguments)
    blocked = []

    def audit(event, args):
        if event.startswith("socket.") or event in {"subprocess.Popen", "os.system"}:
            blocked.append(event)
            raise RuntimeError("Cold material replay forbids network and child processes: " + event)

    sys.addaudithook(audit)
    try:
        from vnext.run_store import load_frozen_run
        manifest, records, decisions = load_frozen_run(run_dir=run_dir, repo_root=data_root)
        actual = _fingerprint(data_root, run_dir, manifest, records, decisions)
        expected = json.loads(expected_path.read_text())
        assert actual == expected, "Cold source/result/period/review fingerprint changed"
        assert manifest["status"] == "FROZEN"
        validation = json.loads((run_dir / "validation.json").read_text())
        assert validation["status"] == "PASSED"
        assert not list(data_root.rglob(".git")) and not list(run_dir.rglob(".git"))
        _save(output_path, {"status": "PASS_FROZEN_COLD_REPLAY", "pid": os.getpid(),
            "cwd": str(Path.cwd()), "data_root_has_git": False, "run_root_has_git": False,
            "child_processes_and_network_forbidden": True, "blocked_events": blocked,
            "manifest": manifest, "fingerprint": actual})
        print(json.dumps({"status": "PASS_FROZEN_COLD_REPLAY", "pid": os.getpid(),
                          "run_id": manifest["run_id"], "metric_id": actual["result"]["metric_id"]}))
        return 0
    except Exception as error:
        _save(output_path, {"status": "FAILED_COLD_REPLAY", "pid": os.getpid(),
            "blocked_events": blocked, "error": type(error).__name__ + ": " + str(error),
            "traceback": traceback.format_exc()})
        traceback.print_exc()
        return 1


class NormalNativeMaterialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        destination = os.environ.get("NORMAL_NATIVE_MATERIAL_ROOT")
        if not destination:
            raise RuntimeError("NORMAL_NATIVE_MATERIAL_ROOT must name a new external directory")
        cls.output = Path(destination).resolve()
        if cls.output == REPO_ROOT or REPO_ROOT in cls.output.parents:
            raise RuntimeError("Material outputs must be outside the repository")
        cls.output.mkdir(parents=True, exist_ok=False)
        cls.commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
        _save(cls.output / "execution.json", {"commit": cls.commit, "python": sys.executable,
            "parent_pid": os.getpid(), "argv": getattr(sys, "orig_argv", sys.argv),
            "output": str(cls.output), "source_policy": "SAVED_ORIGINALS_ONLY", "new_calls": [0, 0, 0]})

    def _case(self, name, company_id, metric_id):
        from vnext.normal_candidates import install_saved_candidate_inputs
        from vnext.normal_candidates import create_risk_heading_run, create_structured_candidate_run
        from vnext.run_store import load_open_run, validate_and_freeze_run
        root = self.output / name; root.mkdir()
        data_root, run_dir = root / "data", root / "run"
        protected = _protected()
        report = {"case": name, "company_id": company_id, "metric_id": metric_id,
                  "commit": self.commit, "status": "RUNNING", "stage": "INSTALL",
                  "new_calls": [0, 0, 0], "parent_pid": os.getpid()}
        try:
            with patch.object(socket.socket, "connect", side_effect=AssertionError("Material test forbids network")):
                installed = install_saved_candidate_inputs(data_root=data_root, company_id=company_id,
                                                           governance=metric_id == "C03")
                _save(root / "installed-input.json", installed)
                report["stage"] = "CREATE_OPEN_NATIVE_RUN"; _save(root / "outcome.json", report)
                if metric_id == "D01":
                    created = create_risk_heading_run(data_root=data_root, run_dir=run_dir, company_id=company_id, freeze=False)
                else:
                    created = create_structured_candidate_run(data_root=data_root, run_dir=run_dir,
                        company_id=company_id, metric_id=metric_id, freeze=False)
                manifest, records, decisions = load_open_run(run_dir=run_dir)
                self.assertEqual("OPEN", manifest["status"])
                self.assertFalse(any(r["record_type"] == "AI_EXTRACTION_ATTEMPT" for r in records))
                before = _fingerprint(data_root, run_dir, manifest, records, decisions)
                _save(root / "before-freeze.json", before)
                self.assertEqual("EXACT", before["result"]["quality"])
                self.assertEqual("PUBLISHED", before["result"]["publication"])
                if metric_id == "D01":
                    self.assertEqual("TEXT_V1", before["result"]["value_kind"])
                    self.assertEqual(34, len(before["result"]["text_payload"]["items"]))
                    self.assertEqual(["SYSTEM"], [d["reviewer_type"] for d in decisions])
                    self.assertEqual(("2025-01-01", "2025-12-31"),
                        (manifest["target_period"]["period_start"], manifest["target_period"]["period_end"]))
                else:
                    self.assertEqual(("63211569", "USD"), (before["result"]["value"], before["result"]["unit"]))
                    self.assertEqual([], decisions)
                    self.assertTrue(any(r["record_type"] == "DERIVED_ASSET" for r in records))
                    self.assertEqual(("2025-08-07", "2025-12-31"),
                        (manifest["target_period"]["period_start"], manifest["target_period"]["period_end"]))
                report["stage"] = "VALIDATE_AND_FREEZE"; _save(root / "outcome.json", report)
                frozen = validate_and_freeze_run(run_dir=run_dir, repo_root=data_root)
                self.assertEqual("FROZEN", frozen["status"])
                self.assertEqual("PASSED", json.loads((run_dir / "validation.json").read_text())["status"])
                self.assertEqual(before["source_data_tree"], _tree(data_root))
                _save(root / "frozen-manifest.json", frozen)
            report["stage"] = "FRESH_PROCESS_LOAD_FROZEN"; _save(root / "outcome.json", report)
            command = [sys.executable, str(Path(__file__).resolve()), "--cold-read", str(data_root),
                       str(run_dir), str(root / "before-freeze.json"), str(root / "cold-read.json")]
            environment = dict(os.environ)
            environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(REPO_ROOT / "scripts"))
            report["cold_command"] = shlex.join(command)
            report["cold_cwd"] = str(root)
            _save(root / "outcome.json", report)
            completed = subprocess.run(command, cwd=root, env=environment, text=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
            (root / "cold-process.log").write_text(completed.stdout)
            report["cold_returncode"] = completed.returncode
            self.assertEqual(0, completed.returncode, completed.stdout)
            cold = json.loads((root / "cold-read.json").read_text())
            self.assertNotEqual(os.getpid(), cold["pid"])
            self.assertEqual(before, cold["fingerprint"])
            self.assertEqual(protected, _protected())
            report.update(status="PASSED_FROZEN_AND_COLD_READ", stage="COMPLETE",
                cold_pid=cold["pid"], run_id=frozen["run_id"], validation_status="PASSED",
                source_references=len(before["sources"]), record_graph_hash=before["record_graph_hash"],
                target_period=before["target_period"], review_count=len(decisions),
                protected_state_unchanged=True, data_root_has_git=False)
        except Exception as error:
            report.update(status="FAILED", error=type(error).__name__ + ": " + str(error), traceback=traceback.format_exc())
            if (run_dir / "manifest.json").exists():
                report["retained_manifest_status"] = json.loads((run_dir / "manifest.json").read_text())["status"]
            report["protected_state_unchanged"] = protected == _protected()
            raise
        finally:
            _save(root / "outcome.json", report)

    def test_01_marriott_d01_real_freeze_and_fresh_process_read(self):
        self._case("marriott_d01", "marriott_international", "D01")

    def test_02_paramount_c03_real_freeze_and_fresh_process_read(self):
        self._case("paramount_c03", "paramount_skydance_paramount_global", "C03")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cold-read":
        raise SystemExit(_cold_main(sys.argv[2:]))
    unittest.main()
