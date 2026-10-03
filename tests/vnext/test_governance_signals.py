"""C03 native-source selection and no-arbitrary-person regressions."""

import copy
import json
import unittest
from pathlib import Path

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_text_coverage import annual, binding
from vnext.governance_signals import C03_SPEC_PATH, GovernanceSignalError
from vnext.governance_signals import replay_c03, resolve_c03
from vnext.governance_signals import C04_SPEC_PATH, replay_c04, resolve_c04
from vnext.sources import source_reference_record
from vnext.canonical import sha256_bytes
from vnext.deterministic_router import source_set_manifest
from vnext.observations import scope_key
from vnext.specs import compile_spec_file


def source(rows, *, measure="money:USD", ecd_uri="http://xbrl.sec.gov/ecd/2025"):
    parts = ['<xbrli:unit id="amount_unit"><xbrli:measure>' + measure + '</xbrli:measure></xbrli:unit>']
    for i, row in enumerate(rows):
        period_start, period_end = row.get("period_start", "2025-01-01"), row.get("period_end", "2025-12-31")
        person = row.get("person")
        dimension = row.get("dimension", "ecd:IndividualAxis")
        member = ('<xbrli:segment><xbrldi:explicitMember dimension="' + dimension + '">' + person + '</xbrldi:explicitMember></xbrli:segment>') if person else ""
        parts.append('<xbrli:context id="p' + str(i) + '"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">' + row.get("entity", "12345") + '</xbrli:identifier>' + member + '</xbrli:entity><xbrli:period><xbrli:startDate>' + period_start + '</xbrli:startDate><xbrli:endDate>' + period_end + '</xbrli:endDate></xbrli:period></xbrli:context>')
        if row.get("concept") == "ecd:PeoName":
            parts.append('<p><ix:nonNumeric name="ecd:PeoName" contextRef="p' + str(i) + '">' + row["amount"] + '</ix:nonNumeric></p>')
        else:
            parts.append('<p><ix:nonFraction name="' + row.get("concept", "ecd:PeoTotalCompAmt") + '" contextRef="p' + str(i) + '" unitRef="amount_unit" scale="' + row.get("scale", "0") + '" decimals="0" format="' + row.get("format", "ixt:num-dot-decimal") + '">' + row["amount"] + '</ix:nonFraction></p>')
    raw = annual("".join(parts), form="DEF 14A")
    return raw.replace(b"<html ", ('<html xmlns:ecd="' + ecd_uri + '" xmlns:ex="https://example.test/taxonomy" xmlns:money="http://www.xbrl.org/2003/iso4217" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2022-02-16" ').encode(), 1)


def arguments(raw):
    args = binding(raw)
    args.pop("expected_company_id")
    args.pop("expected_period_end")
    scope = {"entity_scope": "registrant"}
    args["target"] = {"company_id": "sample_entity", "period_start": "2025-01-01", "period_end": "2025-12-31",
                      "scope": scope, "scope_key": scope_key(scope=scope)}
    args["compiled_spec"] = compile_spec_file(path=REPO_ROOT / C03_SPEC_PATH, dependency_specs={})
    return args


