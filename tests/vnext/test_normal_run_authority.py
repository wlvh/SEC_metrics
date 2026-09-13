"""Every ordinary successor Run enters its own source and Spec admission."""
import unittest
import json
from pathlib import Path
import shutil
import tempfile

from tests.vnext.common import REPO_ROOT
from vnext.normal_run_v2 import validate_normal_run_authority
from vnext.run_store import _validate_record_graph
from vnext.specs import compile_spec_file
from vnext.requirements import load_requirement_snapshot


class NormalRunAuthorityTest(unittest.TestCase):
    def test_imported_snapshot_cannot_remove_execution_authority(self):
        with tempfile.TemporaryDirectory(prefix="normal-current-authority-") as tmp:
            path = Path(tmp) / "requirements/issue_28_v12"
            shutil.copytree(REPO_ROOT / "requirements/issue_28_v12", path)
            baseline_path = path / "baseline_manifest.json"
            baseline = json.loads(baseline_path.read_text())
            baseline["execution_authority"]["files"] = {}
            baseline_path.write_text(json.dumps(baseline))
            with self.assertRaisesRegex(ValueError, "installed snapshot differs"):
                load_requirement_snapshot(snapshot_dir=path)

    def test_empty_and_multiple_spec_sets_are_rejected_before_record_dispatch(self):
        manifest = {"requirement_id": "issue_28_v12"}
        for specs in ({}, {"A03": {}, "A04": {}}):
            with self.subTest(specs=list(specs)), self.assertRaisesRegex(ValueError, "ONE_SPEC_REQUIRED"):
                _validate_record_graph(repo_root=REPO_ROOT, run_dir=REPO_ROOT,
                    manifest=manifest, records=[], effective_decisions={}, compiled_specs=specs,
                    raw_bytes_by_id={}, company_ciks=[], requirement={})

    def test_old_table_spec_cannot_select_a_path_without_ordinary_source_replay(self):
        path = "catalog/metrics/A03_liquidity_coverage_ratio.md"
        spec = compile_spec_file(path=REPO_ROOT / path, dependency_specs={})
        self.assertEqual("ai_table", spec["compiled"]["source_mode"])
        manifest = {"requirement_id": "issue_28_v12", "run_id": "run:normal-current:" + "0" * 64,
                    "spec_file_hashes": {path: "0" * 64}}
        with self.assertRaisesRegex(ValueError, "SPEC_ROUTE_NOT_ENABLED"):
            _validate_record_graph(repo_root=REPO_ROOT, run_dir=REPO_ROOT,
                manifest=manifest, records=[], effective_decisions={}, compiled_specs={"A03": spec},
                raw_bytes_by_id={}, company_ciks=[], requirement={})

    def test_an_installed_metric_from_outside_this_policy_is_rejected(self):
        path = "catalog/metrics/B01_revenue.md"
        spec = compile_spec_file(path=REPO_ROOT / path, dependency_specs={})
        manifest = {"requirement_id": "issue_28_v12", "run_id": "run:normal-current:" + "0" * 64,
                    "spec_file_hashes": {path: "0" * 64}}
        with self.assertRaisesRegex(ValueError, "SPEC_ROUTE_NOT_ENABLED"):
            validate_normal_run_authority(repo_root=REPO_ROOT, manifest=manifest,
                records=[], compiled_specs={"B01": spec})


if __name__ == "__main__":
    unittest.main()
