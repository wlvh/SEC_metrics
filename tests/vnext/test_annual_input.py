"""Raw-input integration using real saved SEC bytes and zero network."""

import builtins
import copy
import io
import json
import socket
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from vnext import annual_input
from vnext.ai_adapter import build_recorded_adapter
from vnext.batch_workflow import create_companyfacts_release_run
from vnext.canonical import sha256_bytes
from vnext.run_store import load_open_run
from vnext.workflow import create_table_task_review_run
from vnext.workflow import finalize_reviewed_direct_results, WorkflowError


REPO_ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_RUN = REPO_ROOT / (
    "artifacts/vnext/qualification/cycles/"
    "0c4569437b1bac3ad353394c8d8b1f59b1a1ee7c229c8fa5ee51a22269b6a448/runs/"
    "0799ec7f91b6bc0472fd80c6c655beb90ddd7db583dcd13cae0bfab506e6412c"
)


@contextmanager
def independent_inputs():
    """Block actual historical matrix reads and all legacy semantic calls."""
    opened, calls = [], set()
    original_io, original_open = io.open, builtins.open

    def check(file):
        if isinstance(file, (str, Path)):
            path = Path(file)
            if path.name in {"metrics_matrix.csv", "metric_evidence.csv"}:
                raise AssertionError("Historical result read: " + str(path))
            opened.append(str(path))

    def checked_io(file, *args, **kwargs):
        check(file)
        return original_io(file, *args, **kwargs)

    def checked_open(file, *args, **kwargs):
        check(file)
        return original_open(file, *args, **kwargs)

    def profile(frame, event, arg):
        if event == "call" and frame.f_globals.get("__name__") == "sec_pipeline":
            name = frame.f_code.co_name
            calls.add(name)
            if name not in {"filing_rows_from_submission_payloads",
                            "flatten_filing_block", "require_key"}:
                raise AssertionError("Legacy function executed: " + name)

    old_profile = sys.getprofile()
    with mock.patch("io.open", checked_io), mock.patch(
        "builtins.open", checked_open,
    ), mock.patch.object(socket.socket, "connect", side_effect=AssertionError("network")):
        sys.setprofile(profile)
        try:
            yield opened, calls
        finally:
            sys.setprofile(old_profile)


def historical_response():
    """Read a test oracle after preparation; it never selects new input."""
    records = [json.loads(line) for line in
               (HISTORICAL_RUN / "records.jsonl").read_text().splitlines()]
    attempt = next(r for r in records if r["record_type"] == "AI_EXTRACTION_ATTEMPT")
    response = (HISTORICAL_RUN / attempt["assistant_output_path"]).read_bytes()
    assert sha256_bytes(content=response) == attempt["assistant_output_sha256"]
    return attempt, response


def recorded_candidate(*, prepared, run_dir):
    """Use the original response only after exact reader request equality."""
    attempt, response = historical_response()
    expected = (HISTORICAL_RUN / attempt["reader_payload_path"]).read_bytes()
    adapter = build_recorded_adapter(
        response_bytes=response, fixture_id="offline-original:" + attempt["attempt_id"],
    )
    original = type(adapter).complete
    completions = []

    def exact_complete(self, *, request_bytes):
        if request_bytes != expected:
            raise AssertionError("Historical response has a different reader request")
        completions.append(sha256_bytes(content=request_bytes))
        return original(self, request_bytes=request_bytes)

    with mock.patch.object(type(adapter), "complete", exact_complete):
        created = create_table_task_review_run(
            repo_root=REPO_ROOT, run_dir=run_dir,
            run_id="run:offline:annual-input:occupancy", clock=None,
            task_contract_id="lodging_occupancy_table_v2", adapter=adapter,
            **prepared["table_input"],
        )
    _, records, _ = load_open_run(run_dir=run_dir)
    current = next(r for r in records if r["record_type"] == "AI_EXTRACTION_ATTEMPT")
    for field in ("task_contract_path", "output_schema_path"):
        assert ((run_dir / current[field]).read_bytes()
                == (HISTORICAL_RUN / attempt[field]).read_bytes())
    finalized = finalize_reviewed_direct_results(repo_root=REPO_ROOT, run_dir=run_dir)
    return created, finalized, completions


