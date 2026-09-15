"""Approved B13 comparison rules; source snippets remain development inputs."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json
import os
import socket
import unittest

from vnext.canonical import content_hash
from vnext.capacity_utilization_source import calculate_comparable_pair,prepare_capacity_sources
from vnext.normal_source_authority import ROOT


def quantity_source(body):
    from tests.vnext.test_text_coverage import annual, binding
    from tests.vnext.test_capacity_semantic_review import source_packet
    from vnext.sources import source_reference_record
    from vnext.text_coverage import build_text_document
    from vnext.r6_semantic_source import _seal_unit
    original = binding(annual(body, cik='1463101'))
    ref = source_reference_record(raw_blob=original['raw_blob'], company_id='enphase_energy',
        source_url='https://www.sec.gov/Archives/edgar/data/1463101/000146310126000001/source.htm',
        accession='0001463101-26-000001', document_name='source.htm', source_role='target_primary',
        request_attempt_id='synthetic-quantity-test')
    original.update(source_reference=ref, expected_company_id='enphase_energy', expected_cik='1463101')
    document = build_text_document(**original)
    for block in document['blocks']:
        block['html_quotation_context'] = False
    unit = _seal_unit(document['text_document_id'], 'VISIBLE_TEXT', {'blocks': document['blocks']}, 0)
    source = source_packet()
    filing = {'accessionNumber': ref['accession'], 'form': '10-K', 'reportDate': '2025-12-31', 'filingDate': '2026-02-01'}
    source['prepared_annual_input'].update(entity='1463101', filing=filing)
    source['prepared_annual_input']['table_input']['target_period'] = {'period_start':'2025-01-01', 'period_end':'2025-12-31', 'fiscal_year':2025}
    source.update(units=[unit], required_unit_ids=[unit['unit_id']], documents=[{'document_id': unit['document_id'],
        'filing': filing, 'source_reference': ref, 'raw_blob': original['raw_blob'], 'registrant_name_binding': {},
        'source_unit_ids':[unit['unit_id']]}])
    source['semantic_source_id'] = content_hash(value={k:v for k,v in source.items() if k != 'semantic_source_id'})
    from vnext.capacity_quantity_scope import attach_quantity_scope
    raw = {original['raw_blob']['raw_asset_id']:original['raw_bytes']}
    return attach_quantity_scope(source=source, raw_bytes_by_id=raw), raw


class CapacityComparisonTest(unittest.TestCase):
    def test_quantity_facts_cannot_be_relabelled_as_other_or_historical(self):
        from vnext.capacity_semantic_review import requests_from_source, validate_response
        from vnext.r6_semantic_source import _bytes
        source, _ = quantity_source('<p>For fiscal year 2025, we produced 80 widgets worldwide.</p>'
            '<p>For fiscal year 2025, our available annual production capacity was 100 widgets worldwide.</p>')
        request = requests_from_source(source)[0]
        unit = source['units'][0]
        findings = []
        for block in unit['payload']['blocks']:
            if '80 widgets' in block['text'] or '100 widgets' in block['text']:
                findings.append({'kind':'ACTUAL_PRODUCTION' if '80 widgets' in block['text'] else 'AVAILABLE_CAPACITY',
                    'subject':'TARGET_REGISTRANT','timing':'CURRENT_REPORT','reason':'Synthetic source classification.',
                    'evidence':[{'kind':'VISIBLE_BLOCK','source_index':block['block_index']}]})
        response = {'request_id':request['request_id'],'units':[{'unit_id':unit['unit_id'], 'reviewed':True,
            'findings':findings,'unresolved':[],'calculation_limits':[]}]}
        validate_response(request=request, raw_response=_bytes(response))
        for field, value in [('kind','OTHER_CONTEXT'),('timing','HISTORICAL'),('subject','OTHER_ENTITY')]:
            bad = deepcopy(response); bad['units'][0]['findings'][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError,'SOURCE_QUANTITY_CLASSIFICATION_CONFLICT'):
                validate_response(request=request, raw_response=_bytes(bad))

    def test_original_quantities_and_scope_are_rebuilt_before_division(self):
        from vnext.capacity_utilization_source import calculate_source_comparable_pair
        source, raw = quantity_source('<p>For fiscal year 2025, we produced 80 million widgets worldwide.</p>'
            '<p>For fiscal year 2025, our available annual production capacity was 100 million widgets globally.</p>')
        checked = calculate_source_comparable_pair(source=source, raw_bytes_by_id=raw)
        self.assertEqual(checked['result']['value'], '0.8')
        self.assertTrue(checked['source_assignments_independently_verified'])
        self.assertFalse(checked['native_result_created'])
        self.assertEqual([o['value'] for o in checked['observations']], ['80000000', '100000000'])
        self.assertIn('widgets; worldwide', checked['target']['scope']['product_or_facility_scope'])
        changed = deepcopy(source)
        block = next(b for b in changed['units'][0]['payload']['blocks'] if '80 million' in b['text'])
        block['text'] = block['text'].replace('80 million','99 million')
        changed['semantic_source_id'] = content_hash(value={k:v for k,v in changed.items() if k != 'semantic_source_id'})
        with self.assertRaisesRegex(ValueError, 'SOURCE_BLOCK_CHANGED'):
            calculate_source_comparable_pair(source=changed, raw_bytes_by_id=raw)

    def test_quantity_relations_reject_scope_period_and_substitute_amounts(self):
        from vnext.capacity_utilization_source import calculate_source_comparable_pair
        production = 'For fiscal year 2025, we produced 80 widgets worldwide.'
        capacity = 'For fiscal year 2025, our available annual production capacity was 100 widgets worldwide.'
        for p, c in [
            (production.replace('produced','sold'),capacity),
            (production.replace('produced','plan to produce'),capacity),
            (production,capacity.replace('available annual','installed annual')),
            (production,capacity.replace('annual','quarterly')),
            (production,capacity.replace('widgets','microinverters')),
            (production,capacity.replace('worldwide','at our North plant')),
            (production.replace('2025','2024'),capacity),
            (production.replace('widgets','tax credits'),capacity.replace('widgets','tax credits')),
        ]:
            source, raw = quantity_source('<p>'+p+'</p><p>'+c+'</p>')
            with self.subTest(p=p,c=c), self.assertRaises(ValueError):
                calculate_source_comparable_pair(source=source, raw_bytes_by_id=raw)
        source, raw = quantity_source('<blockquote><p>'+production+'</p></blockquote><p>'+capacity+'</p>')
        with self.assertRaisesRegex(ValueError, 'RELATION_NOT_UNIQUE_OR_UNSUPPORTED'):
            calculate_source_comparable_pair(source=source, raw_bytes_by_id=raw)
        source, raw = quantity_source('<h2>Hypothetical example:</h2><p>'+production+'</p><p>'+capacity+'</p>')
        with self.assertRaisesRegex(ValueError, 'RELATION_NOT_UNIQUE_OR_UNSUPPORTED'):
            calculate_source_comparable_pair(source=source, raw_bytes_by_id=raw)
        source, raw = quantity_source('<p>'+production.replace('For fiscal year', 'During')+'</p><p>'+capacity+'</p>')
        source['prepared_annual_input']['table_input']['target_period']['period_start'] = '2024-12-29'
        source['semantic_source_id'] = content_hash(value={k:v for k,v in source.items() if k != 'semantic_source_id'})
        with self.assertRaisesRegex(ValueError, 'RELATION_NOT_UNIQUE_OR_UNSUPPORTED'):
            calculate_source_comparable_pair(source=source, raw_bytes_by_id=raw)

    def setUp(self):
        scope={'capacity_basis':'actual_production_over_available_capacity','product_or_facility_scope':'same facility and product'}
        self.target={'company_id':'ford_motor_company','entity':'37996','period_start':'2025-01-01',
            'period_end':'2025-12-31','accession':'0000037996-26-000015','scope':scope,'scope_key':content_hash(value=scope)}
        common={k:self.target[k] for k in ['entity','period_start','period_end']}
        common.update(unit='vehicles',product_or_facility_scope=scope['product_or_facility_scope'],
            source_binding={'entity':self.target['entity'],'accession':self.target['accession'],'filing_date':'2026-02-01',
                'document_name':'synthetic.html','raw_asset_id':content_hash(value='synthetic source'),
                'source_reference_id':content_hash(value='synthetic reference'),'source_role':'target_primary'})
        self.production={**common,'basis':'ACTUAL_PRODUCTION','value':'80'}
        self.capacity={**common,'basis':'AVAILABLE_CAPACITY','value':'100'}

    def test_comparable_quantities_reuse_the_existing_calculator(self):
        result=calculate_comparable_pair(target=self.target,production=self.production,capacity=self.capacity)
        self.assertEqual(result['result']['value'],'0.8')
        self.assertFalse(result['native_result_created'])
        self.assertFalse(result['source_assignments_independently_verified'])
        self.assertEqual(len(result['observations']),2)
        for output,expected in [('0','0'),('120','1.2')]:
            result=calculate_comparable_pair(target=self.target,production={**self.production,'value':output},capacity=self.capacity)
            self.assertEqual(result['result']['value'],expected)

    def test_no_sales_shipments_installed_or_planned_substitutes(self):
        for role in ['SALES','SHIPMENTS','INSTALLED_CAPACITY','PLANNED_PRODUCTION']:
            with self.assertRaisesRegex(ValueError,'QUANTITY_ROLE'):
                calculate_comparable_pair(target=self.target,production={**self.production,'basis':role},capacity=self.capacity)
        with self.assertRaisesRegex(ValueError,'QUANTITY_ROLE'):
            calculate_comparable_pair(target=self.target,production=self.production,capacity={**self.capacity,'basis':'FUTURE_PLANNED_CAPACITY'})

    def test_unit_subject_period_and_facility_mismatch_are_rejected(self):
        for field,value in [('unit','microinverters'),('entity','other'),('period_start','2024-01-01'),
                            ('period_end','2024-12-31'),('product_or_facility_scope','different facility')]:
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'INCOMPARABLE'):
                calculate_comparable_pair(target=self.target,production=self.production,capacity={**self.capacity,field:value})

    def test_zero_capacity_and_unapproved_company_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'NOT_POSITIVE'):
            calculate_comparable_pair(target=self.target,production=self.production,capacity={**self.capacity,'value':'0'})
        with self.assertRaisesRegex(ValueError,'APPLICABILITY'):
            calculate_comparable_pair(target={**self.target,'company_id':'pfizer'},production=self.production,capacity=self.capacity)
        scope={**self.target['scope'],'capacity_basis':'sales_over_capacity'}
        with self.assertRaisesRegex(ValueError,'MEANING_CHANGED'):
            calculate_comparable_pair(target={**self.target,'scope':scope,'scope_key':content_hash(value=scope)},
                production=self.production,capacity=self.capacity)


class CapacitySourceMaterialTest(unittest.TestCase):
    def test_actual_two_company_disclosures_do_not_become_ratios_or_absence(self):
        output=os.environ.get('B13_SOURCE_MATERIAL_ROOT')
        root=Path(output).resolve() if output else None
        if root:self.assertFalse(root.exists());root.mkdir(parents=True)
        with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen',side_effect=AssertionError('SEC_FORBIDDEN')):
            for company in ['ford_motor_company','enphase_energy']:
                result=prepare_capacity_sources(repo_root=ROOT,company_id=company)
                self.assertEqual(result['source_status'],'RELATED_DISCLOSURES_FOUND')
                self.assertEqual(result['candidate_text_status'],'TEXT_QUAL')
                self.assertFalse(result['absence_established']);self.assertFalse(result['native_result_created'])
                self.assertFalse(result['numeric_pair_completeness_verified'])
                texts='\n'.join(r['text'] for r in result['related_disclosures'])
                expected='rationalize our EV manufacturing capacity' if company=='ford_motor_company' else 'five-million microinverters per quarter'
                self.assertIn(expected,texts)
                if root:(root/(company+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
                print(company,len(result['related_disclosures']),'related disclosures',len(result['possible_actual_production']),'production candidates',flush=True)


if __name__=='__main__':unittest.main()
