"""Read reported standby amounts without fabricating unavailable capacity."""
import unittest
from vnext.b06_bond_leases import (_reported_other_natures, _financing_inventory,
    _current_borrowing_assertions, _supplementary_standby_capacity)

DATES='February 1, 2025 and February 3, 2024'
ZERO='As of '+DATES+', there were no outstanding borrowings under the agreement.'
STANDBY='There were $144 million and $148 million of other standby letters of credit outstanding as of '+DATES+', respectively'
PURCHASE=('Our estimated total purchase obligations, which primarily consist of merchandise purchase obligations and obligations under outsourcing arrangements, '
          'software license and other service commitments, energy and other supply agreements identified by the Company and construction contracts, '
          'were approximately $100 million and $110 million as of '+DATES+', respectively. '
          'These purchase obligations are primarily due within 1 year and recorded as liabilities when goods are received or services rendered.')

def notes(*, capacity=False):
    ending=(', which reduced the available borrowing capacity to $2,856 million and $2,852 million, respectively.' if capacity else '.')
    debt=ZERO+' '+STANDBY+ending
    if capacity:debt+=' The Amendment reduced the asset-based credit facility to $3,000 million.'
    return {'debt':{'text':'<p>'+debt+'</p>'},'commitments':{'text':'<p>'+PURCHASE+'</p>'}}

PREPARED={'filing':{'reportDate':'2025-02-01'},'table_input':{'target_period':{'period_start':'2024-02-04'}}}

