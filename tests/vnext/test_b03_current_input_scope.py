"""Finite D&A scope boundaries and actual current source-only result delivery."""
from decimal import Decimal
from pathlib import Path
import shutil
import json
from copy import deepcopy
from unittest.mock import patch
import tempfile
import unittest
from types import SimpleNamespace

from tests.vnext.common import REPO_ROOT
from vnext.ordinary_b03_input_scope import inspect_depreciation_input
from vnext.ordinary_saved_result import create_saved_result, read_saved_result
from vnext.normal_annual_input import prepare_saved_annual_input
from vnext.deterministic_router import shared_xbrl_parses
from vnext.annual_amendment_scope import prepare_saved_amendment_scopes
from vnext.instant_balance_amendment import prepare_instant_balance_amendment_input

PERIOD={'fiscal_year':2025,'period_start':'2025-01-01','period_end':'2025-12-31'}


def original(facts):
    # Small labelled synthetic input; not a registered company or source claim.
    prefix='''<html xmlns:gaap="http://fasb.org/us-gaap/2025" xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:currency="http://www.xbrl.org/2003/iso4217"><body>'''
    parts=[]
    for index,item in enumerate(facts):
        concept,value,decimals,*extra=item;overrides=extra[0] if extra else {}
        entity=overrides.get('entity','195');start=overrides.get('start','2025-01-01');end=overrides.get('end','2025-12-31')
        currency=overrides.get('unit','USD');scheme=overrides.get('scheme','http://www.sec.gov/CIK')
        segment=''
        if overrides.get('dimension'):
            segment='<xbrli:segment><xbrldi:explicitMember dimension="gaap:SegmentsAxis">gaap:OtherSegmentMember</xbrldi:explicitMember></xbrli:segment>'
        parts.append(f'''<xbrli:context id="c{index}"><xbrli:entity><xbrli:identifier scheme="{scheme}">{entity}</xbrli:identifier>{segment}</xbrli:entity><xbrli:period><xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate></xbrli:period></xbrli:context><xbrli:unit id="u{index}"><xbrli:measure>currency:{currency}</xbrli:measure></xbrli:unit><ix:nonFraction name="gaap:{concept}" contextRef="c{index}" unitRef="u{index}" decimals="{decimals}">{value}</ix:nonFraction>''')
    return (prefix+''.join(parts)+'</body></html>').encode()


def observation(concept,value):
    return {'semantic_role':'depreciation_and_amortization','value':value,
            'source_binding':{'concept':'us-gaap:'+concept}}


