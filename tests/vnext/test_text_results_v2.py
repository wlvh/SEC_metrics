"""C02/D02 disclosure periods, native review and hostile replay counterexamples."""
import copy
import json
import unittest
import tempfile
from pathlib import Path

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_text_coverage import annual, binding
from tests.vnext.test_text_business_candidates import BODY
from vnext.canonical import content_hash, sha256_bytes
from vnext.sources import source_reference_record
from vnext.text_results_v2 import prepare_business_text_sources, SCOPES


def source(raw, *, accession, filename, role="target_primary"):
    blob = {"record_type": "RAW_BLOB", "raw_asset_id": "sha256:" + sha256_bytes(content=raw),
            "byte_length": len(raw), "media_type": "text/html", "storage_uri": "fixture/" + filename}
    ref = source_reference_record(raw_blob=blob, company_id="sample_entity",
        source_url="https://www.sec.gov/Archives/edgar/data/12345/" + accession.replace("-", "") + "/" + filename,
        accession=accession, document_name=filename, source_role=role, request_attempt_id="test-only-source-attempt")
    return blob, ref, raw


def inputs(metric_id="C02", *, governance=None, form="DEF 14A", annual_body=BODY):
    anchor = source(annual(annual_body), accession="0000012345-26-000001", filename="annual.htm")
    scope = SCOPES[metric_id]
    target = {"company_id": "sample_entity", "entity": "12345", "accession": anchor[1]["accession"],
              "period_start": "2025-01-01", "period_end": "2025-12-31", "scope": scope, "scope_key": content_hash(value=scope)}
    fs = {anchor[1]["source_reference_id"]: {"form": "10-K", "accessionNumber": anchor[1]["accession"],
            "primaryDocument": "annual.htm", "filingDate": "2026-02-15", "reportDate": "2025-12-31"}}
    sources = [anchor]
    if metric_id == "C02":
        body = governance if governance is not None else ('<p>Our Board currently has eleven directors.</p>'
                '<p>Upon election, our Board will consist of twelve directors.</p>'
                '<p>The Board determined that all directors except the CEO are independent.</p>')
        gov = source(annual(body, form=form), accession="0000012345-26-000002", filename="governance.htm",
                     role="governance_proxy" if form == "DEF 14A" else "target_primary")
        sources.append(gov)
        fs[gov[1]["source_reference_id"]] = {"form": form, "accessionNumber": gov[1]["accession"],
            "primaryDocument": "governance.htm", "filingDate": "2026-03-27", "reportDate": "2026-05-08" if form == "DEF 14A" else "2025-12-31"}
    return {"target": target, "source_references": [s[1] for s in sources],
            "raw_blobs": {s[0]["raw_asset_id"]: s[0] for s in sources},
            "raw_bytes_by_id": {s[0]["raw_asset_id"]: s[2] for s in sources}, "source_filings": fs}


def accrual_inputs(*, start="2025-01-01", end="2025-12-31", entity="12345",
                   concept="LossContingencyAccrualProvision"):
    raw=annual(BODY).replace(b'xmlns:dei=',b'xmlns:us-gaap="http://fasb.org/us-gaap/2025" xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:dei=')
    extra=('<xbrli:context id="reported"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">'+entity+'</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>'+start+'</xbrli:startDate><xbrli:endDate>'+end+'</xbrli:endDate></xbrli:period></xbrli:context><xbrli:unit id="USD"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit><ix:nonFraction name="us-gaap:'+concept+'" contextRef="reported" unitRef="USD" scale="6">107</ix:nonFraction>').encode()
    raw=raw.replace(b'</ix:hidden>',extra+b'</ix:hidden>');blob,ref,raw=source(raw,accession="0000012345-26-000001",filename="annual.htm")
    args=inputs("D02");filing=next(iter(args["source_filings"].values()))
    args.update(source_references=[ref],raw_blobs={blob["raw_asset_id"]:blob},raw_bytes_by_id={blob["raw_asset_id"]:raw},source_filings={ref["source_reference_id"]:filing})
    return args


def replace_accrual_raw(args, raw):
    old=args["source_references"][0];filing=args["source_filings"][old["source_reference_id"]]
    blob,ref,raw=source(raw,accession=old["accession"],filename=old["document_name"])
    return {**args,"source_references":[ref],"raw_blobs":{blob["raw_asset_id"]:blob},
            "raw_bytes_by_id":{blob["raw_asset_id"]:raw},"source_filings":{ref["source_reference_id"]:filing}}