class GovernanceSignalsTest(unittest.TestCase):
    def test_native_observation_calculator_trace_and_replay(self):
        args = arguments(source([{"amount": "1,234,567", "person": "ex:PersonAMember"}]))
        resolved = resolve_c03(**args)
        self.assertEqual("1234567", resolved["result"]["value"])
        self.assertEqual("USD", resolved["observation"]["unit"])
        self.assertEqual("PASS", resolved["result"]["reason_code"])
        self.assertEqual(resolved["observation"]["observation_id"], resolved["trace"]["steps"][0]["observation_id"])
        self.assertEqual(resolved, replay_c03(resolution=resolved, **args))
        self.assertEqual(resolved, replay_c03(resolution=json.loads(json.dumps(resolved)), **args))
        self.assertFalse(resolved["formal_publication_authorized"])

    def test_same_value_repetitions_and_generic_person_are_not_summed(self):
        resolved = resolve_c03(**arguments(source([{"amount": "100"}, {"amount": "100", "person": "ecd:PeoMember"}, {"amount": "100", "person": "ex:PersonAMember"}])))
        self.assertEqual("100", resolved["result"]["value"])
        self.assertEqual(3, len(resolved["observation"]["source_binding"]["fact_locators"]))

    def test_multiple_people_even_equal_amounts_cannot_first_win(self):
        resolved = resolve_c03(**arguments(source([{"amount": "100", "person": "ex:PersonAMember"}, {"amount": "100", "person": "ex:PersonBMember"}])))
        self.assertEqual("C03_MULTIPLE_REPORTED_PEOPLE", resolved["selection"]["reason_code"])
        self.assertIsNone(resolved["result"]["value"])

    def test_conflicting_amounts_and_reported_zero_are_retained(self):
        rows = [{"amount": "100", "person": "ex:PersonAMember"}, {"amount": "—", "person": "ex:PersonBMember", "format": "ixt:fixed-zero"}]
        resolved = resolve_c03(**arguments(source(rows)))
        self.assertEqual("C03_MULTIPLE_REPORTED_AMOUNTS", resolved["selection"]["reason_code"])
        self.assertEqual(["0", "100"], resolved["selection"]["distinct_values"])
        self.assertEqual("WITHHELD", resolved["result"]["publication"])

    def test_old_year_quarter_and_compensation_actually_paid_do_not_substitute(self):
        rows = [{"amount": "20", "period_start": "2024-01-01", "period_end": "2024-12-31"},
                {"amount": "30", "period_start": "2025-10-01"},
                {"amount": "900", "concept": "ecd:PeoActuallyPaidCompAmt"}]
        resolved = resolve_c03(**arguments(source(rows)))
        self.assertEqual("C03_TARGET_PERIOD_NOT_FOUND", resolved["selection"]["reason_code"])
        self.assertIsNone(resolved["observation"])
        self.assertEqual(2, len(resolved["selection"]["excluded"]))

    def test_proper_noncalendar_duration_and_scale(self):
        raw = source([{"amount": "1,234", "scale": "3", "period_start": "2025-02-02", "period_end": "2026-01-31"}])
        args = arguments(raw)
        args["target"]["period_start"], args["target"]["period_end"] = "2025-02-02", "2026-01-31"
        self.assertEqual("1234000", resolve_c03(**args)["result"]["value"])

    def test_different_entity_dimension_or_unit_blocks_current_scalar(self):
        for row in ({"amount": "100", "entity": "54321"}, {"amount": "100", "person": "ex:PersonAMember", "dimension": "ex:GeographyAxis"}):
            resolved = resolve_c03(**arguments(source([row])))
            self.assertEqual("C03_TARGET_FACT_INVALID", resolved["selection"]["reason_code"])
        resolved = resolve_c03(**arguments(source([{"amount": "100"}], measure="money:EUR")))
        self.assertEqual("C03_USD_UNIT_REQUIRED", resolved["selection"]["invalid_target_facts"][0]["reason"])

    def test_malformed_current_competitor_is_not_silently_dropped(self):
        resolved = resolve_c03(**arguments(source([{"amount": "100"}, {"amount": "unknown"}])))
        self.assertEqual("C03_TARGET_FACT_INVALID", resolved["selection"]["reason_code"])
        self.assertIsNone(resolved["result"]["value"])
        self.assertEqual(1, len(resolved["selection"]["candidates"]))

    def test_namespace_and_unknown_transform_cannot_impersonate_ecd_usd(self):
        with self.assertRaisesRegex(GovernanceSignalError, "ECD_TAXONOMY"):
            resolve_c03(**arguments(source([{"amount": "100"}], ecd_uri="https://example.test/not-ecd")))
        for transform in ("ixt:num-comma-decimal", "ex:num-dot-decimal"):
            resolved = resolve_c03(**arguments(source([{"amount": "100", "format": transform}])))
            self.assertEqual("C03_TARGET_FACT_INVALID", resolved["selection"]["reason_code"])
        raw = source([{"amount": "100"}]).replace(b"http://www.xbrl.org/2003/iso4217", b"https://example.test/currency")
        self.assertEqual("C03_TARGET_FACT_INVALID", resolve_c03(**arguments(raw))["selection"]["reason_code"])

    def test_source_and_output_mutations_cannot_replay(self):
        args = arguments(source([{"amount": "100"}]))
        resolved = resolve_c03(**args)
        changed = copy.deepcopy(resolved)
        changed["selection"]["candidates"][0]["value"] = "101"
        with self.assertRaisesRegex(GovernanceSignalError, "REPLAY_MISMATCH"):
            replay_c03(resolution=changed, **args)
        args["raw_bytes"] = args["raw_bytes"].replace(b">100<", b">101<")
        with self.assertRaisesRegex(GovernanceSignalError, "BYTES_CHANGED"):
            resolve_c03(**args)

    def test_live_network_and_legacy_outputs_are_unneeded(self):
        from unittest.mock import patch
        args = arguments(source([{"amount": "100"}]))
        with patch("socket.socket", side_effect=AssertionError("network called")), patch.object(Path, "read_text", side_effect=AssertionError("legacy file read")):
            self.assertEqual("100", resolve_c03(**args)["result"]["value"])

    def test_other_period_zero_placeholder_needs_positive_current_name_identity(self):
        rows = [{"amount": "—", "format": "ixt:fixed-zero", "person": "ex:FormerPersonMember"},
                {"amount": "100", "person": "ex:CurrentPersonMember"},
                {"concept": "ecd:PeoName", "amount": "Former Person", "person": "ex:FormerPersonMember", "period_start": "2024-01-01", "period_end": "2024-12-31"},
                {"concept": "ecd:PeoName", "amount": "Current Person", "person": "ex:CurrentPersonMember"}]
        resolved = resolve_c03(**arguments(source(rows)))
        self.assertEqual("100", resolved["result"]["value"])
        self.assertEqual("OTHER_PERIOD_PEO_ZERO_PLACEHOLDER", resolved["selection"]["excluded"][0]["reason"])
        # Removing the typed historical relationship must not invoke a generic
        # pick-the-nonzero rule.
        resolved = resolve_c03(**arguments(source(rows[:2] + rows[3:])))
        self.assertIsNone(resolved["result"]["value"])

    def test_second_current_name_retains_true_multiple_peo_and_no_value_guess(self):
        rows = [{"amount": "—", "format": "ixt:fixed-zero", "person": "ex:PersonAMember"},
                {"amount": "100", "person": "ex:PersonBMember"},
                {"concept": "ecd:PeoName", "amount": "Person A", "person": "ex:PersonAMember"},
                {"concept": "ecd:PeoName", "amount": "Person B", "person": "ex:PersonBMember"}]
        resolved = resolve_c03(**arguments(source(rows)))
        self.assertEqual("C03_MULTIPLE_REPORTED_AMOUNTS", resolved["selection"]["reason_code"])
        self.assertEqual(2, len(resolved["selection"]["reported_person_facts"]))
        self.assertEqual(2, len(resolved["selection"]["candidates"]))

    def test_old_name_period_and_mismatching_dimensions_cannot_authorize_current_person(self):
        rows = [{"amount": "100", "person": "ex:PersonAMember"},
                {"concept": "ecd:PeoName", "amount": "Person A", "person": "ex:PersonAMember", "period_start": "2024-01-01", "period_end": "2024-12-31"},
                {"concept": "ecd:PeoName", "amount": "Person B", "person": "ex:PersonBMember"}]
        resolved = resolve_c03(**arguments(source(rows)))
        self.assertEqual("C03_TARGET_FACT_INVALID", resolved["selection"]["reason_code"])
        self.assertIn("C03_CURRENT_PEO_IDENTITY_MISMATCH", [r["reason"] for r in resolved["selection"]["invalid_target_facts"]])
        rows[2]["dimension"] = "ex:GeographyAxis"
        resolved = resolve_c03(**arguments(source(rows)))
        self.assertIn("C03_PEO_NAME_SCOPE_CONFLICT", [r["reason"] for r in resolved["selection"]["invalid_target_facts"]])


