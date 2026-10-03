"""Real text candidates keep exact excerpts and source dates in public rows.

This is an explicit material suite; it freezes the installed successor rules.
It is intentionally excluded from the short fast-suite tier.
"""
import csv
import io
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from vnext.normal_run_v2 import install_normal_inputs, create_normal_run
from vnext.normal_text_projection_v2 import render_normal_text_run, render_open_text_preview
from vnext.run_store import RunStoreError, validate_and_freeze_run


class NormalTextProjectionV2Test(unittest.TestCase):
    def _case(self, company, metric, form, filed, count):
        with tempfile.TemporaryDirectory(prefix="normal-text-public-") as tmp:
            data, run = Path(tmp) / "data", Path(tmp) / "run"
            with patch.object(socket.socket, "connect", side_effect=AssertionError("No network")):
                install_normal_inputs(data_root=data, company_id=company, metric_id=metric)
                native = create_normal_run(data_root=data, run_dir=run,
                    company_id=company, metric_id=metric, freeze=False)
                with self.assertRaisesRegex(RunStoreError, "requires a FROZEN Run"):
                    render_normal_text_run(data_root=data, run_dir=run)
                preview = render_open_text_preview(data_root=data, run_dir=run)
                self.assertEqual("OPEN", preview["receipt"]["run_status"])
                validate_and_freeze_run(run_dir=run, repo_root=data)
                rendered = render_normal_text_run(data_root=data, run_dir=run)
            rows = list(csv.DictReader(io.StringIO(rendered["files"]["metrics_matrix.csv"].decode())))
            evidence = list(csv.DictReader(io.StringIO(rendered["files"]["metric_evidence.csv"].decode())))
            self.assertEqual([rendered["row"]], rows)
            self.assertEqual(rendered["evidence"], evidence)
            self.assertEqual(20, len(rows[0]))
            self.assertTrue(all(len(e) == 18 for e in evidence))
            self.assertEqual(count, len(evidence))
            self.assertEqual(native["result"]["value"], rows[0]["value"])
            self.assertEqual([i["text"] for i in native["result"]["text_payload"]["items"]],
                             [e["evidence_quote"] for e in evidence])
            self.assertEqual((form, filed), (rows[0]["form"], rows[0]["filed_date"]))
            self.assertEqual("TEXT_QUAL", rows[0]["status"])
            self.assertEqual("FROZEN", rendered["receipt"]["run_status"])
            self.assertFalse(rendered["receipt"]["production_authorized"])
            self.assertEqual(preview["files"], rendered["files"])
            if metric == "C02":
                self.assertIn("board measurement date not inferred", rows[0]["context_or_dimension"])
                self.assertNotEqual(filed, rows[0]["period_end"])

    def test_actual_proxy_disclosure_date_is_not_a_board_measurement_date(self):
        self._case("marriott_international", "C02", "DEF 14A", "2026-03-27", 29)

    def test_actual_part_iii_amendment_is_not_relabelled_proxy(self):
        self._case("paramount_skydance_paramount_global", "C02", "10-K/A", "2026-04-24", 12)

    def test_actual_legal_notes_keep_all_quotes_and_byte_evidence(self):
        self._case("jpmorgan_chase", "D02", "10-K", "2026-02-13", 34)


if __name__ == "__main__":
    unittest.main()
