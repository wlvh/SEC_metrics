"""D04 normal source packets: exact input coverage, no inferred absence."""

import copy
import json
import unittest

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_text_coverage import annual
from tests.vnext.test_text_business_candidates import source_arguments
from vnext.canonical import content_hash
from vnext.going_concern_source import (
    GoingConcernSourceError, UNIT_SOURCE_BYTES, inspect_going_concern_source,
    prepare_ordinary_going_concern_source, verify_going_concern_source,
)


BODY = '''<h2>Item 1A. Risk Factors</h2><p>Our operations face economic risks.</p>
<h2>Item 1B. Unresolved Staff Comments</h2><p>None.</p>
<h2>Item 3. Legal Proceedings</h2><p>The legal disclosures are included below.</p>
<h2>Item 4. Mine Safety Disclosures</h2><p>Not applicable.</p>
<h2>Item 8. Financial Statements and Supplementary Data</h2><p>The statements follow.</p>
<h2>Item 9. Changes in and Disagreements with Accountants</h2><p>None.</p>
<h2>Report of Independent Registered Public Accounting Firm</h2>
<p>We have audited the accompanying consolidated balance sheets of Example Corporation and its subsidiaries (the Company) as of December 31, 2025 and 2024, and the related consolidated statements of operations.</p>
<p>In our opinion, the financial statements present fairly in all material respects.</p>
{statement}
<h2>Consolidated Balance Sheets</h2><p>Balance sheet amounts appear here.</p>
<h2>Note 1. Accounting Policies</h2><p>Our accounting policies are described here.</p>'''
POSITIVE = "As of December 31, 2025, Example Corporation has substantial doubt about its ability to continue as a going concern."


def arguments(statement="", body=None, extra_fact=""):
    body = BODY.format(statement="<p>" + statement + "</p>") if body is None else body
    raw = annual(body).replace(b"</ix:hidden>", (
        '<ix:nonNumeric name="dei:EntityRegistrantName" contextRef="annual">Example Corporation</ix:nonNumeric>'
        + extra_fact + "</ix:hidden>").encode())
    return source_arguments(raw)


def component(statement="", **kwargs):
    return inspect_going_concern_source(**arguments(statement, **kwargs))


def named_cover_arguments(dei_name, cover_name, audit_name=None, caption_count=1):
    cover = '<h1>FORM 10-K</h1>' + (
        '<h1>' + cover_name + '</h1><p>(Exact name of registrant as specified in its charter)</p>') * caption_count
    cover += '<p>Securities registered pursuant to Section 12(b) of the Act:</p>'
    body = BODY.format(statement="").replace('of Example Corporation and', 'of ' + (audit_name or cover_name) + ' and')
    args = arguments(body=cover + body)
    raw = args['raw_bytes'].replace(b'contextRef="annual">Example Corporation</ix:nonNumeric>',
        ('contextRef="annual">' + dei_name + '</ix:nonNumeric>').encode())
    return source_arguments(raw)