class CurrentDaScopeTest(unittest.TestCase):
    def check(self,rows,value='1200000000'):
        return inspect_depreciation_input(raw_bytes=original(rows),entity='195',period=PERIOD,
            observations=[observation('DepreciationDepletionAndAmortization',value)])

    def test_conflicting_subtotal_is_withheld_and_larger_total_not_automatically_taken(self):
        answer=self.check([('DepreciationDepletionAndAmortization','1200000000','-8'),
                           ('DepreciationAndAmortization','3631000000','-6')])
        self.assertEqual(answer['status'],'WITHHOLD')
        self.assertEqual(answer['reason_code'],'B03_DEPRECIATION_AMORTIZATION_SCOPE_UNPROVEN')
        self.assertFalse(answer['complete_business_scope_proven'])

    def test_unsupported_numeric_tag_cannot_confirm_chain_amount(self):
        raw=original([('DepreciationDepletionAndAmortization','138','INF')])
        raw=raw.replace(b'<ix:nonFraction ', b'<wrong:nonFraction xmlns:wrong="http://example.com/not-inline" ')
        raw=raw.replace(b'</ix:nonFraction>', b'</wrong:nonFraction>')
        answer=inspect_depreciation_input(raw_bytes=raw,entity='195',period=PERIOD,
            observations=[observation('DepreciationDepletionAndAmortization','138')])
        self.assertEqual(answer['status'],'WITHHOLD')
        self.assertEqual(answer['why'],'SOURCE_NUMERIC_VALUES_UNRESOLVED')
        self.assertTrue(any('NUMERIC_TAG_NOT_SUPPORTED' in i['reason'] for i in answer['source_numeric_issues']))

    def test_unformatted_comma_is_not_silently_removed_to_confirm_chain(self):
        answer=self.check([('DepreciationDepletionAndAmortization','1,38','INF')],value='138')
        self.assertEqual(answer['status'],'WITHHOLD')
        self.assertTrue(any('NUMERIC_LEXICAL_FORM_NOT_SUPPORTED' in i['reason'] for i in answer['source_numeric_issues']))

    def test_declared_numeric_transform_remains_supported(self):
        raw=original([('DepreciationDepletionAndAmortization','1,200','INF')])
        raw=raw.replace(b'<html ', b'<html xmlns:num="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12" ')
        raw=raw.replace(b'<ix:nonFraction ', b'<ix:nonFraction format="num:num-dot-decimal" ')
        answer=inspect_depreciation_input(raw_bytes=raw,entity='195',period=PERIOD,
            observations=[observation('DepreciationDepletionAndAmortization','1200')])
        self.assertEqual(answer['status'],'KEEP')
        self.assertEqual(answer['source_facts'][0]['value'],'1200')

    def test_nil_keeps_other_evidence_and_gives_a_named_withhold(self):
        raw=original([('DepreciationDepletionAndAmortization','138','INF'),
                      ('DepreciationAndAmortization','','INF')])
        raw=raw.replace(b'<html ', b'<html xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ')
        raw=raw.replace(b'decimals="INF"></ix:nonFraction>', b'decimals="INF" xsi:nil="true"></ix:nonFraction>')
        answer=inspect_depreciation_input(raw_bytes=raw,entity='195',period=PERIOD,
            observations=[observation('DepreciationDepletionAndAmortization','138')])
        self.assertEqual(answer['status'],'WITHHOLD')
        self.assertEqual([f['value'] for f in answer['source_facts']],['138'])
        self.assertTrue(any('NIL_OR_INVALID_SOURCE_VALUE' in i['reason'] for i in answer['source_numeric_issues']))

    def test_numeric_helper_change_affects_b03_configuration_but_not_b01(self):
        from vnext import ordinary_current_update as update
        name='scripts/vnext/reported_monetary_literal.py'
        before={m:update._configuration(REPO_ROOT,'marriott_international',m) for m in ('B01','B03')}
        self.assertIn(name,before['B03']['processing_files'])
        self.assertNotIn(name,before['B01']['processing_files'])
        original_hash=update.sha256_file
        with patch.object(update,'sha256_file',side_effect=lambda *,path:
                'changed-literal-parser' if Path(path).name=='reported_monetary_literal.py' else original_hash(path=path)):
            after={m:update._configuration(REPO_ROOT,'marriott_international',m) for m in ('B01','B03')}
        self.assertNotEqual(before['B03'],after['B03'])
        self.assertEqual(before['B01'],after['B01'])

    def test_reported_precision_agreement_keeps_chain_not_exact_numeric_equality(self):
        answer=self.check([('DepreciationDepletionAndAmortization','1200000000','-8'),
                           ('DepreciationAndAmortization','1234000000','-6')])
        self.assertEqual(answer['status'],'KEEP')
        self.assertEqual(answer['chain_input']['value'],'1200000000')

    def test_only_unique_original_composition_can_retake_a_later_direct_candidate(self):
        answer=self.check([('DepreciationDepletionAndAmortization','10','INF'),
            ('DepreciationAndAmortization','20','INF'),('Depreciation','7','INF'),
            ('AmortizationOfIntangibleAssets','13','INF')],value='10')
        self.assertEqual(answer['status'],'RETAKE');self.assertEqual(answer['concept'],'DepreciationAndAmortization')

    def test_foreign_entity_period_unit_segment_or_namespace_does_not_create_own_total_conflict(self):
        good=('DepreciationDepletionAndAmortization','1200000000','INF')
        for changes in ({'entity':'196'},{'start':'2024-01-01'},{'unit':'GBP'},{'dimension':True}):
            with self.subTest(changes=changes):
                answer=self.check([good,('DepreciationAndAmortization','3631000000','INF',changes)])
                self.assertEqual(answer['status'],'KEEP')
                self.assertEqual(len(answer['source_facts']),1)
        raw=original([good,('DepreciationAndAmortization','3631000000','INF')])
        raw=raw.replace(b'name="gaap:DepreciationAndAmortization"',b'name="foreign:DepreciationAndAmortization"')
        answer=inspect_depreciation_input(raw_bytes=raw,entity='195',period=PERIOD,
            observations=[observation(good[0],good[1])])
        self.assertEqual(answer['status'],'KEEP')

    def test_currency_alias_is_resolved_and_foreign_identifier_scheme_is_not_accepted(self):
        answer=self.check([('DepreciationDepletionAndAmortization','1200000000','INF')])
        self.assertEqual(answer['status'],'KEEP')
        self.assertTrue(answer['source_facts'][0]['context_proof'])
        with self.assertRaises(ValueError):
            self.check([('DepreciationDepletionAndAmortization','1200000000','INF',{'scheme':'https://example.invalid/company'})])

    def test_legal_gaap_prefix_alias_composition_keeps_same_quantity(self):
        rows=[('Depreciation','7','INF'),('AmortizationOfIntangibleAssets','13','INF')]
        observations=[{'semantic_role':role,'value':value,'source_binding':{'concept':'us-gaap:'+concept}}
            for role,concept,value in [('depreciation','Depreciation','7'),('amortization','AmortizationOfIntangibleAssets','13')]]
        alias=original(rows)
        canonical=alias.replace(b'xmlns:gaap=',b'xmlns:us-gaap=').replace(b'name="gaap:',b'name="us-gaap:')
        args=dict(entity='195',period=PERIOD,observations=observations)
        for raw in (alias,canonical):
            answer=inspect_depreciation_input(raw_bytes=raw,**args)
            self.assertEqual(answer['status'],'KEEP')
            self.assertEqual(answer['chain_input']['value'],'20')

    def test_context_policy_alone_changes_update_configuration_and_requires_calculation(self):
        from vnext import ordinary_current_update as update
        from vnext import text_results_v2 as context_rules
        raw=original([('DepreciationDepletionAndAmortization','20','INF')])
        args=dict(raw_bytes=raw,entity='195',period=PERIOD,observations=[observation('DepreciationDepletionAndAmortization','20')])
        self.assertEqual(inspect_depreciation_input(**args)['status'],'KEEP')
        before=update._configuration(REPO_ROOT,'marriott_international','B03')
        self.assertIn('catalog/r6/text_results_v2_policy.json',before['processing_files'])
        changed=deepcopy(context_rules._CAPABILITY_POLICY);changed['cik_identifier_schemes']=['https://www.sec.gov/CIK']
        actual_hash=update.sha256_file
        def changed_hash(*,path):
            return 'changed-policy' if Path(path).name=='text_results_v2_policy.json' else actual_hash(path=path)
        with patch.object(context_rules,'_CAPABILITY_POLICY',changed),patch.object(update,'sha256_file',side_effect=changed_hash):
            with self.assertRaisesRegex(ValueError,'D02_FACT_ENTITY_SCHEME_NOT_PROVEN'):
                inspect_depreciation_input(**args)
            after=update._configuration(REPO_ROOT,'marriott_international','B03')
            self.assertNotEqual(before,after)
            previous={'company_id':'marriott_international','metric_id':'B03','version':'old','configuration':before,'source_census':[],'result_id':'old'}
            saved={'manifest':{'company_id':'marriott_international','metric_id':'B03','source_proofs':[]},'result':{'result_id':'old'}}
            with tempfile.TemporaryDirectory() as temporary,patch.object(update,'_recover',return_value=previous),patch.object(update,'_source_census',return_value=[]),patch.object(update,'read_saved_result',return_value=saved),patch.object(update,'create_saved_result',side_effect=ValueError('TEST_NEW_POLICY_REQUIRES_CURRENT_CALCULATION')) as calculate:
                report=update.run_once(state_root=Path(temporary)/'state',source_root=REPO_ROOT,company_id='marriott_international',metric_id='B03')
                calculate.assert_called_once()
                self.assertNotEqual(report['status'],'NO_SOURCE_CONTENT_CHANGE')

    def test_existing_direct_scope_uses_namespace_alias_and_retains_usd_check(self):
        from vnext.b03_depreciation_scope import assess_direct_depreciation_scope
        from vnext.canonical import sha256_bytes
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path=root/'primary.htm'
            raw=original([('DepreciationDepletionAndAmortization','20','INF')]);path.write_bytes(raw)
            selected={'semantic_role':'depreciation_and_amortization','value':'20',
                'source_binding':{'concept':'us-gaap:DepreciationDepletionAndAmortization','entity':'195','accession':'fixture'}}
            case={'primary_metric_id':'B03','results':{'B03':{'publication':'PUBLISHED','reason_code':'PASS'}},
                'observations':[selected],'target_period':PERIOD,'source_proofs':[{'accession':'fixture','document_name':'primary.htm','request_repo_relative_path':'primary.htm','content_sha256':sha256_bytes(content=raw)}]}
            self.assertFalse(assess_direct_depreciation_scope(case=case,data_root=root)['blocked'])
            foreign=original([('DepreciationDepletionAndAmortization','20','INF',{'unit':'GBP'})]);path.write_bytes(foreign)
            case['source_proofs'][0]['content_sha256']=sha256_bytes(content=foreign)
            with self.assertRaisesRegex(ValueError,'SELECTED_INLINE_FACT_NOT_FOUND'):
                assess_direct_depreciation_scope(case=case,data_root=root)

    def test_company_custom_same_local_name_cannot_displace_legitimate_gaap_composition(self):
        rows=[('Depreciation','7','INF'),('AmortizationOfIntangibleAssets','13','INF')]
        observations=[{'semantic_role':role,'value':value,'source_binding':{'concept':'us-gaap:'+concept}}
            for role,concept,value in [('depreciation','Depreciation','7'),('amortization','AmortizationOfIntangibleAssets','13')]]
        for value in ('7','999'):
            raw=original([*rows,('Depreciation',value,'INF')])
            raw=raw.replace(b'<body>',b'<body xmlns:company="https://example.invalid/company">')
            needle=b'name="gaap:Depreciation" contextRef="c2"'
            raw=raw.replace(needle,b'name="company:Depreciation" contextRef="c2"')
            self.assertNotIn(needle,raw)
            answer=inspect_depreciation_input(raw_bytes=raw,entity='195',period=PERIOD,observations=observations)
            self.assertEqual(answer['status'],'KEEP')
            self.assertEqual(answer['chain_input']['value'],'20')
            self.assertEqual(len(answer['source_facts']),2)


