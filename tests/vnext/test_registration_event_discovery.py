"""Synthetic metadata routing only; no SEC acquisition or metric credit."""
from copy import deepcopy
import hashlib
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from vnext.normal_governance_input import _filings,NormalGovernanceInputError
from vnext.normal_source_requirements import _discovery_filings,_registration_event_requirements,SourceRequirementsError


def metadata():
    rows=[
        ('8-K12B','0000000456-25-000001','registered.htm','2025-08-07','2025-08-07','1.01,9.01'),
        ('8-K12B/A','0000000123-25-000002','amended.htm','2025-10-23','2025-08-07','7.01,9.01'),
        ('8-K','0000000123-25-000003','ordinary.htm','2025-06-01','2025-06-01','4.01'),
        ('10-K','0000000123-26-000001','annual.htm','2026-02-17','2025-12-31','')]
    keys=['form','accessionNumber','primaryDocument','filingDate','reportDate','items']
    return {'filings':{'recent':{key:[row[i]for row in rows]for i,key in enumerate(keys)}}}


class RouteOnlyPlan:
    def __init__(self):self.requests={}
    def require(self,url,role,media,accession):
        self.requests.setdefault(url,{'source_url':url,'roles':[role],'media_type':media,
            'accession':accession,'source_acquisition_credit':False,'fixture':'SYNTHETIC_ROUTING_ONLY'})


class RegistrationEventDiscoveryTest(unittest.TestCase):
    window={'period_start':'2025-01-01','period_end':'2025-12-31'}
    def rows(self,payload):return _discovery_filings(payload,inventory_name='synthetic-current.json')
    def test_frozen_parser_hash_and_original_default_are_preserved(self):
        relative='scripts/vnext/normal_governance_input.py'
        binding=json.loads((ROOT/'requirements/issue_28_v11/baseline_manifest.json').read_text())['new_rule_files'][relative]
        raw=(ROOT/relative).read_bytes()
        self.assertEqual({'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)},binding)
        original=_filings(metadata(),inventory_name='synthetic-current.json')
        self.assertEqual([row['form']for row in original],['8-K','10-K'])
    def test_original_payload_every_field_and_raw_variant_names_survive(self):
        source=metadata();before=deepcopy(source);rows=self.rows(source)
        self.assertEqual(source,before)
        self.assertEqual([r['form']for r in rows],source['filings']['recent']['form'])
        for row in rows:
            index=row['metadata_origin']['row_index']
            for key,values in source['filings']['recent'].items():self.assertEqual(row[key],values[index])
    def test_four_urls_are_deduplicated_and_registrant_cik_owns_paths(self):
        plan=RouteOnlyPlan();rows=self.rows(metadata())
        selected=_registration_event_requirements(plan,rows,'123',self.window)
        _registration_event_requirements(plan,rows,'123',self.window)
        self.assertEqual(len(selected),2);self.assertEqual(len(plan.requests),4)
        self.assertTrue(all('/data/123/'in url for url in plan.requests))
        self.assertTrue(any('/000000045625000001/'in url for url in plan.requests))
        self.assertTrue(all(r['semantic_form_scope']=='SOURCE_DISCOVERY_ONLY_NOT_EXISTING_EVENT_ACCEPTANCE'
                            and r['source_acquisition_credit']is False for r in plan.requests.values()))
    def test_items_field_cannot_remove_the_original_dependencies(self):
        source=metadata();source['filings']['recent']['items']=['']*4
        plan=RouteOnlyPlan();_registration_event_requirements(plan,self.rows(source),'123',self.window)
        self.assertEqual(len(plan.requests),4)
    def test_variant_identity_path_date_columns_and_raw_form_are_checked(self):
        for field,value in [('accessionNumber','bad'),('primaryDocument','../escape.htm'),('filingDate','2025-99-01'),('form',' 8-K12B')]:
            with self.subTest(field=field):
                source=metadata();source['filings']['recent'][field][0]=value
                with self.assertRaises(NormalGovernanceInputError):self.rows(source)
        source=metadata();source['filings']['recent']['items'].pop()
        with self.assertRaisesRegex(NormalGovernanceInputError,'COLUMNS_CONFLICT'):self.rows(source)
    def test_duplicates_are_rejected_before_any_requirement_is_added(self):
        source=metadata();source['filings']['recent']['accessionNumber'][1]=source['filings']['recent']['accessionNumber'][0]
        with self.assertRaisesRegex(NormalGovernanceInputError,'ACCESSION_INVALID_OR_DUPLICATE'):self.rows(source)
        rows=self.rows(metadata());plan=RouteOnlyPlan()
        with self.assertRaisesRegex(SourceRequirementsError,'REGISTRATION_INVENTORIES_OVERLAP'):
            _registration_event_requirements(plan,rows+[deepcopy(rows[1])],'123',self.window)
        self.assertEqual(plan.requests,{})
    def test_only_exact_two_variants_inside_the_existing_window_are_added(self):
        source=metadata();source['filings']['recent']['form'][0]='8-K12B-UNKNOWN'
        rows=self.rows(source);plan=RouteOnlyPlan();selected=_registration_event_requirements(plan,rows,'123',self.window)
        self.assertEqual([r['form']for r in selected],['8-K12B/A']);self.assertEqual(len(plan.requests),2)
        plan=RouteOnlyPlan();self.assertEqual(_registration_event_requirements(plan,self.rows(metadata()),'123',
            {'period_start':'2026-01-01','period_end':'2026-12-31'}),[]);self.assertEqual(plan.requests,{})


if __name__=='__main__':unittest.main()