class AnnualInputTest(unittest.TestCase):
    def _assert_invalid_raw_annual_date(self, *, form, report_date, fiscal_year):
        """Inject raw parallel arrays; retain the real submissions converter."""
        payload = json.loads(
            (REPO_ROOT / "evidence/submissions/CIK0001048286.json").read_text())
        recent = payload["filings"]["recent"]
        payload["filings"]["recent"] = {
            field: [values[0], values[0]] for field, values in recent.items()
        }
        recent = payload["filings"]["recent"]
        recent.update({
            "form": [form, "10-K"],
            "accessionNumber": ["0001048286-26-000099", "0001048286-25-000099"],
            "filingDate": ["2026-03-01", "2025-02-11" if form == "10-K" else "2026-02-10"],
            "reportDate": [report_date, "2024-12-31" if form == "10-K" else "2025-12-31"],
            "primaryDocument": ["synthetic-new.htm", "synthetic-original.htm"],
        })
        raw = json.dumps(payload).encode("utf-8")

        def inventory_only(**kwargs):
            self.assertEqual(
                "https://data.sec.gov/submissions/CIK0001048286.json",
                kwargs["url"],
                "Invalid annual metadata reached target/Company Facts reads",
            )
            return {}, raw

        with mock.patch.object(
            annual_input, "_saved_source", side_effect=inventory_only,
        ) as saved, mock.patch.object(
            annual_input, "filing_rows_from_submission_payloads",
            wraps=annual_input.filing_rows_from_submission_payloads,
        ) as convert, mock.patch.object(
            socket.socket, "connect", side_effect=AssertionError("network"),
        ):
            with self.assertRaisesRegex(
                annual_input.AnnualInputError, "ANNUAL_REPORT_DATE_INVALID",
            ):
                annual_input.prepare_annual_input(
                    repo_root=REPO_ROOT, company_id="marriott_international",
                    fiscal_year=fiscal_year,
                )
            convert.assert_called_once()
            saved.assert_called_once()

    def test_unknown_new_annual_date_cannot_fall_back_to_older_year(self):
        for report_date in ("", None, "2025-02-30"):
            with self.subTest(report_date=report_date):
                self._assert_invalid_raw_annual_date(
                    form="10-K", report_date=report_date, fiscal_year=None,
                )

    def test_unknown_amendment_date_blocks_default_and_explicit_year(self):
        for report_date in ("", None, "not-a-date"):
            for fiscal_year in (None, 2025):
                with self.subTest(report_date=report_date, fiscal_year=fiscal_year):
                    self._assert_invalid_raw_annual_date(
                        form="10-K/A", report_date=report_date,
                        fiscal_year=fiscal_year,
                    )

    def test_raw_inputs_reach_b01_and_exact_recorded_b10(self):
        with tempfile.TemporaryDirectory() as temporary, independent_inputs() as observed:
            prepared = annual_input.prepare_annual_input(
                repo_root=REPO_ROOT, company_id="marriott_international",
            )
            structured = create_companyfacts_release_run(
                repo_root=REPO_ROOT, run_dir=Path(temporary) / "structured",
                run_id="run:offline:annual-input:structured",
                **prepared["companyfacts_input"],
            )
            self.assertEqual("26186000000", structured["results"]["B01"]["value"])
            self.assertEqual("USD", structured["results"]["B01"]["unit"])
            run_dir = Path(temporary) / "occupancy"
            _, _, calls = recorded_candidate(prepared=prepared, run_dir=run_dir)
            _, records, decisions = load_open_run(run_dir=run_dir)
            result = next(r for r in records if r["record_type"] == "METRIC_RESULT")
            self.assertEqual(("B10", "0.693", "ratio", "PASS"),
                             tuple(result[k] for k in ("metric_id", "value", "unit", "reason_code")))
            self.assertEqual("2025-01-01", result["period_start"])
            self.assertEqual("2025-12-31", result["period_end"])
            self.assertEqual("SYSTEM", decisions[0]["reviewer_type"])
            self.assertEqual(1, len(calls))
            inventory_path = str(REPO_ROOT / prepared["source_proofs"][0]["request_repo_relative_path"])
            self.assertIn(inventory_path, observed[0])
            self.assertIn("filing_rows_from_submission_payloads", observed[1])
            before = (run_dir / "records.jsonl").read_bytes()
            with self.assertRaisesRegex(WorkflowError, "TERMINAL_DIVERGENT"):
                recorded_candidate(prepared=prepared, run_dir=run_dir)
            self.assertEqual(before, (run_dir / "records.jsonl").read_bytes())

    def test_historical_annual_progression_uses_distinct_source_periods(self):
        with tempfile.TemporaryDirectory() as temporary, independent_inputs():
            inputs, values = [], []
            for year in (2023, 2024, 2025):
                p = annual_input.prepare_annual_input(
                    repo_root=REPO_ROOT, company_id="marriott_international", fiscal_year=year,
                )
                result = create_companyfacts_release_run(
                    repo_root=REPO_ROOT, run_dir=Path(temporary) / str(year),
                    run_id="run:offline:annual-input:" + str(year), **p["companyfacts_input"],
                )
                inputs.append(p)
                values.append(result["results"]["B01"]["value"])
                self.assertEqual(year, p["table_input"]["target_period"]["fiscal_year"])
            self.assertEqual(["23713000000", "25100000000", "26186000000"], values)
            self.assertEqual(3, len({p["table_input"]["accession"] for p in inputs}))
            self.assertEqual(3, len({p["source_proofs"][1]["content_sha256"] for p in inputs}))
            self.assertEqual(inputs[-1], annual_input.prepare_annual_input(
                repo_root=REPO_ROOT, company_id="marriott_international"))

    def test_missing_original_stops_without_fallback(self):
        rows = annual_input.parse_request_log_rows(
            text=(REPO_ROOT / "evidence/requests_log.csv").read_text())
        rows = [r for r in rows if not r["document_name"].endswith(".htm")]
        with mock.patch.object(annual_input, "parse_request_log_rows", return_value=rows):
            with self.assertRaisesRegex(annual_input.AnnualInputError, "SAVED_SOURCE_MISSING"):
                annual_input.prepare_annual_input(
                    repo_root=REPO_ROOT, company_id="marriott_international")

    def test_ambiguous_and_amended_metadata_fail(self):
        original = annual_input.filing_rows_from_submission_payloads
        for mutation, reason in (("duplicate", "AMBIGUOUS"), ("amended", "AMENDED")):
            def changed(**kwargs):
                rows = original(**kwargs)
                annual = copy.deepcopy(next(r for r in rows if r["form"] == "10-K"))
                if mutation == "amended":
                    annual["form"] = "10-K/A"
                return rows + [annual]
            with self.subTest(mutation=mutation), mock.patch.object(
                annual_input, "filing_rows_from_submission_payloads", changed,
            ), self.assertRaisesRegex(annual_input.AnnualInputError, reason):
                annual_input.prepare_annual_input(repo_root=REPO_ROOT,
                                                   company_id="marriott_international")

    def test_raw_period_contradiction_fails(self):
        p = annual_input.prepare_annual_input(repo_root=REPO_ROOT,
                                               company_id="marriott_international")
        raw = (REPO_ROOT / p["table_input"]["source_repo_relative_path"]).read_bytes()
        with self.assertRaises(ValueError):
            annual_input._annual_period(raw=raw, cik=1048286,
                                        filing={"form": "10-K", "reportDate": "2024-12-31"})


if __name__ == "__main__":
    unittest.main()