class StandbyNoteRelationTest(unittest.TestCase):
    def test_reported_amount_does_not_require_a_disclosed_capacity(self):
        result=_reported_other_natures(notes(),PREPARED)
        self.assertEqual('144000000',result['standby_current'])
        self.assertIsNone(result['unused_capacity'])
        self.assertIsNone(result['facility_limit'])
        self.assertEqual('NOT_REPORTED_IN_SELECTED_DEBT_NOTE',result['capacity_field_scope'])
        self.assertEqual(STANDBY+'.',result['standby_statement'])
        self.assertEqual('100000000',result['purchase_current'])

    def test_existing_reported_capacity_still_reconciles(self):
        result=_reported_other_natures(notes(capacity=True),PREPARED)
        self.assertEqual({'revolver_zero_statement':ZERO,'standby_statement':STANDBY+
            ', which reduced the available borrowing capacity to $2,856 million and $2,852 million, respectively.',
            'standby_current':'144000000','unused_capacity':'2856000000','facility_limit':'3000000000',
            'purchase_statement':PURCHASE,'purchase_current':'100000000'},result)

    def test_purchase_punctuation_does_not_change_nature_or_numbers(self):
        source=notes();source['commitments']['text']=source['commitments']['text'].replace('Company and construction','Company, and construction')
        result=_reported_other_natures(source,PREPARED)
        self.assertEqual('100000000',result['purchase_current'])
        self.assertIn('Company, and construction',result['purchase_statement'])
        source['commitments']['text']=source['commitments']['text'].replace('when goods are received or services rendered','under a borrowing agreement')
        with self.assertRaisesRegex(ValueError,'PURCHASE_GOODS_SERVICES_RECOGNITION_UNPROVEN'):
            _reported_other_natures(source,PREPARED)

    def test_reported_retirement_expense_is_not_a_principal_balance(self):
        sentence=('The Company recognized $1 million of losses on early retirement of debt '
                  'on the Consolidated Statements of Income during the third quarter of 2024.')
        source={role:{'text':''} for role in ('debt','lease_classification','fair_value','commitments')}
        source['debt']['text']='<p>'+sentence+'</p>'
        rows=_current_borrowing_assertions(source,PREPARED,{'revolver_zero_statement':ZERO,'standby_statement':STANDBY+'.'})
        self.assertEqual('REPORTED_INCOME_STATEMENT_DEBT_EXTINGUISHMENT_EXPENSE',rows[0]['disposition'])
        source['debt']['text']='<p>'+sentence[:-1]+', and $1 million principal remains outstanding.</p>'
        with self.assertRaisesRegex(ValueError,'CURRENT_BORROWING_ASSERTION_UNRESOLVED'):
            _current_borrowing_assertions(source,PREPARED,{'revolver_zero_statement':ZERO,'standby_statement':STANDBY+'.'})

    def test_a_reported_capacity_cannot_lose_its_limit_or_reconciliation(self):
        for old,new,reason in [('$3,000 million','$3,001 million','RECONCILIATION_CONFLICT'),
                               ('The Amendment reduced','The facility formerly had','LIMIT_UNPROVEN')]:
            source=notes(capacity=True);source['debt']['text']=source['debt']['text'].replace(old,new)
            with self.subTest(change=old),self.assertRaisesRegex(ValueError,reason):
                _reported_other_natures(source,PREPARED)

    def test_stale_period_wrong_nature_or_missing_zero_remains_unproved(self):
        for old,new in [(DATES,'February 3, 2024 and January 28, 2023'),
                        ('other standby letters of credit','other outstanding borrowings'),
                        (ZERO,'Borrowings were reported elsewhere.')]:
            source=notes();source['debt']['text']=source['debt']['text'].replace(old,new)
            with self.subTest(change=old),self.assertRaises(ValueError):
                _reported_other_natures(source,PREPARED)

    def test_unknown_capacity_description_cannot_match_a_shortened_sentence(self):
        source=notes();source['debt']['text']=source['debt']['text'].replace('respectively.','respectively, which has unverified capacity.')
        with self.assertRaisesRegex(ValueError,'STANDBY_CAPACITY_NATURE_UNPROVEN'):
            _reported_other_natures(source,PREPARED)

    def test_a_native_capacity_cannot_be_cleared_without_a_reported_relation(self):
        from tests.vnext.test_bond_maturity_sections import fixture
        _,_,args=fixture()
        for source in (args['primary'],args['xml']):
            source['raw_bytes']=source['raw_bytes'].replace(b'DebtCurrent',b'LineOfCreditFacilityRemainingBorrowingCapacity')
        composition={'lease':{'maturity':{},'finance_reports':{}},'balance_reports':{},
                     'supplier':{'native_reports':{}}}
        with self.assertRaisesRegex(ValueError,'UNUSED_CAPACITY_SOURCE_RELATION_UNPROVEN'):
            _financing_inventory(**args,composition=composition,members=[],
                other={'unused_capacity':None})

    def test_standard_word_zero_for_a_second_credit_line_is_parsed_and_cross_checked(self):
        from tests.vnext.test_bond_maturity_sections import fixture
        from vnext.deterministic_router import parse_accession_xbrl_source
        _,_,args=fixture()
        primary=args['primary']['raw_bytes'].replace(b'DebtCurrent',b'LineOfCredit')
        primary=primary.replace(b'<html ',b'<html xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12" ')
        primary=primary.replace(b'name="us-gaap:LineOfCredit"',b'format="ixt:fixed-zero" name="us-gaap:LineOfCredit"')
        primary=primary.replace(b'scale="6">6</ix:nonFraction>',b'scale="6">no</ix:nonFraction>',1)
        args['primary']['raw_bytes']=primary
        args['xml']['raw_bytes']=args['xml']['raw_bytes'].replace(b'DebtCurrent',b'LineOfCredit').replace(b'>6000000<',b'>0<',1)
        represented={kind:[{'ordinal':fact['ordinal']} for fact in
            parse_accession_xbrl_source(raw_bytes=args[kind]['raw_bytes']).facts
            if fact['qualified_name'].split(':')[-1].casefold()=='debtinstrumentcarryingamount']
            for kind in ('primary','xml')}
        composition={'lease':{'maturity':{},'finance_reports':{}},
            'balance_reports':{'other':represented},
            'supplier':{'native_reports':{}}}
        other={'revolver_zero_statement':ZERO}
        result=_financing_inventory(**args,composition=composition,members=[],other=other)
        self.assertEqual('0',result['primary'][0]['value'])
        self.assertEqual('EXPLICIT_CURRENT_ZERO',result['primary'][0]['disposition'])
        for old,new in [(b'inlineXBRL/transformation/2020-02-12',b'not-a-transformation/2020-02-12'),
                        (b'ixt:fixed-zero',b'ixt:numdash'),
                        (b'format="ixt:fixed-zero"',b'sign="+" format="ixt:fixed-zero"')]:
            args['primary']['raw_bytes']=primary.replace(old,new)
            with self.subTest(change=old),self.assertRaisesRegex(ValueError,'REVOLVER_NATIVE_WORD_ZERO_UNPROVEN'):
                _financing_inventory(**args,composition=composition,members=[],other=other)
        args['primary']['raw_bytes']=primary
        args['xml']['raw_bytes']=args['xml']['raw_bytes'].replace(b'>0<',b'>9000000<',1)
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_FINANCING_FACT|PRECISION_CONFLICT'):
            _financing_inventory(**args,composition=composition,members=[],other=other)


