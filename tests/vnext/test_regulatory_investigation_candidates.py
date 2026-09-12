"""D03 exact source, subject/status distinctions and replay counterexamples."""
import copy
import json
import unittest

from tests.vnext.test_text_coverage import annual
from tests.vnext.test_text_business_candidates import BODY,source_arguments
from vnext.canonical import content_hash
from vnext.regulatory_investigation_candidates import prepare_regulatory_investigation_candidates as prepare
from vnext.regulatory_investigation_candidates import replay_regulatory_investigation_candidates as replay


def args(text, *, prefix="", legal=None):
    body=BODY.replace("If a regulator conducts an investigation, our expenses could increase.",text)
    if legal:body=body.replace("We are defendants in litigation concerning a product contract.",legal)
    return source_arguments(annual(prefix+body))


def facts(bundle):
    return [f for c in bundle['candidates'] for f in c['facts']]


class RegulatoryCandidatesTest(unittest.TestCase):
    def test_current_involvement_is_a_reported_statement_not_case_count_or_fye(self):
        p=prepare(**args('We are also involved in government investigations that arise in the ordinary course of our business.'))
        f=next(f for f in facts(p) if f['rule_id']=='CURRENT_INVOLVEMENT')
        self.assertEqual('SOURCE_REPORTED_FACT',f['status']);self.assertTrue(f['current_status_asserted'])
        self.assertFalse(f['same_as_annual_measurement_period_asserted'])
        self.assertFalse(f['investigation_case_identity_or_count_inferred'])
        self.assertFalse(f['investigated_subject_identity_inferred_from_participation'])

    def test_proven_clause_cannot_certify_remaining_paragraph_or_target_identity(self):
        p=prepare(**args('We are involved in government investigations. Our supplier has received a separate subpoena.'))
        self.assertEqual(1,p['supported_fact_count'])
        candidate=next(c for c in p['candidates'] if c['facts'])
        self.assertTrue(candidate['requires_semantic_review'])
        self.assertFalse(candidate['unmatched_language_semantically_resolved'])

    def test_current_legal_inventory_requires_explicit_same_block_antecedent(self):
        p=prepare(**args('We are involved in various legal matters arising from our business. These include claims, suits, government investigations and other proceedings.'))
        self.assertTrue(any(f['rule_id']=='CURRENT_LEGAL_INVENTORY' and f['status']=='SOURCE_REPORTED_FACT' for f in facts(p)))
        p=prepare(**args('We are involved in various legal matters arising from our business.</p><p>These include government investigations of another company.'))
        self.assertFalse(any(f['status']=='SOURCE_REPORTED_FACT' for f in facts(p)))

    def test_old_process_receipt_does_not_assert_open_investigation_now(self):
        p=prepare(**args('In October 2018, we received a subpoena from the U.S. Attorney’s Office seeking records. We have produced records in response.'))
        f=next(f for f in facts(p) if f['rule_id']=='RECEIVED_PROCESS')
        self.assertEqual('SOURCE_REPORTED_FACT',f['status']);self.assertFalse(f['current_status_asserted'])
        self.assertEqual(['October 2018'],f['source_date_literals'])
        self.assertIn('U.S. Attorney',f['statement_text'])

    def test_current_response_is_distinct_from_receipt(self):
        p=prepare(**args('We are cooperating fully with the DOJ inquiry.'))
        self.assertTrue(any(f['rule_id']=='CURRENT_COOPERATION' and f['current_status_asserted'] for f in facts(p)))
        p=prepare(**args('On an ongoing basis, we vigorously defend ourselves in lawsuits and proceedings and respond to various investigations and inquiries from federal, state, local and international authorities.'))
        self.assertTrue(any(f['rule_id']=='CURRENT_RESPONSE' and f['status']=='SOURCE_REPORTED_FACT' for f in facts(p)))

    def test_mixed_current_and_resolution_is_not_resolved_by_word_precedence(self):
        p=prepare(**args('We are cooperating with the DOJ investigation. Most investigations have been resolved or no longer appear to be active.'))
        f=next(f for f in facts(p) if f['rule_id']=='CURRENT_COOPERATION')
        self.assertEqual('SEMANTIC_REVIEW_REQUIRED',f['status']);self.assertFalse(f['current_status_asserted'])
        self.assertFalse(p['not_disclosed_confirmed'])
        self.assertIn('PARTIAL_RESOLUTION',p['candidates'][0]['language_signals'])

    def test_resolution_after_receipt_keeps_event_but_never_assumes_it_is_open(self):
        p=prepare(**args('In June 2020, we received a subpoena from the SEC. The matter was resolved in July 2021.'))
        self.assertEqual(1,p['supported_fact_count']);self.assertFalse(facts(p)[0]['current_status_asserted'])
        self.assertIn('RESOLUTION',p['candidates'][0]['language_signals'])

    def test_hypothetical_negated_or_mixed_future_is_not_an_actual_fact(self):
        for text in ['If we received a subpoena from the SEC, costs could increase.',
                     'We have not received a subpoena from the SEC.',
                     'We are, or may become, involved in government investigations.',
                     'We could be subject to regulatory investigations.',
                     'We are involved in government investigations if an authority opens an inquiry.']:
            with self.subTest(text=text):
                p=prepare(**args(text));self.assertEqual(0,p['supported_fact_count']);self.assertFalse(p['not_disclosed_confirmed'])

    def test_third_party_private_and_internal_words_do_not_prove_registrant_target(self):
        for text in ['Our supplier received a subpoena from the DOJ.',
                     'We received a subpoena from our customer in private litigation.',
                     'We are involved in government investigations of our suppliers.',
                     'A Special Litigation Committee conducted an internal investigation.',
                     'Our supplier stated, “We are involved in government investigations.”']:
            with self.subTest(text=text):self.assertEqual(0,prepare(**args(text))['supported_fact_count'])

    def test_authority_mention_elsewhere_does_not_make_private_actor_regulatory(self):
        for text in ['We received a subpoena from Delta, a customer whose other proceedings involve government investigations.',
                     'We are cooperating with private counsel in a lawsuit that discusses SEC investigations.',
                     'We are responding to inquiries by private counsel regarding information from SEC investigators.',
                     'A private plaintiff issued a subpoena to Example Incorporated in a case concerning SEC investigations.']:
            with self.subTest(text=text):
                p=prepare(**args(text));self.assertEqual(0,p['supported_fact_count'])
                self.assertTrue(p['candidates']);self.assertFalse(p['not_disclosed_confirmed'])

    def test_generic_regulation_and_no_hits_do_not_mean_no_investigation(self):
        for text in ['We comply with regulatory requirements and enforcement priorities.',
                     'Economic conditions affect our business.']:
            p=prepare(**args(text));self.assertEqual(0,p['supported_fact_count']);self.assertFalse(p['not_disclosed_confirmed'])
            self.assertFalse(p['semantic_scope_completeness_asserted'])

    def test_quoted_or_reported_present_tense_does_not_assert_registrant_current_status(self):
        for introduction in ['The following quotation is from our 2018 annual report; the inquiry was closed in 2019.',
                             'Our supplier Delta provided this statement about its own investigation:',
                             'If the DOJ opened an inquiry, our hypothetical response would be:']:
            text = introduction + '</p><blockquote><p>We are cooperating with the DOJ inquiry.</p></blockquote><p>End of quotation.'
            with self.subTest(introduction=introduction):
                p = prepare(**args(text))
                self.assertEqual(0, p['supported_fact_count'])
                self.assertFalse(any(f['current_status_asserted'] or f['authority_to_action_relation_proven'] for f in facts(p)))
        p = prepare(**args('Our supplier stated:</p><p>We are cooperating with the DOJ inquiry.'))
        self.assertEqual(0, p['supported_fact_count'])

    def test_adjacent_linked_closure_does_not_become_current_open_status(self):
        p = prepare(**args('We are cooperating with the DOJ inquiry.</p><p>This inquiry was closed in January 2021.'))
        self.assertEqual(0, p['supported_fact_count'])
        self.assertFalse(any(f['current_status_asserted'] for f in facts(p)))
        p = prepare(**args('We are cooperating with the DOJ inquiry.</p><p>An unrelated private contract dispute was closed in 2021.'))
        self.assertEqual(1, p['supported_fact_count'])

    def test_agency_reporting_or_denying_a_private_action_is_not_issuing_process(self):
        for sentence in ['The SEC reported that private plaintiff Delta issued a subpoena to Example Incorporated.',
                         'The SEC denied that it issued a subpoena to Example Incorporated.']:
            raw = annual(BODY.replace('If a regulator conducts an investigation, our expenses could increase.', sentence))
            raw = raw.replace(b'</ix:hidden>', b'<ix:nonNumeric name="dei:EntityRegistrantName" contextRef="annual">Example Incorporated</ix:nonNumeric></ix:hidden>')
            with self.subTest(sentence=sentence):
                p = prepare(**source_arguments(raw))
                self.assertEqual(0, p['supported_fact_count'])

    def test_government_word_inside_a_private_company_is_not_an_agency(self):
        p = prepare(**args('We received a subpoena from Government Employees Insurance Company, a private insurer, in its contract lawsuit.'))
        self.assertEqual(0, p['supported_fact_count'])
        self.assertTrue(p['candidates'])

    def test_cooperation_on_a_conference_is_not_a_regulatory_process(self):
        p = prepare(**args('We are cooperating with the SEC on its conference about enforcement practices.'))
        self.assertEqual(0, p['supported_fact_count'])
        self.assertFalse(any(f['current_status_asserted'] for f in facts(p)))

    def test_toc_and_outside_range_mentions_cannot_supply_supported_facts(self):
        p=prepare(**args('Economic conditions affect our business.',prefix='<p><a href="#legal">SEC investigations</a></p><p>We are involved in government investigations.</p>'))
        self.assertEqual(0,p['supported_fact_count']);self.assertTrue(p['outside_requested_range_action_candidates'])
        self.assertFalse(any(c['excerpt']['text']=='SEC investigations' for c in p['candidates']))

    def test_unresolved_note_or_truncated_document_does_not_gain_complete_credit(self):
        a=args('We are involved in government investigations.');raw=a['raw_bytes'].replace(b'Refer to Note 2',b'Refer to Note 8');a=source_arguments(raw)
        p=prepare(**a);self.assertEqual('INCOMPLETE',p['coverage_status']);self.assertEqual(0,p['supported_fact_count'])
        p=prepare(**source_arguments(raw.replace(b'</body></html>',b'')))
        self.assertEqual(0,p['supported_fact_count']);self.assertFalse(p['not_disclosed_confirmed'])

    def test_company_alias_requires_explicit_definition_of_same_dei_name(self):
        raw=annual('<p>Example Incorporated (“the Company”) refers to the registrant.</p>'+BODY.replace('If a regulator conducts an investigation, our expenses could increase.','The Company is cooperating with the DOJ inquiry.'))
        raw=raw.replace(b'</ix:hidden>',b'<ix:nonNumeric name="dei:EntityRegistrantName" contextRef="annual">Example Incorporated</ix:nonNumeric></ix:hidden>')
        p=prepare(**source_arguments(raw));self.assertEqual(1,p['supported_fact_count'])
        raw=raw.replace(b'Example Incorporated (',b'Unrelated Incorporated (')
        self.assertEqual(0,prepare(**source_arguments(raw))['supported_fact_count'])

    def test_quoted_transaction_and_share_class_do_not_become_entity_aliases(self):
        for definition in ['Example Incorporated (“Transactions”, and the “Company”)',
                           'Example Incorporated (shares of the “Company”)',
                           'Example Incorporated (“Example Incorporated Class A Common Stock”)']:
            raw=annual('<p>'+definition+'</p>'+BODY.replace('If a regulator conducts an investigation, our expenses could increase.','The Company is cooperating with the DOJ inquiry.'))
            raw=raw.replace(b'</ix:hidden>',b'<ix:nonNumeric name="dei:EntityRegistrantName" contextRef="annual">Example Incorporated</ix:nonNumeric></ix:hidden>')
            with self.subTest(definition=definition):self.assertEqual(0,prepare(**source_arguments(raw))['supported_fact_count'])

    def test_regulator_process_to_exact_name_preserves_receipt_without_open_status(self):
        raw=annual(BODY.replace('If a regulator conducts an investigation, our expenses could increase.',
            'The FCC’s Enforcement Bureau issued a Letter of Inquiry to Example Incorporated regarding its certifications.'))
        raw=raw.replace(b'</ix:hidden>',b'<ix:nonNumeric name="dei:EntityRegistrantName" contextRef="annual">Example Incorporated</ix:nonNumeric></ix:hidden>')
        p=prepare(**source_arguments(raw));f=next(f for f in facts(p) if f['rule_id']=='ISSUED_PROCESS_TO_NAMED_ENTITY')
        self.assertEqual('SOURCE_REPORTED_FACT',f['status']);self.assertFalse(f['current_status_asserted'])
        self.assertEqual('Example Incorporated',f['subject_binding']['text'])
        raw=raw.replace(b'to Example Incorporated regarding',b'to Unrelated Incorporated regarding')
        self.assertEqual(0,prepare(**source_arguments(raw))['supported_fact_count'])

    def test_json_replay_and_utf8_block_locators_reject_rehashed_semantic_edits(self):
        a=args('We are cooperating with the DOJ inquiry regarding café transactions.');p=prepare(**a)
        self.assertEqual(p,replay(bundle=json.loads(json.dumps(p)),**a))
        c=next(c for c in p['candidates'] if c['facts']);e=c['excerpt'];span=c['facts'][0]['visible_block_character_span']
        self.assertEqual(c['facts'][0]['statement_text'],e['text'][span['start']:span['end']])
        self.assertIn('café'.encode(),a['raw_bytes'][e['raw_start_byte']:e['raw_end_byte']])
        altered=copy.deepcopy(p);altered['candidates'][0]['facts'][0]['current_status_asserted']=False
        altered['candidate_bundle_id']=content_hash(value={k:v for k,v in altered.items() if k!='candidate_bundle_id'})
        with self.assertRaisesRegex(ValueError,'REPLAY_CHANGED'):replay(bundle=altered,**a)

    def test_wrong_source_identity_is_rejected(self):
        a=args('We are involved in government investigations.');a['cik']='54321'
        with self.assertRaises(ValueError):prepare(**a)


if __name__=='__main__':unittest.main()
