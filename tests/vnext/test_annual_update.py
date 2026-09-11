"""Saved-source integration; all new observations are SIMULATED_HTTP_BOUNDARY.

No test mutates repository source evidence. Cropped/altered submissions are
synthetic behavior fixtures, never claimed as real historical list snapshots.
"""
import copy
import io
import json
import shutil
import socket
import subprocess
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

import sec_http
from vnext import annual_input, annual_update as update
from vnext.canonical import sha256_bytes

ROOT = Path(__file__).resolve().parents[2]
CYCLE = ROOT / "artifacts/vnext/qualification/cycles/0c4569437b1bac3ad353394c8d8b1f59b1a1ee7c229c8fa5ee51a22269b6a448/runs"
OLD_RUN = CYCLE / "6f40df80eb602219bc9137a946c4da81ae215f413bc157d712a0289a4871161d"
NEW_RUN = CYCLE / "0799ec7f91b6bc0472fd80c6c655beb90ddd7db583dcd13cae0bfab506e6412c"


class Response(io.BytesIO):
    def __init__(self, raw, status=200):
        super().__init__(raw)
        self.status = status
        self.headers = {"Content-Type": "application/json", "X-Test-Evidence": "SIMULATED_HTTP_BOUNDARY"}


class AnnualUpdateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(socket.socket, "connect", side_effect=AssertionError("real network forbidden")):
            cls.company = update.supported_company(repo_root=ROOT)
            cls.old = update.candidate_baseline(company=cls.company, run_dir=OLD_RUN)
            cls.new = update.candidate_baseline(company=cls.company, run_dir=NEW_RUN)
            cls.prepared = annual_input.prepare_annual_input(repo_root=ROOT, company_id=cls.company["company_id"])
            cls.sources = {}
            for source in cls.prepared["source_proofs"]:
                cls.sources[source["source_url"]] = (ROOT / source["request_repo_relative_path"]).read_bytes()
            cls.inventory_url, cls.primary_url, cls.facts_url = [s["source_url"] for s in cls.prepared["source_proofs"]]
            cls.inventory = json.loads(cls.sources[cls.inventory_url])

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(socket.socket, "connect", side_effect=AssertionError("real network forbidden")))
        self.stack.enter_context(patch.dict("os.environ", {"SEC_CONTACT_EMAIL": "annual-update-tests@secmetrics.org"}))
        for relative in ("config/sec_config.json", "config/company_registry.csv", "docs/evidence/issue_28_annual_candidate_policy.json"):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        self.client = sec_http.SecHttpClient(workdir=self.root, config_path=self.root / "config/sec_config.json",
                                             log_path=self.root / "evidence/requests_log.csv")
        self.client.config = {**self.client.config, "max_retries": 0}
        self.n = 0

    def save(self, url, raw=None, status=200):
        self.n += 1
        with patch.object(sec_http, "urlopen", side_effect=lambda **_: Response(self.sources[url] if raw is None else raw, status)):
            return self.client.fetch(url=url, purpose="SIMULATED_HTTP_BOUNDARY",
                local_path=self.root / "evidence/test_observations" / str(self.n) / url.rsplit("/", 1)[1])

    def seed(self, *, primary=True, facts=True):
        self.save(self.inventory_url)
        if primary:
            self.save(self.primary_url)
        if facts:
            self.save(self.facts_url)

    def inspect(self, baseline=None):
        return update.inspect_annual_update(repo_root=self.root, company=self.company,
                                            successful_candidate=baseline or self.old)

    def mutated_inventory(self, mutate):
        payload = copy.deepcopy(self.inventory)
        mutate(payload)
        return json.dumps(payload).encode()

    def test_real_saved_old_to_new_prepares_existing_inputs(self):
        self.seed()
        result = self.inspect()
        self.assertEqual("INPUT_READY", result["status"], result)
        self.assertEqual("NEW_ANNUAL_FILING", result["filing_change"])
        self.assertEqual("PRIMARY_DEI_AND_CONTEXT", result["discovered_filing"]["period_basis"])
        self.assertEqual(self.new["filing"]["accession"], result["prepared_input"]["table_input"]["accession"])
        self.assertEqual(self.prepared["table_input"]["target_period"], result["prepared_input"]["table_input"]["target_period"])
        self.assertEqual("NOT_EXECUTED", result["execution"])
        self.assertEqual(self.old, result["latest_successful_candidate"])
        self.assertIsNone(result["current_published"])
        self.assertEqual(self.prepared, annual_input.prepare_annual_input(repo_root=ROOT, company_id=self.company["company_id"]))

    def test_no_change_repeat_download_and_unrelated_filing(self):
        self.seed()
        first = self.inspect(self.new)
        def unrelated(p):
            recent = p["filings"]["recent"]
            for field in recent:
                recent[field].append(recent[field][0])
            recent["form"][-1] = "8-K"
            recent["accessionNumber"][-1] = "0001048286-26-009999"
        self.save(self.inventory_url, self.mutated_inventory(unrelated))
        self.save(self.primary_url)
        second = self.inspect(self.new)
        self.assertNotEqual(first["submissions"]["source_proof"]["request_attempt_id"], second["submissions"]["source_proof"]["request_attempt_id"])
        for report in (first, second):
            self.assertEqual("NO_NEW_ANNUAL_FILING", report["status"], report)
            self.assertIsNone(report["prepared_input"])
            self.assertEqual([0, 0, 0], report["provider_paid_sec_calls"])

    def test_candidate_leading_publication_survives_discovery_failure(self):
        self.seed()
        report = update.inspect_annual_update(repo_root=self.root, company=self.company,
            successful_candidate=self.new, published=self.old)
        self.assertEqual("CANDIDATE_PENDING_PUBLICATION", report["status"])
        self.assertEqual("UNCHANGED", report["filing_change"])
        self.assertEqual("NONE", report["candidate_work"])
        self.assertEqual("SUCCESSFUL_CANDIDATE_PENDING", report["publication_work"])
        (self.root / "evidence/requests_log.csv").unlink()
        failed = update.inspect_annual_update(repo_root=self.root, company=self.company,
            successful_candidate=self.new, published=self.old)
        self.assertEqual("CHECK_FAILED", failed["status"])
        self.assertEqual("SUCCESSFUL_CANDIDATE_PENDING", failed["publication_work"])
        self.assertEqual("UNKNOWN", failed["filing_change"])

    def test_publication_progress_is_explicit_and_run_specific(self):
        self.seed()
        missing = self.inspect(self.new)
        self.assertEqual("NOT_SUPPLIED", missing["publication_work"])
        current = update.inspect_annual_update(repo_root=self.root, company=self.company,
            successful_candidate=self.new, published=self.new)
        self.assertEqual("NONE", current["publication_work"])
        replacement = {**self.new, "run_id": self.new["run_id"] + ":different-execution"}
        pending = update.inspect_annual_update(repo_root=self.root, company=self.company,
            successful_candidate=replacement, published=self.new)
        self.assertEqual("SUCCESSFUL_CANDIDATE_PENDING", pending["publication_work"])
        self.assertEqual("CANDIDATE_PENDING_PUBLICATION", pending["status"])

    def test_missing_sources_and_stale_facts_are_not_ready(self):
        self.seed(primary=False, facts=False)
        missing = self.inspect()
        self.assertEqual("INPUTS_MISSING", missing["status"])
        self.assertEqual(["PRIMARY_DOCUMENT", "COMPANYFACTS"], [s["kind"] for s in missing["missing_sources"]])
        self.save(self.primary_url)
        payload = json.loads(self.sources[self.facts_url])
        for namespace in payload["facts"].values():
            for concept in namespace.values():
                for unit, facts in concept["units"].items():
                    concept["units"][unit] = [f for f in facts if f.get("accn") != self.new["filing"]["accession"]]
        self.save(self.facts_url, json.dumps(payload).encode())
        stale = self.inspect()
        self.assertEqual("INPUTS_MISSING", stale["status"], stale)
        self.assertEqual("TARGET_ANNUAL_FACTS_MISSING", stale["missing_sources"][0]["reason"])

    def test_metadata_failures_never_report_no_change(self):
        self.seed()
        def annual(p):
            return p["filings"]["recent"], p["filings"]["recent"]["form"].index("10-K")
        def set_annual(field, value):
            def mutate(p):
                recent, index = annual(p)
                recent[field][index] = value
            return mutate
        def duplicate(p):
            recent, index = annual(p)
            for values in recent.values():
                values.append(values[index])
        cases = [(set_annual("form", "10-K/A"), "AMENDED"),
                 (set_annual("reportDate", ""), "REPORT_DATE_INVALID"),
                 (set_annual("reportDate", None), "REPORT_DATE_INVALID"),
                 (set_annual("reportDate", "2025-02-30"), "REPORT_DATE_INVALID"),
                 (set_annual("filingDate", ""), "FILING_DATE_INVALID"),
                 (duplicate, "AMBIGUOUS"),
                 (lambda p: p.update(cik="9999999"), "CIK_MISMATCH"),
                 (lambda p: p["filings"]["files"].append({"filingFrom": "2025-01-01", "filingTo": "2025-02-01"}), "SUPPLEMENTAL_HISTORY_REQUIRED"),
                 (lambda p: p["filings"]["files"].append({"filingFrom": "", "filingTo": ""}), "HISTORY_DATE_UNKNOWN")]
        for mutation, reason in cases:
            with self.subTest(reason=reason):
                self.save(self.inventory_url, self.mutated_inventory(mutation))
                report = self.inspect(self.new)
                self.assertEqual("CHECK_FAILED", report["status"], report)
                self.assertIn(reason, report["error"])
                self.assertIsNone(report["prepared_input"])

    def test_unknown_form_cannot_hide_a_possible_new_annual(self):
        self.seed()
        for form in (None, "", " ", 10, [], {}):
            def mutate(payload):
                recent = payload["filings"]["recent"]
                index = recent["form"].index("10-K")
                for values in recent.values():
                    values.append(values[index])
                recent["accessionNumber"][-1] = "0001048286-27-009999"
                recent["reportDate"][-1] = "2026-12-31"
                recent["filingDate"][-1] = "2027-02-10"
                recent["form"][-1] = form
            with self.subTest(form=form):
                self.save(self.inventory_url, self.mutated_inventory(mutate))
                report = self.inspect(self.new)
                self.assertEqual("CHECK_FAILED", report["status"])
                self.assertEqual("FILING_FORM_UNKNOWN", report["error"])
                self.assertEqual("UNKNOWN", report["filing_change"])

    def test_malformed_companyfacts_containers_report_failure(self):
        self.seed()
        shapes = [[], None, {"test": []}, {"test": {"concept": []}},
                  {"test": {"concept": {"units": []}}},
                  {"test": {"concept": {"units": {"USD": {}}}}},
                  {"test": {"concept": {"units": {"USD": [None]}}}}]
        for facts in shapes:
            with self.subTest(facts=facts):
                raw = json.dumps({"cik": int(self.company["primary_cik"]), "facts": facts}).encode()
                self.save(self.facts_url, raw)
                report = self.inspect()
                self.assertEqual("CHECK_FAILED", report["status"])
                self.assertEqual("COMPANYFACTS_STRUCTURE_INVALID", report["error"])
                self.assertEqual(self.old, report["latest_successful_candidate"])

    def test_preparation_failure_keeps_baselines_and_repeats_pending(self):
        self.seed(primary=False)
        self.save(self.primary_url, b"<html>SIMULATED invalid new primary</html>")
        before = copy.deepcopy(self.old)
        for _ in range(2):
            failed = self.inspect()
            self.assertEqual("CHECK_FAILED", failed["status"])
            self.assertEqual("NEW_ANNUAL_FILING", failed["filing_change"])
            self.assertEqual(before, failed["latest_successful_candidate"])
            self.assertIsNone(failed["prepared_input"])
        self.assertEqual(before, self.old)

    def test_later_failed_request_and_same_accession_conflict(self):
        self.seed()
        self.save(self.primary_url, self.sources[self.primary_url] + b"\nSIMULATED content conflict")
        report = self.inspect(self.new)
        self.assertEqual("CHECK_FAILED", report["status"])
        self.assertIn("CONTENT_CONFLICT", report["error"])
        self.save(self.inventory_url, b"SIMULATED failure", status=503)
        report = self.inspect(self.new)
        self.assertEqual("CHECK_FAILED", report["status"])
        self.assertIn("LATEST_SOURCE_REQUEST_FAILED", report["error"])

    def refresh(self, responses, *, limit=3, baseline=None):
        observed = []
        def opened(*, request, timeout):
            observed.append(request.full_url)
            expected, payload = responses[len(observed) - 1]
            self.assertEqual(expected, request.full_url)
            if isinstance(payload, Exception):
                raise payload
            if isinstance(payload, tuple):
                return Response(*payload)
            return Response(payload)
        with patch.object(sec_http, "urlopen", side_effect=opened):
            report = update.refresh_annual_update(repo_root=self.root, company=self.company,
                successful_candidate=baseline or self.old, refresh="missing", sec_request_limit=limit)
        self.assertEqual(len(observed), report["provider_paid_sec_calls"][2])
        return report, observed

    def test_conditional_refresh_uses_real_client_and_appends_evidence(self):
        self.seed(primary=False, facts=False)
        old_log = (self.root / "evidence/requests_log.csv").read_bytes()
        historical = {p: p.read_bytes() for p in (self.root / "evidence/request_attempts").rglob("*") if p.is_file()}
        report, urls = self.refresh([(url, self.sources[url]) for url in (self.inventory_url, self.primary_url, self.facts_url)])
        self.assertEqual("INPUT_READY", report["status"], report)
        self.assertEqual(3, len(urls))
        self.assertTrue((self.root / "evidence/requests_log.csv").read_bytes().startswith(old_log))
        for p, raw in historical.items():
            self.assertEqual(raw, p.read_bytes())
        repeat, urls = self.refresh([(self.inventory_url, self.sources[self.inventory_url])], baseline=self.new)
        self.assertEqual("NO_NEW_ANNUAL_FILING", repeat["status"], repeat)
        self.assertEqual([self.inventory_url], urls)

    def test_refresh_bound_failures_stop_without_fallback_or_retry(self):
        self.seed(primary=False, facts=False)
        report, urls = self.refresh([(self.inventory_url, OSError("SIMULATED connection failure"))])
        self.assertEqual("CHECK_FAILED", report["status"], report)
        self.assertEqual(1, len(urls))
        report, urls = self.refresh([(self.inventory_url, (b"SIMULATED HTTP 503", 503))])
        self.assertEqual("CHECK_FAILED", report["status"])
        self.assertEqual(1, len(urls), "Retryable HTTP failure exceeded the one-request bound")
        report, urls = self.refresh([(self.inventory_url, self.sources[self.inventory_url])], limit=1)
        self.assertEqual("INPUTS_MISSING", report["status"])
        self.assertEqual(1, len(urls))
        report, urls = self.refresh([(self.inventory_url, self.sources[self.inventory_url]),
                                     (self.primary_url, b"SIMULATED invalid primary")])
        self.assertEqual("CHECK_FAILED", report["status"], report)
        self.assertEqual(2, len(urls))

    def test_real_persistence_conflict_keeps_failure_and_unknown_count(self):
        self.seed()
        raw = self.sources[self.inventory_url]
        digest = sha256_bytes(content=raw)
        snapshot = self.root / "evidence/request_attempts" / digest[:2] / digest / self.inventory_url.rsplit("/", 1)[1]
        count = []
        def opened(**kwargs):
            count.append(kwargs["request"].full_url)
            # Simulate a conflicting on-disk observation at the HTTP boundary.
            # The unmodified client's real immutable writer raises RuntimeError.
            snapshot.write_bytes(b"SIMULATED immutable disk conflict")
            return Response(raw)
        before_rows = update._rows(self.root)
        with patch.object(sec_http, "urlopen", side_effect=opened):
            report = update.refresh_annual_update(repo_root=self.root, company=self.company,
                successful_candidate=self.old, refresh="missing", sec_request_limit=3)
        self.assertEqual("CHECK_FAILED", report["status"])
        self.assertIn("Immutable request artifact changed", report["error"])
        self.assertEqual([self.inventory_url], count)
        self.assertEqual([0, 0, None], report["provider_paid_sec_calls"])
        self.assertEqual(1, report["sec_fetch_invocations"])
        tail = update._rows(self.root)[len(before_rows):]
        self.assertEqual(1, len(tail))
        self.assertIn("PersistenceError: RuntimeError", tail[0]["error"])
        self.assertEqual(self.old, report["latest_successful_candidate"])

    def test_cli_http_failure_stdout_is_one_json_document(self):
        from tools import vnext_annual_update as cli
        self.seed()
        # Real immutable publication fixture; only its file root is supplied
        # to the CLI. No publication, selection or HTTP-client behavior stub.
        output_root = self.root / "outputs"
        output_root.mkdir()
        for name in ("active_publication.json", "active_publication.json.lock"):
            shutil.copyfile(ROOT / "outputs" / name, output_root / name)
        shutil.copytree(ROOT / "outputs/publication_switch_receipts", output_root / "publication_switch_receipts")
        pointer = json.loads((output_root / "active_publication.json").read_text())
        publication = pointer["publication_id"]
        shutil.copytree(ROOT / "outputs/publications" / publication, output_root / "publications" / publication)
        stdout, stderr = io.StringIO(), io.StringIO()
        calls = []
        def opened(**kwargs):
            calls.append(kwargs["request"].full_url)
            return Response(b"SIMULATED HTTP 503", status=503)
        original_root = cli.REPO_ROOT
        cli.REPO_ROOT = self.root
        try:
            with patch.object(sec_http, "urlopen", side_effect=opened), redirect_stdout(stdout), redirect_stderr(stderr):
                code = cli.main(["--refresh", "missing", "--sec-request-limit", "3"])
        finally:
            cli.REPO_ROOT = original_root
        report = json.loads(stdout.getvalue())
        self.assertEqual(2, code)
        self.assertEqual("CHECK_FAILED", report["status"], report)
        self.assertEqual([0, 0, 1], report["provider_paid_sec_calls"])
        self.assertEqual([self.inventory_url], calls)
        self.assertIn("SEC retry exhausted", stderr.getvalue())

    def test_http_metadata_serialization_failure_keeps_unknown_count(self):
        self.seed()
        calls = []
        def opened(**kwargs):
            calls.append(kwargs["request"].full_url)
            response = Response(self.sources[self.inventory_url])
            response.headers = {"X-Test-Invalid-Header": object()}
            return response
        before_rows = update._rows(self.root)
        with patch.object(sec_http, "urlopen", side_effect=opened):
            report = update.refresh_annual_update(repo_root=self.root, company=self.company,
                successful_candidate=self.old, refresh="missing", sec_request_limit=3)
        self.assertEqual("CHECK_FAILED", report["status"])
        self.assertEqual([self.inventory_url], calls)
        self.assertEqual([0, 0, None], report["provider_paid_sec_calls"])
        self.assertEqual(1, report["sec_fetch_invocations"])
        tail = update._rows(self.root)[len(before_rows):]
        self.assertEqual(1, len(tail))
        self.assertIn("PersistenceError: TypeError", tail[0]["error"])

    def test_source_tamper_and_failed_baseline_rejected(self):
        self.seed()
        saved = update.saved_source(repo_root=self.root, url=self.inventory_url)
        (self.root / saved["proof"]["request_repo_relative_path"]).write_bytes(b"SIMULATED tamper")
        self.assertEqual("CHECK_FAILED", self.inspect(self.new)["status"])
        copied = self.root / "failed_run"
        copied.mkdir()
        for name in ("manifest.json", "records.jsonl", "review_decisions.jsonl"):
            shutil.copyfile(NEW_RUN / name, copied / name)
        records = [json.loads(l) for l in (copied / "records.jsonl").read_text().splitlines()]
        (copied / "records.jsonl").write_text("\n".join(json.dumps(r) for r in records if r["record_type"] != "METRIC_RESULT"))
        with self.assertRaisesRegex(ValueError, "BASELINE_FROZEN_BYTES_CHANGED"):
            update.candidate_baseline(company=self.company, run_dir=copied)
        manifest = json.loads((copied / "manifest.json").read_text())
        manifest["status"] = "OPEN"
        (copied / "manifest.json").write_text(json.dumps(manifest))
        (copied / "records.jsonl").write_text("\n".join(json.dumps(r) for r in records if r["record_type"] != "AI_EXTRACTION_ATTEMPT"))
        with self.assertRaisesRegex(ValueError, "BASELINE_ATTEMPT_NOT_SUCCESSFUL"):
            update.candidate_baseline(company=self.company, run_dir=copied)

    def test_code_head_and_output_location_do_not_define_filing_change(self):
        self.seed()
        def git(*args):
            return subprocess.check_output(["git", "-c", "user.name=Annual Update Test", "-c",
                "user.email=annual-update-tests@secmetrics.org", *args], cwd=self.root, stderr=subprocess.DEVNULL).decode().strip()
        git("init")
        (self.root / "test_code.txt").write_text("SIMULATED code version 1")
        git("add", "test_code.txt")
        git("commit", "-m", "synthetic code baseline")
        head = git("rev-parse", "HEAD")
        first = self.inspect(self.new)
        (self.root / "test_code.txt").write_text("SIMULATED code version 2")
        git("commit", "-am", "synthetic code-only change")
        self.assertNotEqual(head, git("rev-parse", "HEAD"))
        self.assertEqual(first["filing_change"], self.inspect(self.new)["filing_change"])
        other = self.root / "another_saved_input_directory"
        shutil.copytree(self.root / "evidence", other / "evidence")
        shutil.copytree(self.root / "config", other / "config")
        result = update.inspect_annual_update(repo_root=other, company=self.company, successful_candidate=self.new)
        self.assertEqual(first["filing_change"], result["filing_change"])
        self.assertEqual("NO_NEW_ANNUAL_FILING", result["status"], result)
        self.assertEqual(sha256_bytes(content=self.sources[self.primary_url]), self.new["primary_sha256"])


if __name__ == "__main__":
    unittest.main()