class CurrentB03SourceOnlyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name);cls.sources={};cls.saved={}
        with shared_xbrl_parses():
            for company in ('marriott_international','salesforce'):
                source=cls.root/company;source.mkdir();cls.sources[company]=source
                prepared=prepare_saved_annual_input(repo_root=REPO_ROOT,company_id=company)
                paths={'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
                for proof in prepared['source_proofs']:
                    paths.update((proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']))
                for relative in paths:
                    target=source/relative;target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(REPO_ROOT/relative,target)
                cls.saved[company]=create_saved_result(source_root=source,output_root=cls.root/(company+'-result'),
                    company_id=company,metric_id='B03')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_marriott_composition_458m_and_135m_revenue_deduction_excluded(self):
        saved=self.saved['marriott_international'];records=[json.loads(s) for s in (self.root/'marriott_international-result/records.jsonl').read_text().splitlines()]
        roles={r['semantic_role']:r for r in records if r['record_type']=='VERIFIED_OBSERVATION' and r['metric_id']=='B03'}
        self.assertEqual(Decimal(roles['depreciation']['value'])+Decimal(roles['amortization']['value']),Decimal('458000000'))
        self.assertEqual(saved['result']['value'],'0.1756281982738868097456656229')
        self.assertEqual(saved['manifest']['target_period']['fiscal_year'],2025)
        self.assertFalse((self.sources['marriott_international']/'catalog').exists())
        self.assertEqual(saved['result']['unit'],'ratio')
        scope=saved['input_assessments']['depreciation_scope']
        self.assertEqual(scope['status'],'KEEP')
        exclusion=scope['existing_scope_check']
        self.assertFalse(exclusion['blocked'])
        self.assertTrue(any(Decimal(row['value_usd'])==Decimal('135000000') and row['dimensions']=={'srt:ProductOrServiceAxis':'mar:FeeServiceMember'} for row in exclusion['excluded_facts']))
        self.assertFalse(exclusion['amount_added_or_result_recomputed'])

    def test_salesforce_named_withheld_does_not_consume_bad_subtotal_and_carries_b01(self):
        saved=self.saved['salesforce'];self.assertIsNone(saved['result']['value'])
        self.assertEqual(saved['result']['publication'],'WITHHELD')
        self.assertEqual(saved['result']['reason_code'],'B03_DEPRECIATION_AMORTIZATION_SCOPE_UNPROVEN')
        self.assertEqual(saved['manifest']['target_period']['fiscal_year'],2026)
        records=[json.loads(s) for s in (self.root/'salesforce-result/records.jsonl').read_text().splitlines()]
        revenues=[r for r in records if r['record_type']=='METRIC_RESULT' and r['metric_id']=='B01']
        self.assertEqual(len(revenues),1);self.assertEqual(revenues[0]['value'],'41525000000')
        reread=read_saved_result(output_root=self.root/'salesforce-result')
        self.assertEqual(reread['result']['result_id'],saved['result']['result_id'])
        scope=reread['input_assessments']['depreciation_scope']
        self.assertEqual(scope['status'],'WITHHOLD')
        self.assertEqual({r['value'] for r in scope['source_facts']},{'1200000000','3631000000'})

    def test_amendment_input_uses_program_policy_without_sources_containing_it(self):
        source=self.sources['marriott_international']
        packet=prepare_saved_amendment_scopes(repo_root=source,company_id='marriott_international',rules_root=REPO_ROOT)
        self.assertEqual(packet['scopes'],[])
        instant=prepare_instant_balance_amendment_input(repo_root=source,company_id='marriott_international',rules_root=REPO_ROOT)
        self.assertEqual(instant['decision'],'INPUT_PROPERTY_PROVEN')
        self.assertFalse((source/'config/annual_amendment_scope_v1.json').exists())

    def test_saved_input_assessment_is_read_without_recalculation_and_damage_is_visible(self):
        path=self.root/'marriott_international-result/input-assessments.json'
        original=path.read_bytes();path.write_bytes(original+b' ')
        try:
            with self.assertRaisesRegex(ValueError,'SAVED_RESULT_FILE_CHANGED:input-assessments.json'):
                read_saved_result(output_root=path.parent)
        finally:path.write_bytes(original)

    def test_contract_revenue_deduction_keeps_relationship_under_legal_prefix_alias(self):
        from vnext.b03_contract_amortization_scope import assess_current_b03_scope
        from vnext.canonical import sha256_bytes
        saved=self.saved['marriott_international'];records=[json.loads(s) for s in (self.root/'marriott_international-result/records.jsonl').read_text().splitlines()]
        observations=[r for r in records if r['record_type']=='VERIFIED_OBSERVATION']
        proof=next(p for p in saved['manifest']['source_proofs'] if p['document_name'].endswith('.htm'))
        raw=(self.sources['marriott_international']/proof['request_repo_relative_path']).read_bytes()
        alias=raw.replace(b'xmlns:us-gaap=',b'xmlns:gaap=').replace(b'us-gaap:',b'gaap:')
        path=self.root/'alias-primary.htm';path.write_bytes(alias)
        case={'primary_metric_id':'B03','results':{'B03':saved['result']},'observations':observations,
              'target_period':saved['manifest']['target_period'],'source_proofs':[{**proof,'document_name':'alias-primary.htm','request_repo_relative_path':'alias-primary.htm','content_sha256':sha256_bytes(content=alias)}]}
        scope=assess_current_b03_scope(case=case,data_root=self.root)
        self.assertFalse(scope['blocked'])
        self.assertEqual(scope['status'],'COMPOSED_DA_CONTRACT_REVENUE_DEDUCTION_EXCLUDED')
        self.assertTrue(any(Decimal(r['value_usd'])==Decimal('135000000') for r in scope['excluded_facts']))



class ContractAggregateTest(unittest.TestCase):
    def material(self, aggregate=7, consolidated=8):
        # Small synthetic labelled tables: the segment total is an overlapping
        # view, never an additional amount added to the two segments.
        rows = [('Revenues', ''), ('Gross fee revenues', 20), ('Contract investment amortization', consolidated),
                ('Net fee revenues', 20-consolidated)]
        tables = ['<table><tr><th></th><th colspan="2">2025</th></tr>']
        for label, value in rows:
            text = ('<ix:nonFraction contextRef="synthetic" scale="6">-'+str(value)+'</ix:nonFraction>') if label.startswith('Contract') else str(value)
            tables.append('<tr><td>'+label+'</td><td>'+text+'</td><td></td></tr>')
        tables += ['</table><table><tr><th></th><th colspan="2">2025</th><th colspan="2">2025</th><th colspan="2">2025</th></tr>',
            '<tr><td>Gross fee revenues</td><td>10</td><td></td><td>10</td><td></td><td>20</td><td></td></tr>',
            '<tr><td>Contract investment amortization</td>'+''.join('<td><ix:nonFraction contextRef="synthetic" scale="6">-'+str(n)+'</ix:nonFraction></td><td></td>' for n in (5,2,aggregate))+'</tr>',
            '<tr><td>Net fee revenues</td><td>5</td><td></td><td>8</td><td></td><td>'+str(20-aggregate)+'</td><td></td></tr></table>']
        raw=('<html><body>'+''.join(tables)+'</body></html>').encode()
        parsed=SimpleNamespace(facts=[{'ordinal':n,'scale':'6'} for n in range(1,5)])
        product={'srt:ProductOrServiceAxis':'test:FeeMember'}
        group={**product,'srt:ConsolidationItemsAxis':'us-gaap:OperatingSegmentsMember'}
        dimensions=[product,{**group,'us-gaap:StatementBusinessSegmentsAxis':'test:SegmentA'},
                    {**group,'us-gaap:StatementBusinessSegmentsAxis':'test:SegmentB'},group]
        amounts=[{'ordinal':i+1,'value_usd':str(n*1000000),'dimensions':d}
                 for i,(n,d) in enumerate(zip((consolidated,5,2,aggregate),dimensions))]
        return raw,parsed,amounts

    def check(self, material):
        from vnext.b03_contract_amortization_scope import _visible_revenue_deductions
        raw,parsed,amounts=material
        return _visible_revenue_deductions(raw=raw,parsed=parsed,amounts=amounts,period=PERIOD)

    def test_aggregate_preserves_all_proofs_without_double_counting(self):
        answer=self.check(self.material())
        self.assertIsNotNone(answer)
        self.assertEqual([x['fact_ordinal'] for x in answer],[1,2,3,4])
        self.assertEqual(answer[-1]['relation_class'],'OPERATING_SEGMENTS_TOTAL_REVENUE_DEDUCTION')
        self.assertEqual(answer[-1]['displayed_amounts'],['20','-7','13'])

    def test_unreconciled_aggregate_or_unknown_scope_stays_unproved(self):
        for material in (self.material(aggregate=6),self.material(aggregate=9,consolidated=8)):
            with self.subTest(amounts=material[2]):self.assertIsNone(self.check(material))
        raw,parsed,amounts=self.material()
        amounts[-1]['dimensions']['srt:ConsolidationItemsAxis']='test:OtherScope'
        self.assertIsNone(self.check((raw,parsed,amounts)))

    def test_duplicate_aggregate_or_segment_does_not_gain_credit(self):
        raw,parsed,amounts=self.material()
        self.assertIsNone(self.check((raw,parsed,[*amounts,dict(amounts[-1])])))
        amounts[2]['dimensions']=dict(amounts[1]['dimensions'])
        self.assertIsNone(self.check((raw,parsed,amounts)))

    def test_aggregate_still_requires_original_gross_to_net_relation(self):
        raw,parsed,amounts=self.material()
        raw=raw.replace(b'<td>13</td>',b'<td>14</td>')
        self.assertIsNone(self.check((raw,parsed,amounts)))

    def test_hidden_self_closing_empty_cells_do_not_shift_visible_year_columns(self):
        raw,parsed,amounts=self.material()
        # Place two invisible empty cells before the total in each body row,
        # leaving the unchanged year headers and original native facts.
        for marker in (b'<td>20</td>', b'<td><ix:nonFraction contextRef="synthetic" scale="6">-7', b'<td>13</td>'):
            raw=raw.replace(marker,b'<td colspan="2" style="display:none"/><td colspan="2" style="DISPLAY: none !important;"/>'+marker)
        answer=self.check((raw,parsed,amounts))
        self.assertIsNotNone(answer)
        self.assertEqual([x['fact_ordinal'] for x in answer],[1,2,3,4])
        paired=raw.replace(b'style="display:none"/>',b'style="display:none"> </td>')
        paired=paired.replace(b'style="DISPLAY: none !important;"/>',b'style="DISPLAY: none !important;"></td>')
        self.assertIsNotNone(self.check((paired,parsed,amounts)))

    def test_visible_spacers_and_nonempty_hidden_cells_are_not_erased(self):
        raw,parsed,amounts=self.material()
        marker=b'<td><ix:nonFraction contextRef="synthetic" scale="6">-7'
        for extra in (b'<td colspan="4"/>', b'<td colspan="4" style="display:none">uncertain layout</td>'):
            with self.subTest(extra=extra):
                self.assertIsNone(self.check((raw.replace(marker,extra+marker),parsed,amounts)))

    def test_conflicting_or_commented_display_does_not_erase_visible_spacer(self):
        raw,parsed,amounts=self.material()
        marker=b'<td><ix:nonFraction contextRef="synthetic" scale="6">-7'
        for style in ('display:none;display:table-cell',
                      'display:none!important;display:table-cell!important',
                      '/* display:none; */ display:table-cell',
                      'display:table-cell;/* x;display:none; */'):
            with self.subTest(style=style):
                extra=('<td colspan="4" style="'+style+'"></td>').encode()
                self.assertIsNone(self.check((raw.replace(marker,extra+marker),parsed,amounts)))


if __name__=='__main__':unittest.main()