class TextResultV2SourceTest(unittest.TestCase):
    def test_c02_annual_anchor_filing_date_meeting_date_and_unknown_asof_are_distinct(self):
        args = inputs(); prepared = prepare_business_text_sources(metric_id="C02", **args)
        gov_id = args["source_references"][1]["source_reference_id"]
        coverage = prepared["coverages"][gov_id]
        self.assertEqual("2026-03-27", coverage["source_disclosure_date"])
        self.assertEqual("2026-05-08", coverage["source_filing"]["reportDate"])
        self.assertIsNone(coverage["board_measurement_as_of"])
        self.assertFalse(coverage["board_count_asserted"])
        self.assertEqual(3, len(prepared["proposals"][gov_id]["candidates"]))
        self.assertEqual("annual_grouping_only", args["target"]["scope"]["period_basis"])
        self.assertEqual(2, len(prepared["coverages"]))

    def test_c02_no_annual_anchor_cannot_assign_a_compensation_or_board_year(self):
        args = inputs();args["source_references"] = args["source_references"][1:]
        args["source_filings"] = {k:v for k,v in args["source_filings"].items() if v["form"] != "10-K"}
        with self.assertRaisesRegex(ValueError, "SOURCE_SET_INVALID"):
            prepare_business_text_sources(metric_id="C02", **args)
        args = inputs();args["target"]["period_start"] = "2025-10-01"
        with self.assertRaisesRegex(ValueError, "ANNUAL_PERIOD_CHANGED"):
            prepare_business_text_sources(metric_id="C02", **args)

    def test_c02_fye_board_scope_or_old_governance_source_is_rejected(self):
        args = inputs();args["target"]["scope"] = {**args["target"]["scope"], "board_as_of": "2025-12-31"}
        args["target"]["scope_key"] = content_hash(value=args["target"]["scope"])
        with self.assertRaisesRegex(ValueError, "DISCLOSURE_SCOPE_CHANGED"):
            prepare_business_text_sources(metric_id="C02", **args)
        args = inputs();sid=args["source_references"][1]["source_reference_id"]
        args["source_filings"][sid]["filingDate"] = "2024-03-27"
        with self.assertRaisesRegex(ValueError, "PRECEDES_ANNUAL_END"):
            prepare_business_text_sources(metric_id="C02", **args)

    def test_c02_amendment_metadata_cannot_retarget_different_raw_period(self):
        args = inputs(form="10-K/A");gov=args["source_references"][1];raw_id=gov["raw_asset_id"]
        raw=args["raw_bytes_by_id"][raw_id].replace(b">2025-12-31</ix:nonNumeric>", b">2024-12-31</ix:nonNumeric>")
        blob,new_ref,raw=source(raw,accession=gov["accession"],filename="governance.htm")
        filing=args["source_filings"].pop(gov["source_reference_id"]);args["source_filings"][new_ref["source_reference_id"]]=filing
        args["source_references"][1]=new_ref;args["raw_blobs"][blob["raw_asset_id"]]=blob;args["raw_bytes_by_id"][blob["raw_asset_id"]]=raw
        with self.assertRaisesRegex(ValueError, "PERIOD"):
            prepare_business_text_sources(metric_id="C02", **args)

    def test_c02_source_filing_or_cross_entity_cannot_supply_positive_result(self):
        args = inputs(governance='<p>Our Board currently has eleven directors.</p>')
        sid=args["source_references"][1]["source_reference_id"];args["source_filings"][sid]["primaryDocument"]="different.htm"
        with self.assertRaisesRegex(ValueError, "SOURCE_FILING_CHANGED"):
            prepare_business_text_sources(metric_id="C02", **args)
        args=inputs();args["target"]["entity"]="54321"
        with self.assertRaises(ValueError):prepare_business_text_sources(metric_id="C02", **args)

    def test_d02_forward_note_text_and_fact_inventory_are_not_total_liability(self):
        args=inputs("D02");prepared=prepare_business_text_sources(metric_id="D02", **args)
        sid=args["source_references"][0]["source_reference_id"]
        coverage=prepared["coverages"][sid]
        self.assertFalse(coverage["current_liability_or_accrual_asserted"])
        self.assertTrue(coverage["fact_periods_and_dimensions_preserved"])
        self.assertEqual("LOCATED_NOTE_RANGE", coverage["note_references"][0]["status"])
        self.assertTrue(any('court has not resolved' in c['text'] for c in prepared['proposals'][sid]['D02']['candidates']))

    def test_d02_missing_note_cannot_turn_into_not_disclosed(self):
        with self.assertRaisesRegex(ValueError, "NAVIGATION_INCOMPLETE"):
            prepare_business_text_sources(metric_id="D02", **inputs("D02",annual_body=BODY.replace("Refer to Note 2", "Refer to Note 8")))

    def test_current_same_entity_accrual_is_recorded_without_total_liability_inference(self):
        prepared=prepare_business_text_sources(metric_id="D02",**accrual_inputs())
        self.assertEqual("SOURCE_TEXT_READY",prepared["capability_status"])
        self.assertEqual([],prepared["capability_gaps"])
        fact=next(iter(prepared["coverages"].values()))["source_fact_inventory"]["facts"][0]
        self.assertEqual("107000000",fact["value_normalized"])
        self.assertTrue(fact["verified_monetary_value"])
        self.assertFalse(fact["aggregate_or_target_period_value_asserted"])
        self.assertEqual("2025-12-31",fact["context"]["period_end"])
        self.assertEqual([["http://www.xbrl.org/2003/iso4217","USD"]],fact["declared_unit"]["measures"])

    def test_old_other_entity_and_unaccrued_facts_are_not_current_accruals(self):
        for changes in ({"start":"2023-10-01","end":"2023-12-31"},{"entity":"54321"},
                        {"concept":"LossContingencyRangeOfPossibleLossPortionNotAccrued"}):
            with self.subTest(changes=changes):
                prepared=prepare_business_text_sources(metric_id="D02",**accrual_inputs(**changes))
                self.assertEqual("SOURCE_TEXT_READY",prepared["capability_status"])
                self.assertEqual([],prepared["capability_gaps"])

    def test_missing_unit_context_namespace_and_nil_never_gain_verified_amount(self):
        args=accrual_inputs();raw=next(iter(args["raw_bytes_by_id"].values()))
        fake_context=raw.replace(b'<xbrli:context id="reported">',b'<wrong:context xmlns:wrong="https://example.test/instance" id="reported">')
        left,right=fake_context.split(b'<wrong:context',1);fake_context=left+b'<wrong:context'+right.replace(b'</xbrli:context>',b'</wrong:context>',1)
        nil=raw.replace(b'xmlns:dei=',b'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:dei=').replace(b'scale="6">107',b'scale="6" xsi:nil="true">107')
        cases=[(raw.replace(b'unitRef="USD" scale="6"',b'unitRef="missing" scale="6"'),"MONETARY_UNIT_NOT_PROVEN"),
               (fake_context,"CONTEXT_NAMESPACE_NOT_PROVEN"),(nil,"NIL_SOURCE_VALUE")]
        for changed,reason in cases:
            with self.subTest(reason=reason):
                p=prepare_business_text_sources(metric_id="D02",**replace_accrual_raw(args,changed))
                fact=next(iter(p["coverages"].values()))["source_fact_inventory"]["facts"][0]
                self.assertEqual("SOURCE_TEXT_READY",p["capability_status"])
                self.assertIsNone(fact["value_normalized"])
                self.assertFalse(fact["verified_monetary_value"])
                self.assertTrue(any(reason in r for r in fact["verification_reason_codes"]))

    def test_supported_currency_and_numeric_lexical_subsets_preserve_exact_amount(self):
        args=accrual_inputs();raw=next(iter(args["raw_bytes_by_id"].values()))
        cases=[(raw.replace(b'iso4217:USD<',b'iso4217:EUR<'),"107000000","EUR"),
               (raw.replace(b'xmlns:dei=',b'xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12" xmlns:dei=').replace(b'scale="6">107',b'scale="6" format="ixt:numdotdecimal">1,234.5'),"1234500000","USD")]
        for changed,value,currency in cases:
            with self.subTest(currency=currency,value=value):
                prepared=prepare_business_text_sources(metric_id="D02",**replace_accrual_raw(args,changed))
                fact=next(iter(prepared["coverages"].values()))["source_fact_inventory"]["facts"][0]
                self.assertEqual(value,fact["value_normalized"])
                self.assertEqual(currency,fact["reported_currency"])
                self.assertTrue(fact["verified_monetary_value"])