class GoingConcernSourceTest(unittest.TestCase):
    def test_legal_terminal_alias_requires_same_source_explicit_cover_name(self):
        for dei_name,cover_name in [('Example Motor Co','Example Motor Company'),
                                   ('Example Corporation','Example Corp.'),
                                   ('Example International Inc /MD/','Example International, Incorporated')]:
            with self.subTest(dei_name=dei_name):
                args = named_cover_arguments(dei_name,cover_name)
                p = inspect_going_concern_source(**args)
                binding = p['registrant_name_binding']
                self.assertEqual('SAME_SOURCE_COVER_AND_CURRENT_DEI_NAME_BOUND',binding['status'])
                self.assertTrue(p['auditor_openings'][0]['target_name_match'])
                self.assertFalse(binding['relation']['marker_jurisdiction_meaning_asserted'])
                for evidence in ('cover_name','cover_caption'):
                    locator=binding[evidence]
                    self.assertIn(locator['text'].encode(),args['raw_bytes'][locator['raw_start_byte']:locator['raw_end_byte']])
        args = named_cover_arguments('Example Motor Co','Example Motor Company',caption_count=0)
        p=inspect_going_concern_source(**args)
        self.assertEqual('EXACT_DEI_NAME_ONLY',p['registrant_name_binding']['status'])
        self.assertFalse(p['auditor_openings'][0]['target_name_match'])

    def test_false_alias_middle_word_organizational_form_and_neighbor_are_not_merged(self):
        for dei_name,cover_name in [('Ford Motor Co','Ford Credit Company'),
                                   ('Example Co Holdings Inc','Example Company Holdings Inc'),
                                   ('Example Corporation','Example LLC'),
                                   ('Example Motor Co /MD/','Example Credit Company'),
                                   ('Example Motor Co /XYZ/','Example Motor Company')]:
            with self.subTest(cover_name=cover_name):
                p=inspect_going_concern_source(**named_cover_arguments(dei_name,cover_name))
                self.assertEqual('COVER_DEI_NAME_CONFLICT',p['registrant_name_binding']['status'])
                self.assertFalse(p['auditor_openings'][0]['target_name_match'])
        p=inspect_going_concern_source(**named_cover_arguments('Ford Motor Co','Ford Motor Company','Ford Credit Company'))
        self.assertEqual('SAME_SOURCE_COVER_AND_CURRENT_DEI_NAME_BOUND',p['registrant_name_binding']['status'])
        self.assertFalse(p['auditor_openings'][0]['target_name_match'])

    def test_duplicate_cover_and_foreign_dei_name_context_cannot_create_alias(self):
        p=inspect_going_concern_source(**named_cover_arguments('Example Motor Co','Example Motor Company',caption_count=2))
        self.assertEqual('COVER_NAME_AMBIGUOUS',p['registrant_name_binding']['status'])
        args=named_cover_arguments('Example Motor Co','Example Motor Company')
        raw=args['raw_bytes'].replace(b'name="dei:EntityRegistrantName" contextRef="annual"',
            b'name="dei:EntityRegistrantName" contextRef="other"')
        context=(b'<xbrli:context id="other"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">98765</xbrli:identifier></xbrli:entity>'
            b'<xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>')
        raw=raw.replace(b'</ix:hidden>',context+b'</ix:hidden>')
        p=inspect_going_concern_source(**source_arguments(raw))
        self.assertEqual('DEI_NAME_MISSING_OR_AMBIGUOUS',p['registrant_name_binding']['status'])
        self.assertTrue(p['registrant_name_binding']['invalid_dei_contexts'])
        self.assertFalse(p['auditor_openings'][0]['target_name_match'])

    def test_rehashed_fake_accepted_alias_is_rebuilt_from_original_cover(self):
        args=named_cover_arguments('Ford Motor Co','Ford Motor Company')
        p=inspect_going_concern_source(**args)
        p['registrant_name_binding']['accepted_source_names'].append('Ford Credit Company')
        p['component_id']=content_hash(value={k:v for k,v in p.items() if k!='component_id'})
        with self.assertRaisesRegex(GoingConcernSourceError,'REPLAY_CHANGED'):
            verify_going_concern_source(component=p,**args)

    def test_real_marriott_marker_and_ford_terminal_abbreviation_bind_to_cover(self):
        for company in ('marriott_international','ford_motor_company'):
            with self.subTest(company=company):
                p=prepare_ordinary_going_concern_source(repo_root=REPO_ROOT,company_id=company)
                original=p['components'][0]
                binding=original['registrant_name_binding']
                self.assertEqual('SAME_SOURCE_COVER_AND_CURRENT_DEI_NAME_BOUND',binding['status'])
                self.assertEqual(1,sum(r['identity_status']=='TARGET_NAME_AND_CURRENT_BALANCE_SHEET_DATE_MATCHED'
                                       for r in original['auditor_openings']))
                self.assertFalse(p['not_disclosed_confirmed'])

    def test_exact_current_report_and_named_statement_are_candidates_only(self):
        packet = component(POSITIVE)
        report = packet["auditor_openings"][0]
        self.assertEqual("TARGET_NAME_AND_CURRENT_BALANCE_SHEET_DATE_MATCHED", report["identity_status"])
        self.assertFalse(report["report_authorship_and_semantics_verified"])
        claim = packet["language_candidates"][0]
        self.assertEqual("DIRECT_SOURCE_DECLARATION_CANDIDATE", claim["candidate_status"])
        self.assertIn("EXPLICIT_NAMED_CURRENT_DOUBT_DECLARATION", claim["labels"])
        self.assertFalse(claim["current_company_doubt_asserted"])
        self.assertTrue(packet["semantic_review_required"])

    def test_negation_retains_negative_statement_without_closed_world_absence(self):
        packet = component(POSITIVE.replace("has substantial", "has no substantial"))
        claim = packet["language_candidates"][0]
        self.assertIn("EXPLICIT_NAMED_CURRENT_NEGATIVE_DECLARATION", claim["labels"])
        self.assertFalse(packet["not_disclosed_confirmed"])
        self.assertFalse(packet["input_coverage"]["semantic_coverage_complete"])

    def test_clean_audit_and_keyword_miss_never_become_no_doubt(self):
        packet = component()
        self.assertEqual([], packet["language_candidates"])
        self.assertEqual([], packet["native_concept_candidates"])
        self.assertFalse(packet["not_disclosed_confirmed"])
        self.assertFalse(packet["clean_opinion_used_as_absence"])
        self.assertEqual("NOT_GRANTED_BY_COMPONENT_API", packet["source_admission"])

    def test_historical_hypothetical_other_entity_and_negated_claims_stay_separate(self):
        cases = [POSITIVE.replace("2025", "2024"), POSITIVE.replace("Example Corporation", "Acquired Corporation"),
                 "If " + POSITIVE[0].lower() + POSITIVE[1:],
                 'For example, "' + POSITIVE + '"',
                 "We previously stated that " + POSITIVE,
                 "We do not believe that there is substantial doubt about our ability to continue as a going concern.",
                 "Management's plans alleviate the substantial doubt about our ability to continue as a going concern."]
        for statement in cases:
            with self.subTest(statement=statement):
                p = component(statement)
                self.assertEqual("SEMANTIC_REVIEW_REQUIRED", p["language_candidates"][0]["candidate_status"])
                self.assertFalse(p["not_disclosed_confirmed"])
                self.assertFalse(p["language_candidates"][0]["current_company_doubt_asserted"])

    def test_same_date_elsewhere_does_not_repair_wrong_audit_subject_or_period(self):
        body = BODY.format(statement="<p>The annual report date is December 31, 2025.</p>")
        for old,new in [("of Example Corporation and its subsidiaries", "of Other Corporation and its subsidiaries"),
                        ("as of December 31, 2025 and 2024", "as of December 31, 2024 and 2023")]:
            with self.subTest(new=new):
                p = component(body=body.replace(old,new))
                self.assertEqual("OTHER_OR_UNRESOLVED_SUBJECT_OR_PERIOD", p["auditor_openings"][0]["identity_status"])

    def test_internal_control_audit_is_not_a_financial_statement_audit(self):
        body = BODY.format(statement="").replace(
            "the accompanying consolidated balance sheets of Example Corporation and its subsidiaries (the Company)",
            "Example Corporation's internal control over financial reporting")
        p = component(body=body)
        self.assertEqual("INTERNAL_CONTROL", p["auditor_openings"][0]["report_kind"])
        self.assertFalse(p["auditor_openings"][0]["target_name_match"])

    def test_unmapped_native_boolean_retains_namespace_context_and_source_value(self):
        for value in ("true", "false"):
            with self.subTest(value=value):
                p = component(extra_fact='<ix:nonNumeric name="dei:GoingConcernIndicator" contextRef="annual">' + value + '</ix:nonNumeric>')
                fact = p["native_concept_candidates"][0]
                self.assertEqual(value, fact["fact"]["text"])
                self.assertEqual("http://xbrl.sec.gov/dei/2025", fact["concept_namespace"])
                self.assertEqual("UNMAPPED_CONCEPT_REQUIRES_SEMANTIC_AUTHORITY", fact["status"])
                self.assertFalse(fact["boolean_doubt_value_asserted"])
                self.assertFalse(p["not_disclosed_confirmed"])

    def test_full_text_includes_unmatched_late_language_and_does_not_clip_large_block(self):
        long_text = "Unmatched financial information. " * (UNIT_SOURCE_BYTES // 20)
        p = component(body=BODY.format(statement="") + "<p>" + long_text + "</p><p>Liquidity is insufficient to meet obligations.</p>")
        units = p["semantic_source_units"]
        self.assertGreater(len(units), 1)
        self.assertTrue(any(u["oversized_single_block"] for u in units))
        rows = [row for u in units for row in u["blocks"]]
        self.assertEqual([[b["block_index"],b["text"]] for b in p["document"]["blocks"]], rows)
        self.assertEqual("Liquidity is insufficient to meet obligations.", rows[-1][1])
        self.assertEqual([], p["language_candidates"])
        self.assertFalse(p["input_coverage"]["provider_tokens_measured"])

    def test_real_json_roundtrip_and_resigned_tampering(self):
        args = arguments(POSITIVE); p = inspect_going_concern_source(**args)
        self.assertEqual(p, verify_going_concern_source(component=json.loads(json.dumps(p)), **args))
        def mutate(kind):
            changed = copy.deepcopy(p)
            if kind == "method": changed["method"] = "CALLER_ASSERTED_ABSENCE"
            if kind == "absence": changed["not_disclosed_confirmed"] = True
            if kind == "missing_units": changed["semantic_source_units"] = []
            if kind == "altered_unmatched_block": changed["semantic_source_units"][0]["blocks"][0][1] = "Changed source text"
            if kind == "locator": changed["language_candidates"][0]["raw_start_byte"] += 1
            if kind == "source": changed["source_reference"]["company_id"] = "other_company"
            changed["component_id"] = content_hash(value={k:v for k,v in changed.items() if k != "component_id"})
            return changed
        for kind in ("method","absence","missing_units","altered_unmatched_block","locator","source"):
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(GoingConcernSourceError,"REPLAY_CHANGED"):
                    verify_going_concern_source(component=mutate(kind), **args)

    def test_unicode_source_characters_survive_json_without_silent_normalization(self):
        args = arguments(body=BODY.format(statement="<p>Decomposed cafe\u0301 remains exact source text.</p>"))
        p = inspect_going_concern_source(**args)
        rows = p["semantic_source_units"][0]["blocks"]
        self.assertTrue(any("cafe\u0301" in row[1] for row in rows))
        self.assertEqual(p,verify_going_concern_source(component=json.loads(json.dumps(p)),**args))
        changed = copy.deepcopy(p)
        for row in changed["semantic_source_units"][0]["blocks"]:
            row[1] = row[1].replace("cafe\u0301","caf\u00e9")
        changed["component_id"] = content_hash(value={k:v for k,v in changed.items() if k != "component_id"})
        with self.assertRaisesRegex(GoingConcernSourceError,"REPLAY_CHANGED"):
            verify_going_concern_source(component=changed,**args)

    def test_source_entity_or_period_conflict_rejected(self):
        for key,value in (("cik","54321"),("company_id","other_company")):
            args = arguments(); args[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                inspect_going_concern_source(**args)
        args = arguments(); args["filing"]["reportDate"] = "2024-12-31"
        with self.assertRaisesRegex(ValueError,"PERIOD_MISMATCH"):
            inspect_going_concern_source(**args)

    def test_fragment_is_preserved_as_incomplete_not_no_disclosure(self):
        args = arguments(); raw = args["raw_bytes"].replace(b"</body></html>",b"")
        p = inspect_going_concern_source(**source_arguments(raw))
        self.assertEqual("INCOMPLETE",p["document"]["source_state"])
        self.assertFalse(p["not_disclosed_confirmed"])

    def test_real_pfizer_acquisition_phrase_and_paramount_predecessor(self):
        p = prepare_ordinary_going_concern_source(repo_root=REPO_ROOT,company_id="pfizer")
        original = p["components"][0]
        claims = original["language_candidates"]
        self.assertEqual(1,len(claims))
        self.assertIn("Seagen",claims[0]["text"])
        self.assertIn("GOING_CONCERN_VALUATION_LANGUAGE",claims[0]["labels"])
        self.assertEqual("SEMANTIC_REVIEW_REQUIRED",claims[0]["candidate_status"])
        self.assertFalse(p["not_disclosed_confirmed"])
        p = prepare_ordinary_going_concern_source(repo_root=REPO_ROOT,company_id="paramount_skydance_paramount_global")
        self.assertEqual(1 + len(p["prepared_annual_input"]["amendments"]),len(p["components"]))
        reports = p["components"][0]["auditor_openings"]
        self.assertEqual(2,len(reports))
        self.assertTrue(reports[0]["target_name_match"])
        self.assertTrue(reports[0]["target_balance_sheet_date_match"])
        self.assertFalse(reports[1]["target_name_match"])
        self.assertFalse(reports[1]["target_balance_sheet_date_match"])
        self.assertIn("Predecessor",reports[1]["source_subject"])
        self.assertEqual({"provider":0,"paid":0,"sec":0},p["calls"])


if __name__ == "__main__":
    unittest.main()