def c04_filing(name, *, accession="0000012345-26-000001", year="2025", form="10-K", entity="12345"):
    raw = annual('<ix:nonNumeric name="dei:AuditorName" contextRef="annual">' + name + '</ix:nonNumeric>', form=form, cik=entity)
    raw = raw.replace(b"2025-", (year + "-").encode())
    args = binding(raw)
    args["source_reference"] = source_reference_record(raw_blob=args["raw_blob"], company_id="sample_entity",
        source_url="https://www.sec.gov/Archives/edgar/data/12345/" + accession.replace("-", "") + "/source.htm",
        accession=accession, document_name="source.htm", source_role="auditor_report", request_attempt_id="test-only-source-attempt")
    return {k: args[k] for k in ("raw_bytes", "raw_blob", "source_reference")}


def c04_events(item=None, *, history_files=None, payload_cik="12345"):
    documents, references = [], []
    accession = "0000012345-25-000005"
    payload = {"cik": payload_cik, "filings": {"recent": {"accessionNumber": [accession] if item else [],
                                      "filingDate": ["2025-04-01"] if item else [],
                                      "form": ["8-K"] if item else []}, "files": history_files or []}}
    raw = json.dumps(payload).encode()
    blob = {"record_type": "RAW_BLOB", "raw_asset_id": "sha256:" + sha256_bytes(content=raw), "byte_length": len(raw), "media_type": "application/json", "storage_uri": "fixture/submissions.json"}
    inventory_ref = source_reference_record(raw_blob=blob, company_id="sample_entity", source_url="https://data.sec.gov/submissions/CIK0000012345.json", accession="SUBMISSIONS-2025", document_name="CIK0000012345.json", source_role="sec_submissions_inventory", request_attempt_id="test-only-inventory-attempt")
    if item:
        doc = {}
        for key, name, content in (("hdr", "header.sgml", ("<ITEMS>" + item + "\n").encode()),
                                   ("primary", "event.htm", ("<html><body>Item " + item + ". Auditor report.</body></html>").encode())):
            b = {"record_type": "RAW_BLOB", "raw_asset_id": "sha256:" + sha256_bytes(content=content), "byte_length": len(content), "media_type": "text/html", "storage_uri": "fixture/" + name}
            ref = source_reference_record(raw_blob=b, company_id="sample_entity", source_url="https://www.sec.gov/Archives/edgar/data/12345/" + accession.replace("-", "") + "/" + name, accession=accession, document_name=name, source_role="fy_8k", request_attempt_id="test-only-event-attempt")
            doc["hdr_bytes" if key == "hdr" else "primary_document_bytes"] = content
            doc["hdr_source_reference" if key == "hdr" else "primary_source_reference"] = ref
            references.append(ref)
        documents.append(doc)
    manifest = source_set_manifest(company_id="sample_entity", source_role="fy_8k", form_types=["8-K"],
        fiscal_or_date_window={"period_start": "2025-01-01", "period_end": "2025-12-31"}, discovery_policy="PINNED_SUBMISSIONS",
        inventory_source_reference=inventory_ref, inventory_bytes=raw, ordered_source_references=references, cutoff_timestamp_or_pinned_submissions_attempt="test-only-cutoff")
    return {"filing_documents": documents, "source_set_manifest": manifest, "inventory_source_reference": inventory_ref, "inventory_bytes": raw}


