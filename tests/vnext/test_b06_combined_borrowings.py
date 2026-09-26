"""Actual combined-note borrowing proof and materially different source cases."""
import copy
import hashlib
import re
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.b06_combined_borrowings import prepare_saved_combined_borrowings, inspect_combined_borrowings, _table, POLICY
from vnext.normal_candidates import _prepare_b06
from vnext.sources import source_reference_record
from vnext.fiscal_year_labels import _DefinitionBlocks
from vnext.annual_update import saved_source
from vnext.normal_source_authority import verify_saved_source_proofs
from vnext.deterministic_router import parse_accession_xbrl_source


class CombinedBorrowingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with original_sources_only():
            cls.preparation = _prepare_b06(repo_root=ROOT, company_id='pfizer')
            cls.actual = prepare_saved_combined_borrowings(repo_root=ROOT, company_id='pfizer')

    def arguments(self):
        p = self.preparation
        return copy.deepcopy({'primary':p['primary'],'xml':p['xml'],
            'prepared':p['input_binding']['prepared_annual_input']})

    def change(self,args,kind,transform):
        item = args[kind]
        raw = transform(item['raw_bytes'])
        self.assertTrue(raw != item['raw_bytes'], 'Mutation did not alter the source')
        blob = {**item['raw_blob'],'raw_asset_id':'sha256:'+hashlib.sha256(raw).hexdigest(),'byte_length':len(raw)}
        old = item['source_reference']
        ref = source_reference_record(raw_blob=blob,company_id=old['company_id'],source_url=old['source_url'],
            accession=old['accession'],document_name=old['document_name'],source_role=old['source_role'],
            request_attempt_id=old['request_attempt_id'])
        args[kind] = {**item,'raw_bytes':raw,'raw_blob':blob,'source_reference':ref}

    def inspect(self,args):
        with original_sources_only():
            return inspect_combined_borrowings(**args)

    def test_actual_carrying_amounts_keep_current_debt_once_and_remaining_scope_explicit(self):
        p = self.actual['reconciliation']
        self.assertEqual('64795000000',p['proven_borrowing_subtotal'])
        self.assertEqual('3154000000',p['native_reports']['short']['chosen']['value'])
        self.assertEqual('61641000000',p['native_reports']['noncurrent']['chosen']['value'])
        self.assertEqual('NOT_PROVEN',p['debt_completeness'])
        self.assertEqual(['finance_leases'],p['not_evaluated_classes'])
        self.assertFalse(p['metric_result_created'])
        self.assertFalse(p['source_acquisition_credit'])
        self.assertFalse(self.actual['native_run_created'])
        self.assertEqual({'provider':0,'paid':0,'sec':0},self.actual['calls'])
        self.assertEqual({'short','noncurrent','current_long','other_short'},set(self.actual['same_filing_companyfacts']))
        self.assertEqual(2,p['long_table']['table_count_in_note'])
        rounded = next(c for c in p['reconciliations'] if c['check']=='LONG_MATURITY_MEMBERS')
        self.assertEqual('1000000',rounded['difference'])
        self.assertEqual('DECLARED_ROUNDING_INTERVALS_OVERLAP',rounded['agreement'])
        self.assertTrue(any(r['value']=='62000000000' for r in p['native_reports']['noncurrent']['primary']))

    def test_current_portion_cannot_be_relabelled_as_already_included_in_long_total(self):
        args = self.arguments()
        for kind in ['primary','xml']:
            self.change(args,kind,lambda raw:raw.replace(b'not included above',b'included above'))
        with self.assertRaisesRegex(ValueError,'UNRECONCILED_TABLE_ROW'):
            self.inspect(args)

    def test_current_long_balance_label_must_name_actual_period(self):
        args = self.arguments()
        self.change(args,'primary',lambda raw:raw.replace(b'debt: 2025&#8212;$',b'debt: 2024&#8212;$',1))
        with self.assertRaisesRegex(ValueError,'CURRENT_LONG_LABEL_PERIOD_UNPROVEN'):
            self.inspect(args)

    def test_narrative_rounding_cannot_hide_incompatible_long_debt(self):
        args = self.arguments()
        pattern=rb'(<ix:nonFraction\b(?=[^>]*name="us-gaap:LongTermDebtNoncurrent")(?=[^>]*decimals="-9")[^>]*>)62(</ix:nonFraction>)'
        self.change(args,'primary',lambda raw:re.sub(pattern,lambda m:m[1]+b'66'+m[2],raw,count=1))
        with self.assertRaisesRegex(ValueError,'REPORTING_PRECISION_CONFLICT'):
            self.inspect(args)

    def test_missing_rounding_statement_does_not_relax_member_reconciliation(self):
        args = self.arguments()
        for kind in ['primary','xml']:
            self.change(args,kind,lambda raw:raw.replace(b'may not add due to rounding',b'must add exactly without rounding'))
        with self.assertRaisesRegex(ValueError,'RECONCILIATION_FAILED:LONG_MATURITY_MEMBERS'):
            self.inspect(args)

    def test_quoted_rounding_statement_cannot_relax_current_note_reconciliation(self):
        args = self.arguments()
        statement = self.actual['reconciliation']['source_rounding_statement'][0]['text']
        def quote(raw):
            text = raw.decode('utf-8-sig')
            blocks = _DefinitionBlocks(text)
            blocks.feed(text);blocks.close();blocks._flush()
            block = next(b for b in blocks.blocks if b['text'] == statement)
            return (text[:block['start']]+'<q>'+text[block['start']:block['end']]+'</q>'+text[block['end']:]).encode()
        self.change(args,'primary',quote)
        with self.assertRaisesRegex(ValueError,'RECONCILIATION_FAILED:LONG_MATURITY_MEMBERS'):
            self.inspect(args)

    def test_large_member_error_cannot_be_treated_as_rounding(self):
        args = self.arguments()
        for kind in ['primary','xml']:
            self.change(args,kind,lambda raw:raw.replace(b'2,081',b'9,081'))
        with self.assertRaisesRegex(ValueError,'RECONCILIATION_FAILED:LONG_MATURITY_MEMBERS'):
            self.inspect(args)

    def test_unit_namespace_and_concept_namespace_are_semantic_inputs(self):
        for before,after,reason in [
            (b'http://www.xbrl.org/2003/iso4217',b'urn:untrusted-currency','UNIT_CONFLICT'),
            (b'http://fasb.org/us-gaap/2025',b'urn:untrusted-accounting','CONCEPT_NAMESPACE_CONFLICT'),
        ]:
            with self.subTest(reason=reason):
                args=self.arguments()
                for kind in ['primary','xml']:
                    self.change(args,kind,lambda raw:raw.replace(before,after))
                with self.assertRaisesRegex(ValueError,reason):
                    self.inspect(args)

    def test_disagreement_between_original_html_and_instance_is_rejected(self):
        args = self.arguments()
        self.change(args,'xml',lambda raw:raw.replace(b'not included above',b'included above'))
        with self.assertRaisesRegex(ValueError,'FULL_PRIMARY_XML_NOTE_CONFLICT'):
            self.inspect(args)

    def test_original_hash_binding_is_not_bypassed_by_semantic_plausibility(self):
        args = self.arguments();args['primary']['raw_bytes'] += b' '
        with self.assertRaisesRegex(ValueError,'SOURCE_BINDING_CHANGED'):
            self.inspect(args)

    def test_prior_saved_instance_has_an_additional_short_term_adjustment_row(self):
        # The prior primary HTML is not saved. This checks the actual table
        # grammar only, not a complete cross-year input or native Run.
        with original_sources_only():
            source=saved_source(repo_root=ROOT,accession='0000078003-25-000054',
                url='https://www.sec.gov/Archives/edgar/data/78003/000007800325000054/pfe-20241231_htm.xml')
            verify_saved_source_proofs(data_root=ROOT,proofs=[source['proof']])
            parsed=parse_accession_xbrl_source(raw_bytes=source['raw'])
            notes=[f for f in parsed.facts if f['qualified_name'].casefold()=='us-gaap:scheduleofshorttermdebttextblock'
                   and parsed.contexts[f['context_ref']]['period_end']=='2024-12-31'
                   and not parsed.contexts[f['context_ref']]['dimensions']]
            self.assertEqual(1,len(notes))
            table=_table({'fact':notes[0]},POLICY['short_labels'],'2024-12-31',
                         optional_roles=POLICY['optional_short_roles'])
        roles=table['roles']
        self.assertEqual('0',roles['fair_value_adjustment']['value'])
        self.assertEqual('-12000000',roles['adjustment']['value'])
        self.assertEqual('6957000000',roles['principal']['value'])
        self.assertEqual('6946000000',roles['carrying']['value'])


if __name__=='__main__':
    unittest.main()