class SupplementaryCapacityTest(unittest.TestCase):
    statement=('Also, the Company is party to the ABL Credit Facility with certain financial institutions providing for a $3,000 million Revolving ABL Facility. '
        'As of February 1, 2025, borrowing capacity of the ABL Credit Facility was $2,856 million, which reflects a $144 million reduction due to standby letters '
        'of credit outstanding and borrowing availability was $2,459 million, which considers a further $397 million reduction due to inventory levels and its impact on the ABL borrowing base.')

    def primary(self,text=None,heading='Liquidity and Capital Resources',quoted=False):
        from hashlib import sha256
        body=self.statement if text is None else text
        if quoted:body='<blockquote>'+body+'</blockquote>'
        raw=('<html><body><p>'+heading+'</p><p>'+body+'</p><p>Item 8. Financial Statements.</p></body></html>').encode()
        return {'raw_bytes':raw,'raw_blob':{'raw_asset_id':'sha256:'+sha256(raw).hexdigest()},
                'source_reference':{'constructed':True}}

    def test_note_absence_retains_the_full_annual_relationship(self):
        from hashlib import sha256
        primary=self.primary();result=_supplementary_standby_capacity(primary,PREPARED,{'standby_current':'144000000'})
        self.assertEqual(('3000000000','2856000000','2459000000','397000000'),tuple(result[k] for k in
            ('facility_limit','borrowing_capacity','borrowing_availability','inventory_reduction')))
        span=primary['raw_bytes'][result['raw_start_byte']:result['raw_end_byte']]
        self.assertEqual(sha256(span).hexdigest(),result['raw_span_sha256'])
        self.assertIn(b'$2,459 million',span)
        primary['raw_bytes']=b'\xef\xbb\xbf'+primary['raw_bytes']
        shifted=_supplementary_standby_capacity(primary,PREPARED,{'standby_current':'144000000'})
        self.assertEqual(result['raw_start_byte']+3,shifted['raw_start_byte'])

    def test_conflicting_capacity_or_note_amount_is_not_silently_ignored(self):
        for source,other in [(self.primary(self.statement.replace('$2,459','$2,458')),{'standby_current':'144000000'}),
                             (self.primary(),{'standby_current':'145000000'})]:
            with self.subTest(change=other),self.assertRaisesRegex(ValueError,'CAPACITY_CONFLICT'):
                _supplementary_standby_capacity(source,PREPARED,other)

    def test_wrong_period_region_quote_or_duplicate_cannot_supply_scope(self):
        cases=(self.primary(self.statement.replace('February 1, 2025','February 3, 2024')),
               self.primary(heading='Human Capital Resources'),self.primary(quoted=True),
               self.primary(self.statement+'</p><p>'+self.statement))
        for primary in cases:
            with self.subTest(source=primary),self.assertRaisesRegex(ValueError,'CAPACITY_RELATION_UNPROVEN'):
                _supplementary_standby_capacity(primary,PREPARED,{'standby_current':'144000000'})
