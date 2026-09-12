"""Actual separate lease classifications before debt-set integration."""
import copy
import hashlib
import re
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.b06_bond_leases import inspect_separate_finance_leases, inspect_supplier_payment_terms, inspect_bond_debt_scope, _notes, _lease_maturity
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.normal_candidates import _prepare_b06
from vnext.normal_source_authority import verify_saved_source_proofs
from vnext.sources import source_reference_record


class SeparateLeaseSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with original_sources_only():
            p = _prepare_b06(repo_root=ROOT,company_id='macys')
            verify_saved_source_proofs(data_root=ROOT,proofs=p['input_binding']['source_proofs'])
            cls.args = {'primary':p['primary'],'xml':p['xml'],'prepared':p['input_binding']['prepared_annual_input']}
            cls.actual = inspect_separate_finance_leases(**cls.args)

    def changed(self,kind,transform,args=None):
        args = args or copy.deepcopy(self.args); item = args[kind]; raw = transform(item['raw_bytes'])
        self.assertTrue(raw != item['raw_bytes'],'Mutation must change the intended original source')
        blob = {**item['raw_blob'],'raw_asset_id':'sha256:'+hashlib.sha256(raw).hexdigest(),'byte_length':len(raw)}
        old = item['source_reference']
        ref = source_reference_record(raw_blob=blob,company_id=old['company_id'],source_url=old['source_url'],
            accession=old['accession'],document_name=old['document_name'],source_role=old['source_role'],request_attempt_id=old['request_attempt_id'])
        args[kind] = {**item,'raw_bytes':raw,'raw_blob':blob,'source_reference':ref}; return args

    def inspect(self,args):
        with original_sources_only(): return inspect_separate_finance_leases(**args)

    def test_actual_current_noncurrent_and_payment_reconciliation(self):
        p = self.actual
        self.assertEqual('13000000',p['recognized_finance_lease'])
        self.assertEqual({'current':'2000000','noncurrent':'11000000'},
                         {k:v['value'] for k,v in p['classification']['selected'].items()})
        self.assertEqual({'payments':'19000000','interest':'6000000','total':'13000000'},
                         {k:v['value'] for k,v in p['maturity']['totals'].items()})
        self.assertEqual(3,p['maturity']['table_count_in_note'])
        self.assertFalse(p['complete_b06_proven']); self.assertFalse(p['separate_from_bond_debt_proven'])
        self.assertFalse(p['source_acquisition_credit']); self.assertFalse(p['production_authorized'])

    def test_classification_cannot_move_the_finance_lease_into_the_debt_line(self):
        args = copy.deepcopy(self.args)
        for kind in ['primary','xml']:
            args = self.changed(kind,lambda raw:raw.replace(b'Long-Term Lease Liabilities',b'Long-Term Debt'),args)
        with self.assertRaisesRegex(ValueError,'FINANCE_STATEMENT_CLASS_UNPROVEN'): self.inspect(args)

    def test_finance_column_cannot_be_replaced_by_operating_column(self):
        note = dict(_notes(**self.args)['lease_maturity'])
        changed = re.sub(r'(?<=>)Finance(?=<)', 'Operating',note['text'])
        self.assertTrue(changed != note['text'],'Change only the displayed column header')
        note['text'] = changed
        with self.assertRaisesRegex(ValueError,'MATURITY_TABLE_NOT_UNIQUE'):
            _lease_maturity(note,self.actual['finance_reports'],self.args['prepared'])

    def test_native_amount_disagreement_is_retained(self):
        args = self.changed('xml',lambda raw:raw.replace(b'>11000000<',b'>31000000<'))
        with self.assertRaisesRegex(ValueError,'PRECISION_CONFLICT'): self.inspect(args)

    def test_visible_maturity_date_and_scale_are_required(self):
        transform = lambda raw:raw.replace(b'31, 2026, the maturity',b'31, 2025, the maturity')
        args = self.changed('xml',transform)
        args = self.changed('primary',transform,args)
        with self.assertRaisesRegex(ValueError,'MATURITY_AS_OF_UNPROVEN'): self.inspect(args)
        args = copy.deepcopy(self.args)
        for kind in ['primary','xml']:
            args = self.changed(kind,lambda raw:raw.replace(b'(millions)',b'(thousands)'),args)
        with self.assertRaisesRegex(ValueError,'SCALE_UNPROVEN'): self.inspect(args)


class SupplierPaymentTermsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with original_sources_only():
            p = _prepare_b06(repo_root=ROOT,company_id='macys')
            verify_saved_source_proofs(data_root=ROOT,proofs=p['input_binding']['source_proofs'])
            cls.args = {'primary':p['primary'],'xml':p['xml'],'prepared':p['input_binding']['prepared_annual_input']}
            cls.actual = inspect_supplier_payment_terms(**cls.args)

    changed = SeparateLeaseSourceTest.changed

    def inspect(self,args):
        with original_sources_only(): return inspect_supplier_payment_terms(**args)

    def test_actual_program_is_classified_by_unchanged_company_terms_and_reported_trade_payable(self):
        p = self.actual
        self.assertEqual('79000000',p['reported_outstanding'])
        self.assertEqual({'opening':'116000000','confirmed':'641000000','paid':'-678000000','closing':'79000000'},
                         {k:v['value'] for k,v in p['table_rows'].items()})
        self.assertEqual('EXCLUDED_REPORTED_ORDINARY_TRADE_PAYABLE_WITH_UNCHANGED_COMPANY_TERMS',p['debt_set_disposition'])
        self.assertFalse(p['whole_b06_proven']); self.assertFalse(p['source_acquisition_credit'])

    def test_changed_payment_terms_or_company_participation_cannot_retain_trade_exclusion(self):
        for before,after in [(b'are not impacted by',b'are extended by'),
                             (b'is not party to the agreements',b'is party to the agreements'),
                             (b'merchandise accounts payable',b'short-term debt')]:
            with self.subTest(change=before):
                args = copy.deepcopy(self.args)
                for kind in ['primary','xml']:
                    args = self.changed(kind,lambda raw:raw.replace(before,after),args)
                with self.assertRaisesRegex(ValueError,'SUPPLIER_PAYMENT_TERMS_UNPROVEN_OR_CHANGED'): self.inspect(args)

    def test_extra_program_obligation_clause_is_not_dropped(self):
        args = copy.deepcopy(self.args)
        for kind in ['primary','xml']:
            args = self.changed(kind,lambda raw:raw.replace(b'The following table sets forth the changes',
                b'The Company also owes the financing bank an additional loan. The following table sets forth the changes'),args)
        with self.assertRaisesRegex(ValueError,'SUPPLIER_PAYMENT_TERMS_UNPROVEN_OR_CHANGED'): self.inspect(args)

    def test_terms_quote_is_not_an_issuer_assertion(self):
        clause = b"The Company's obligations to its suppliers, including amounts due and scheduled payment terms, are not impacted by a supplier's participation in the SCF programs."
        args = self.changed('primary',lambda raw:raw.replace(clause,b'<blockquote>'+clause+b'</blockquote>'))
        with self.assertRaisesRegex(ValueError,'SUPPLIER_TERMS_ASSERTION_NOT_CURRENT_ISSUER'): self.inspect(args)

    def test_changed_native_closing_amount_cannot_use_old_table(self):
        args = self.changed('xml',lambda raw:raw.replace(b'>79000000<',b'>89000000<'))
        with self.assertRaisesRegex(ValueError,'PRECISION_CONFLICT|AMOUNT_CONFLICT'): self.inspect(args)


class BondDebtScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with original_sources_only():
            p = _prepare_b06(repo_root=ROOT,company_id='macys')
            verify_saved_source_proofs(data_root=ROOT,proofs=p['input_binding']['source_proofs'])
            cls.args = {'primary':p['primary'],'xml':p['xml'],'prepared':p['input_binding']['prepared_annual_input']}
            cls.actual = inspect_bond_debt_scope(**cls.args)

    changed = SeparateLeaseSourceTest.changed

    def inspect(self,args):
        with original_sources_only(): return inspect_bond_debt_scope(**args)

    def test_full_reported_composition_preserves_supplier_and_nonlease_subsets(self):
        p = self.actual
        self.assertTrue(p['complete_b06_proven'])
        self.assertEqual('2445000000',p['proven_composition_amount'])
        self.assertEqual('2432000000',p['bonds']['reported_borrowing'])
        self.assertEqual('13000000',p['lease']['recognized_finance_lease'])
        self.assertEqual('79000000',p['supplier']['reported_outstanding'])
        self.assertEqual(21,len(p['native_bond_members']))
        self.assertEqual('2307000000',p['fair_value']['columns']['fair_value']['value'])
        self.assertEqual('143000000',p['other_reported_natures']['standby_current'])
        self.assertTrue(any(r['disposition']=='NONLEASE_SUBCOMPONENT_NOT_ADDED_TO_COMBINED_REPORTED_FINANCE_LIABILITY'
                            for r in p['independent_financing_inventory']['xml']))
        self.assertFalse(p['source_acquisition_credit']); self.assertFalse(p['production_authorized'])

    def test_dimensioned_additional_borrowing_cannot_escape_inventory(self):
        args = copy.deepcopy(self.args); parsed = parse_accession_xbrl_source(raw_bytes=args['xml']['raw_bytes'])
        fact = next(f for f in parsed.facts if f['qualified_name'].casefold()=='us-gaap:debtinstrumentcarryingamount'
                    and parsed.contexts[f['context_ref']]['period_end']=='2026-01-31')
        added = ('<us-gaap:ShortTermBorrowings contextRef="'+fact['context_ref']+'" unitRef="'+fact['unit_ref']+'" decimals="-6">17000000</us-gaap:ShortTermBorrowings>').encode()
        args = self.changed('xml',lambda raw:raw.replace(b'</xbrl>',added+b'</xbrl>'),args)
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_FINANCING_FACT'): self.inspect(args)

    def test_unquantified_additional_borrowing_is_not_an_absent_amount(self):
        args = copy.deepcopy(self.args)
        for kind in ['primary','xml']:
            args = self.changed(kind,lambda raw:raw.replace(b'Debt Obligations',
                b'Debt Obligations. There are other borrowings not included above. '),args)
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_ADDITIONAL_BORROWING'): self.inspect(args)

    def test_unknown_native_nonlease_change_is_not_hidden_by_unchanged_total(self):
        args = copy.deepcopy(self.args)
        pattern = rb'(<m:FinanceLeaseLiabilityNonLeaseComponentNoncurrent\b[^>]*>)1000000(</m:FinanceLeaseLiabilityNonLeaseComponentNoncurrent>)'
        args = self.changed('xml',lambda raw:re.sub(pattern,lambda m:m[1]+b'2000000'+m[2],raw),args)
        with self.assertRaisesRegex(ValueError,'PRECISION_CONFLICT'): self.inspect(args)

    def test_current_revolver_statement_must_prove_no_borrowings(self):
        args = copy.deepcopy(self.args)
        for kind in ['primary','xml']:
            args = self.changed(kind,lambda raw:raw.replace(b'outstanding borrowings under the agreement',
                b'undisclosed borrowings under the agreement'),args)
        with self.assertRaisesRegex(ValueError,'REVOLVER_CURRENT_ZERO_UNPROVEN'): self.inspect(args)

    def test_future_purchase_commitment_cannot_be_relabelled_as_financed_debt(self):
        args = copy.deepcopy(self.args)
        for kind in ['primary','xml']:
            args = self.changed(kind,lambda raw:raw.replace(b'when goods are received or services rendered',
                b'when the financing loans are drawn'),args)
        with self.assertRaisesRegex(ValueError,'PURCHASE_GOODS_SERVICES_RECOGNITION_UNPROVEN'): self.inspect(args)

    def test_actual_comparative_current_debt_is_included_in_the_new_reconciliation(self):
        # These are prior-period facts reported in the same actual filing,
        # not a claim that the previous year's primary document was fetched.
        from vnext.b06_disclosure import _facts
        from vnext.canonical import strict_json_file
        from vnext.constraints import evaluate_expression
        from decimal import Decimal
        p = self.args['prepared']; scope = {'entity_scope':'consolidated'}
        target = {'entity':p['entity'],'accession':p['filing']['accessionNumber'],
                  'period_start':'2025-02-01','period_end':'2025-02-01','scope':scope}
        get = _facts(self.args['xml']['raw_bytes'],self.args['xml']['source_reference'],target,p['filing']['filingDate'])
        registry = strict_json_file(path=ROOT/'config/b06_bond_debt_set_v1.json')
        model = registry['debt_set_models']['BOND_CURRENT_NONCURRENT_PLUS_SEPARATE_FINANCE_LEASE']
        # The comparative source has no separate total finance-lease fact;
        # this test covers the borrowing check, whose operands do not use it.
        facts = {role:get(concept)[0] for role,concept in model['inputs'].items() if role != 'finance_lease'}
        check = model['checks'][0]
        facts.update({role:get(concept)[0] for role,concept in check['inputs'].items()})
        values = {k:Decimal(f['value']) for k,f in facts.items()}
        self.assertEqual(Decimal('6000000'),values['current'])
        self.assertEqual(Decimal('2773000000'),values['carrying'])
        self.assertEqual(Decimal('2779000000'),evaluate_expression(expression=check['left'],values=values))
        self.assertEqual(Decimal('2779000000'),evaluate_expression(expression=check['right'],values=values))


if __name__ == '__main__': unittest.main()