def c04_arguments(current="Example Audit LLP", prior="Example Audit LLP", events=True):
    scope = {"entity_scope": "registrant"}
    return {"current_filings": [[c04_filing(current)]],
            "prior_sources": [c04_filing(prior, accession="0000012345-25-000001", year="2024")],
            "target_accession": "0000012345-26-000001", "prior_period_end": "2024-12-31",
            "target": {"company_id": "sample_entity", "period_start": "2025-01-01", "period_end": "2025-12-31", "scope": scope, "scope_key": scope_key(scope=scope)},
            "expected_cik": "12345", "compiled_spec": compile_spec_file(path=REPO_ROOT / C04_SPEC_PATH, dependency_specs={}),
            "event_input": c04_events() if events else None}


class AuditorSignalsTest(unittest.TestCase):
    def test_rebound_inventory_identity_and_history_dates_cannot_grant_zero(self):
        # All raw hashes/SourceReference/SourceSetManifest identities are newly
        # and consistently built; rejection must be a source-content check.
        cases = [(c04_events(payload_cik="54321"), "C04_INVENTORY_ENTITY_CONFLICT"),
                 (c04_events(history_files=[{"name": "CIK0000012345-submissions-001.json",
                    "filingFrom": "unknown", "filingTo": "unknown"}]), "C04_HISTORY_DATE_INVALID"),
                 (c04_events(history_files=[{"name": "CIK0000012345-submissions-001.json",
                    "filingFrom": "2026-01-01", "filingTo": "2025-01-01"}]), "C04_HISTORY_DATE_INVALID")]
        for source_input, reason in cases:
            args = c04_arguments()
            args["event_input"] = source_input
            with self.subTest(reason=reason), self.assertRaisesRegex(GovernanceSignalError, reason):
                resolve_c04(**args)

    def test_unchanged_requires_both_names_and_complete_event_source_set(self):
        args = c04_arguments(current="Example Audit, LLP", prior="EXAMPLE AUDIT LLP")
        resolved = resolve_c04(**args)
        self.assertEqual("0", resolved["result"]["value"])
        self.assertEqual(resolved, replay_c04(resolution=resolved, **args))
        args["event_input"] = None
        self.assertEqual("C04_EVENT_COVERAGE_REQUIRED", resolve_c04(**args)["selection"]["reason_code"])

    def test_equal_year_end_names_do_not_hide_intervening_item_4_01(self):
        args = c04_arguments()
        args["event_input"] = c04_events("4.01")
        resolved = resolve_c04(**args)
        self.assertEqual("1", resolved["result"]["value"])
        self.assertEqual(1, len(resolved["selection"]["matched_item_4_01_claim_ids"]))

    def test_different_bound_names_are_positive_without_absence_claim(self):
        resolved = resolve_c04(**c04_arguments(current="Second Audit LLP", events=False))
        self.assertEqual("1", resolved["result"]["value"])
        self.assertIsNone(resolved["selection"]["event_item_claims"])

    def test_amendment_precedes_same_year_original_and_conflict_never_falls_back(self):
        args = c04_arguments()
        args["current_filings"] = [[c04_filing("", form="10-K/A")], [c04_filing("Example Audit LLP", accession="0000012345-26-000002")]]
        resolved = resolve_c04(**args)
        self.assertEqual("0000012345-26-000002", resolved["selection"]["selected_current_accession"])
        self.assertEqual("0", resolved["result"]["value"])
        args["current_filings"][0] = [c04_filing('Example Audit LLP</ix:nonNumeric><ix:nonNumeric name="dei:AuditorName" contextRef="annual">Conflicting Audit LLP', form="10-K/A")]
        self.assertEqual("C04_AUDITOR_SOURCE_CONFLICT", resolve_c04(**args)["selection"]["reason_code"])

    def test_same_cik_prior_period_target_order_and_raw_byte_tamper(self):
        args = c04_arguments()
        args["prior_sources"] = [c04_filing("Example Audit LLP", accession="0000012345-25-000001", year="2024", entity="54321")]
        self.assertEqual("C04_AUDITOR_SOURCE_CONFLICT", resolve_c04(**args)["selection"]["reason_code"])
        args = c04_arguments()
        args["target_accession"] = "0000012345-26-000099"
        with self.assertRaisesRegex(GovernanceSignalError, "FILED_TARGET"):
            resolve_c04(**args)
        args = c04_arguments()
        args["prior_sources"][0]["raw_bytes"] += b" "
        with self.assertRaisesRegex(GovernanceSignalError, "BYTES_CHANGED"):
            resolve_c04(**args)

    def test_deleted_event_and_required_history_shard_cannot_make_zero(self):
        args = c04_arguments()
        args["event_input"] = c04_events("4.01")
        args["event_input"]["filing_documents"] = []
        with self.assertRaises(ValueError):
            resolve_c04(**args)
        args = c04_arguments()
        payload = json.loads(args["event_input"]["inventory_bytes"])
        payload["filings"]["files"] = [{"name": "CIK0000012345-submissions-001.json", "filingFrom": "2024-01-01", "filingTo": "2025-03-01"}]
        args["event_input"]["inventory_bytes"] = json.dumps(payload).encode()
        with self.assertRaisesRegex(GovernanceSignalError, "HISTORY_SHARD_SET_INCOMPLETE"):
            resolve_c04(**args)

    def test_missing_prior_never_becomes_no_change(self):
        args = c04_arguments()
        args["prior_sources"] = []
        self.assertEqual("C04_COMPARABLE_AUDITOR_FACTS_MISSING", resolve_c04(**args)["selection"]["reason_code"])


if __name__ == "__main__":
    unittest.main()