def native_arguments(metric_id="C02", **kwargs):
    from vnext.specs import compile_spec_file
    name = "C02_board_disclosures_v1.md" if metric_id == "C02" else "D02_legal_disclosures_v1.md"
    return {"compiled_spec": compile_spec_file(path=REPO_ROOT / "catalog/r6" / name, dependency_specs={}),
            **inputs(metric_id, **kwargs)}


def native_reviewed(metric_id="C02", *, arguments=None, **kwargs):
    from vnext.text_results_v2 import create_deterministic_text_candidate, build_text_evidence, build_text_review_unit
    from vnext.review import create_system_review_decision
    from vnext.requirements import load_requirement_snapshot
    args = arguments or native_arguments(metric_id, **kwargs)
    candidate = create_deterministic_text_candidate(**args)
    evidence = build_text_evidence(candidate=candidate, **args)
    unit, assets = build_text_review_unit(compiled_spec=args["compiled_spec"], candidate=candidate,
        evidence_check=evidence, source_bindings=args["source_references"])
    # Actual existing D-06 policy machinery; synthetic sources have no normal
    # source admission or production credit. No HUMAN identity is invented.
    requirement = load_requirement_snapshot(snapshot_dir=REPO_ROOT / "requirements/ai_first_v3_3_1")
    decision = create_system_review_decision(review_unit=unit, required_claims=args["target"]["scope"],
        decided_at_utc="2026-09-12T12:00:00Z", requirement=requirement)
    return {**args, "company_traits": [], "candidate": candidate, "evidence_check": evidence,
            "review_unit": unit, "review_decisions": [decision]}, assets


