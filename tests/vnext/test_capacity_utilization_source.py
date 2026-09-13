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


class CapacityComparisonTest(unittest.TestCase):
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