def rehashed(record):
    from vnext.records import _expected_identifier
    altered = copy.deepcopy(record)
    key, value = _expected_identifier(record_type=altered["record_type"], record=altered)
    altered[key] = value
    return altered


class TextResultV2NativeTest(unittest.TestCase):
    def test_unhandled_currency_or_numeric_grouping_remains_literal_and_text_continues(self):
        from vnext.text_results_v2 import replay_text_result
        args=native_arguments("D02");args.update(accrual_inputs())
        raw=next(iter(args["raw_bytes_by_id"].values()))
        cases=[(raw.replace(b'iso4217:USD<',b'iso4217:ZZZ<'),"CURRENCY_NOT_SUPPORTED"),
               (raw.replace(b'iso4217:USD<',b'iso4217:GBP<'),"CURRENCY_NOT_SUPPORTED"),
               (raw.replace(b'>107</ix:nonFraction>',b'>1,23</ix:nonFraction>'),"NUMERIC_LEXICAL_FORM_NOT_SUPPORTED"),
               (raw.replace(b'xmlns:dei=',b'xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12" xmlns:dei=').replace(b'scale="6">107',b'scale="6" format="ixt:numdotdecimal">1,23'),"NUMERIC_LEXICAL_FORM_NOT_SUPPORTED")]
        for changed,reason in cases:
            with self.subTest(reason=reason):
                reviewed,assets=native_reviewed("D02",arguments=replace_accrual_raw(args,changed))
                result,_,_=replay_text_result(**reviewed)
                fact=reviewed["evidence_check"]["checks"][0]["coverage"][0]["source_fact_inventory"]["facts"][0]
                self.assertIsNone(fact["value_normalized"])
                self.assertFalse(fact["verified_monetary_value"])
                self.assertEqual("SOURCE_LITERAL_ONLY",fact["verification_status"])
                self.assertIn(reason.encode(),assets["rendered_review_bytes"])
                self.assertNotIn(b"123000000",assets["rendered_review_bytes"])
                self.assertEqual("TEXT_V1",result["value_kind"])

    def test_current_accrual_survives_real_json_disk_review_and_native_rebuild(self):
        from vnext.canonical import canonical_json_bytes
        from vnext.text_results_v2 import replay_text_result,verify_text_result
        args=native_arguments("D02");args.update(accrual_inputs())
        reviewed,assets=native_reviewed("D02",arguments=args)
        result,trace,observations=replay_text_result(**reviewed)
        fact=reviewed["evidence_check"]["checks"][0]["coverage"][0]["source_fact_inventory"]["facts"][0]
        self.assertEqual("107000000",fact["value_normalized"])
        self.assertIn(b"107000000",assets["rendered_review_bytes"])
        self.assertIn(b"LossContingencyAccrualProvision",assets["rendered_review_bytes"])
        self.assertEqual("text",result["unit"])
        self.assertNotEqual("107000000",result["value"])
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/"records.json"
            path.write_bytes(canonical_json_bytes(value={"arguments":{k:v for k,v in reviewed.items() if k!="raw_bytes_by_id"},
                "result":result,"trace":trace,"observations":observations}))
            stored=json.loads(path.read_bytes())
            rebuilt=verify_text_result(result=stored["result"],trace=stored["trace"],observations=stored["observations"],
                raw_bytes_by_id=reviewed["raw_bytes_by_id"],**stored["arguments"])
            self.assertEqual((result,trace,observations),rebuilt)

    def test_unsupported_transform_is_readable_raw_only_not_wrong_normalized_amount(self):
        from vnext.text_results_v2 import replay_text_result
        args=native_arguments("D02");args.update(accrual_inputs());raw=next(iter(args["raw_bytes_by_id"].values()))
        raw=raw.replace(b'xmlns:dei=',b'xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12" xmlns:dei=').replace(b'scale="6">107',b'scale="6" format="ixt:numcommadecimal">1,23')
        args=replace_accrual_raw(args,raw);reviewed,assets=native_reviewed("D02",arguments=args)
        result,_,_=replay_text_result(**reviewed)
        fact=reviewed["evidence_check"]["checks"][0]["coverage"][0]["source_fact_inventory"]["facts"][0]
        self.assertEqual("1,23",fact["source_text"])
        self.assertIsNone(fact["value_normalized"])
        self.assertEqual("SOURCE_LITERAL_ONLY",fact["verification_status"])
        self.assertIn(b"1,23",assets["rendered_review_bytes"])
        self.assertIn(b"UNSUPPORTED_NUMERIC_TRANSFORM",assets["rendered_review_bytes"])
        self.assertNotIn(b"123000000",assets["review_context_bytes"])
        self.assertNotIn(b"123000000",assets["rendered_review_bytes"])
        self.assertEqual("TEXT_V1",result["value_kind"])

    def test_rehashed_fact_inventory_cannot_change_a_verified_amount(self):
        from vnext.text_results_v2 import replay_text_result
        args=native_arguments("D02");args.update(accrual_inputs());reviewed,_=native_reviewed("D02",arguments=args)
        evidence=copy.deepcopy(reviewed["evidence_check"])
        coverage=evidence["checks"][0]["coverage"][0];inventory=coverage["source_fact_inventory"];fact=inventory["facts"][0]
        fact["value_normalized"]="999999999"
        fact["fact_evidence_id"]=content_hash(value={k:v for k,v in fact.items() if k!="fact_evidence_id"})
        inventory["fact_inventory_id"]=content_hash(value={k:v for k,v in inventory.items() if k!="fact_inventory_id"})
        coverage["coverage_hash"]=content_hash(value={k:v for k,v in coverage.items() if k!="coverage_hash"})
        with self.assertRaisesRegex(ValueError,"EVIDENCE_REPLAY_CHANGED"):
            replay_text_result(**{**reviewed,"evidence_check":rehashed(evidence)})

    def test_c02_and_d02_use_native_records_with_no_ai_or_human_identity(self):
        from vnext.text_results_v2 import replay_text_result, verify_text_result
        from vnext.records import validate_record
        from vnext.constraints import verify_trace_observation_values
        for metric in ("C02", "D02"):
            with self.subTest(metric=metric):
                args, assets = native_reviewed(metric)
                result, trace, observations = replay_text_result(**args)
                self.assertEqual("DETERMINISTIC_TEXT_CANDIDATE", args["candidate"]["record_type"])
                self.assertNotIn("attempt_id", args["candidate"])
                self.assertNotIn("assistant_output_sha256", args["candidate"])
                self.assertEqual("SYSTEM", args["review_decisions"][0]["reviewer_type"])
                self.assertEqual(("TEXT_V1", "EXACT", "PUBLISHED"), (result["value_kind"],result["quality"],result["publication"]))
                self.assertEqual(len(args["candidate"]["selected"]),len(observations))
                for r in [args["candidate"],args["evidence_check"],args["review_unit"],*args["review_decisions"],*observations,trace,result]:
                    self.assertEqual(r,validate_record(record=json.loads(json.dumps(r))))
                verify_trace_observation_values(trace=trace,observations={o["observation_id"]:o for o in observations})
                self.assertEqual((result,trace,observations),verify_text_result(result=result,trace=trace,observations=observations,**args))
                self.assertIn(b"Source dates and measurement basis",assets["rendered_review_bytes"])
                self.assertTrue(all(o["scope"] == SCOPES[metric] for o in observations))

    def test_omitted_or_changed_exact_excerpts_and_source_sets_are_rejected(self):
        from vnext.text_results_v2 import create_deterministic_text_candidate,build_text_evidence
        args=native_arguments();candidate=create_deterministic_text_candidate(**args)
        for mutation in ("omit", "replace", "scope"):
            altered=copy.deepcopy(candidate)
            if mutation=="omit":altered["selected"].pop("excerpt_2")
            elif mutation=="replace":altered["selected"]["excerpt_0"]["text"]="The board had twelve members at fiscal year end."
            else:altered["calculation_target"]["scope"]["board_as_of"]="2025-12-31"
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                build_text_evidence(candidate=rehashed(altered),**args)
        incomplete=copy.deepcopy(args);incomplete["source_references"].pop(0)
        with self.assertRaisesRegex(ValueError,"SOURCE_SET_INVALID"):
            build_text_evidence(candidate=candidate,**incomplete)

    def test_no_approval_or_stale_review_render_cannot_create_observations(self):
        from vnext.text_results_v2 import replay_text_result
        args,_=native_reviewed()
        with self.assertRaisesRegex(ValueError,"no decision"):
            replay_text_result(**{**args,"review_decisions":[]})
        changed=copy.deepcopy(args["review_unit"]);changed["rendered_review_hash"]="a"*64
        with self.assertRaisesRegex(ValueError,"REVIEW_BINDING_CHANGED"):
            replay_text_result(**{**args,"review_unit":rehashed(changed)})

    def test_changed_date_evidence_and_fully_rehashed_result_fail_raw_replay(self):
        from vnext.text_results_v2 import replay_text_result,verify_text_result
        from vnext.text_results import build_text_result_and_trace
        args,_=native_reviewed();result,trace,observations=replay_text_result(**args)
        evidence=copy.deepcopy(args["evidence_check"])
        evidence["checks"][0]["coverage"][1]["board_measurement_as_of"]="2025-12-31"
        with self.assertRaisesRegex(ValueError,"EVIDENCE_REPLAY_CHANGED"):
            replay_text_result(**{**args,"evidence_check":rehashed(evidence)})
        altered=copy.deepcopy(observations);altered[0]["value"]="Unsupported fiscal year-end board count."
        altered[0]=rehashed(altered[0]);payload=copy.deepcopy(result["text_payload"])
        payload["items"][0].update(text=altered[0]["value"],observation_id=altered[0]["observation_id"])
        result,trace=build_text_result_and_trace(compiled_spec=args["compiled_spec"],target=args["target"],payload=payload)
        with self.assertRaisesRegex(ValueError,"NATIVE_REPLAY_CHANGED"):
            verify_text_result(result=result,trace=trace,observations=altered,**args)

    def test_old_accrual_stays_in_original_context_not_current_value(self):
        from vnext.text_results_v2 import create_deterministic_text_candidate,build_text_evidence
        from vnext.specs import compile_spec_file
        body=BODY
        raw=annual(body).replace(b'xmlns:dei=',b'xmlns:us-gaap="http://fasb.org/us-gaap/2025" xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:dei=')
        extra=b'''<xbrli:context id="old"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">12345</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2023-10-01</xbrli:startDate><xbrli:endDate>2023-12-31</xbrli:endDate></xbrli:period></xbrli:context><xbrli:unit id="USD"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit><ix:nonFraction name="us-gaap:LossContingencyAccrualProvision" contextRef="old" unitRef="USD" scale="6">107</ix:nonFraction>'''
        raw=raw.replace(b'</ix:hidden>',extra+b'</ix:hidden>');blob,ref,raw=source(raw,accession="0000012345-26-000001",filename="annual.htm")
        args=native_arguments("D02");filing=next(iter(args["source_filings"].values()))
        args.update(source_references=[ref],raw_blobs={blob["raw_asset_id"]:blob},raw_bytes_by_id={blob["raw_asset_id"]:raw},source_filings={ref["source_reference_id"]:filing})
        candidate=create_deterministic_text_candidate(**args);evidence=build_text_evidence(candidate=candidate,**args)
        coverage=evidence["checks"][0]["coverage"][0];facts=coverage["source_fact_inventory"]["facts"]
        self.assertEqual("107000000",facts[0]["value_normalized"])
        self.assertEqual("2023-12-31",facts[0]["context"]["period_end"])
        self.assertFalse(coverage["current_liability_or_accrual_asserted"])
        self.assertTrue(all("107000000" not in c["text"] for c in candidate["selected"].values()))


if __name__ == "__main__":
    unittest.main()
