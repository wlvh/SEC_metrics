"""Actual capital ratios and RPO retain native source scope and instant grain."""
import copy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from tests.vnext.test_normal_companyfacts_results import copy_sources
from vnext.canonical import content_hash
from vnext.normal_annual_input import _registry_rows
from vnext.normal_accession_results import (resolve_ordinary_accession_metrics, verify_ordinary_accession_metrics,
    inspect_ordinary_accession_facts, NormalAccessionError)
from vnext.records import validate_record
from vnext.sources import source_reference_record


class OrdinaryAccessionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with original_sources_only():
            cls.cases = {c['company_id']:resolve_ordinary_accession_metrics(repo_root=ROOT,company_id=c['company_id'])
                for c in _registry_rows(repo_root=ROOT)}
        cls.policy=json.loads((ROOT/'config/normal_accession_metrics_v1.json').read_text())
        cls.catalog=json.loads((ROOT/'catalog/deterministic_metrics.json').read_text())

    def inspect(self,company,metric,raw):
        """Rebound synthetic bytes exercise parsing, never saved-source credit."""
        case=self.cases[company]
        old=next(r for r in case['source_records'] if r['record_type']=='SOURCE_REFERENCE' and r['source_role']=='target_primary')
        blob=next(r for r in case['source_records'] if r['record_type']=='RAW_BLOB' and r['raw_asset_id']==old['raw_asset_id'])
        changed={**blob,'raw_asset_id':'sha256:'+hashlib.sha256(raw).hexdigest(),'byte_length':len(raw)}
        ref=source_reference_record(raw_blob=changed,company_id=company,source_url=old['source_url'],accession=old['accession'],
            document_name=old['document_name'],source_role=old['source_role'],request_attempt_id=old['request_attempt_id'])
        manifest={**case['source_set'],'ordered_source_reference_ids':[ref['source_reference_id']]}
        manifest['source_set_manifest_id']=content_hash(value={k:v for k,v in manifest.items() if k!='source_set_manifest_id'})
        with original_sources_only():
            return inspect_ordinary_accession_facts(raw_bytes=raw,source_reference=ref,source_set_manifest=manifest,
                expected_cik=case['prepared_input']['entity'],period_end=case['prepared_input']['filing']['reportDate'],
                route=self.catalog['metrics'][metric],metric_id=metric,policy=self.policy)

    def raw(self,company):
        return (ROOT/self.cases[company]['prepared_input']['table_input']['source_repo_relative_path']).read_bytes()

    def test_all_thirty_native_coordinates_preserve_three_applicable_source_values(self):
        numbers=[]
        for company,case in self.cases.items():
            self.assertEqual({'A01','A02','B12'},set(case['metrics']))
            self.assertEqual('NOT_CREATED',case['native_run_status'])
            self.assertFalse(case['production_authorized'])
            self.assertEqual({'provider':0,'paid':0,'sec':0},case['calls'])
            for metric,row in case['metrics'].items():
                for record in row['records']:validate_record(record=record)
                result=row['result']
                self.assertEqual(result['period_start'],result['period_end'])
                if result['applicability']=='APPLICABLE':numbers.append((company,metric,result['value'],result['unit']))
                else:self.assertEqual([],row['observations'])
        self.assertEqual([('jpmorgan_chase','A01','0.155','ratio'),('jpmorgan_chase','A02','0.146','ratio'),
                          ('salesforce','B12','72400000000','USD')],numbers)

    def test_capital_ratios_exclude_bank_subsidiary_and_advanced_method(self):
        for metric,value in [('A01','0.155'),('A02','0.146')]:
            row=self.cases['jpmorgan_chase']['metrics'][metric]
            claim=row['claims'][0]
            self.assertEqual(value,claim['value'])
            dims=claim['attributes']['context']['dimensions']
            self.assertEqual('srt:ParentCompanyMember',dims['srt:ConsolidatedEntitiesAxis'])
            self.assertEqual('jpm:BaselIIIStandardizedMember',dims['us-gaap:RiskWeightedAssetsCalculationMethodologyAxis'])
            other=[f for f in row['inspection']['facts'] if f['reason']=='OTHER_DISCLOSED_DIMENSION_SCOPE']
            self.assertEqual(3,len(other))
            self.assertTrue(any('dei:LegalEntityAxis' in f['context']['dimensions'] for f in other))
            self.assertTrue(any('jpm:BaselIIIAdvancedMember' in f['context']['dimensions'].values() for f in other))

    def test_rpo_is_the_undimensioned_instant_and_not_the_acquired_entity(self):
        row=self.cases['salesforce']['metrics']['B12']
        self.assertEqual('2026-01-31',row['result']['period_start'])
        self.assertEqual({},row['claims'][0]['attributes']['context']['dimensions'])
        self.assertEqual('REPORTED_UNDIMENSIONED_RPO_SUBSTITUTE_NOT_ARR_OR_CHURN',row['measure'])
        excluded=[r for r in row['inspection']['facts'] if r['reason']=='OTHER_DISCLOSED_DIMENSION_SCOPE']
        self.assertEqual(1,len(excluded))
        self.assertEqual({'us-gaap:BusinessAcquisitionAxis':'crm:InformaticaInc.Member'},excluded[0]['context']['dimensions'])

    def test_unit_identifier_renaming_keeps_the_definition_but_false_measure_is_rejected(self):
        for company,metric in [('jpmorgan_chase','A01'),('salesforce','B12')]:
            raw=self.raw(company)
            claim=self.cases[company]['metrics'][metric]['claims'][0]
            unit=claim['attributes']['raw_unit_ref'].encode()
            changed=raw.replace(b'unitRef="'+unit+b'"',b'unitRef="renamed-unit"').replace(b'id="'+unit+b'"',b'id="renamed-unit"')
            self.assertNotEqual(raw,changed)
            result=self.inspect(company,metric,changed)
            self.assertEqual('SOURCE_SCOPE_PROVEN',result['status'])
            self.assertFalse(result['source_acquisition_credit'])
            measure=b'xbrli:pure' if metric=='A01' else b'iso4217:USD'
            false=b'iso4217:USD' if metric=='A01' else b'xbrli:shares'
            changed=raw.replace(measure,false)
            self.assertNotEqual(raw,changed)
            self.assertEqual('UNRESOLVED',self.inspect(company,metric,changed)['status'])

    def test_source_context_namespace_and_malformed_numeric_text_are_not_accepted(self):
        raw=self.raw('salesforce')
        changed=raw.replace(b'http://www.sec.gov/CIK',b'urn:unverified-entity-scheme')
        self.assertNotEqual(raw,changed)
        result=self.inspect('salesforce','B12',changed)
        self.assertEqual('UNRESOLVED',result['status'])
        claim=self.cases['salesforce']['metrics']['B12']['claims'][0]
        qualified=re.escape(claim['locator']['qualified_name'].encode())
        context=re.escape(claim['locator']['context_ref'].encode())
        pattern=rb'<ix:nonFraction(?=[^>]*name="'+qualified+rb'")(?=[^>]*contextRef="'+context+rb'")[^>]*>.*?</ix:nonFraction>'
        match=re.search(pattern,raw,re.S);self.assertIsNotNone(match)
        element=match.group()
        bad=re.sub(rb'(?<=>)[^<]+(?=<)',b'72,40',element,count=1)
        self.assertNotEqual(element,bad)
        changed=raw[:match.start()]+bad+raw[match.end():]
        self.assertEqual('UNRESOLVED',self.inspect('salesforce','B12',changed)['status'])

    def test_real_no_git_json_rebuild_rejects_changed_answer_and_period(self):
        for company in ('jpmorgan_chase','salesforce'):
            case=self.cases[company]
            with tempfile.TemporaryDirectory(prefix='normal-accession-source-') as tmp:
                data=Path(tmp);copy_sources(case,data)
                with original_sources_only():
                    self.assertEqual(case,verify_ordinary_accession_metrics(candidate=json.loads(json.dumps(case)),repo_root=data,company_id=company))
                changed=copy.deepcopy(case);metric='A01' if company=='jpmorgan_chase' else 'B12'
                changed['metrics'][metric]['result']['period_start']='2025-01-01'
                changed['component_id']=content_hash(value={k:v for k,v in changed.items() if k!='component_id'})
                with original_sources_only(),self.assertRaisesRegex(NormalAccessionError,'SOURCE_REPLAY_CHANGED'):
                    verify_ordinary_accession_metrics(candidate=changed,repo_root=data,company_id=company)


if __name__=='__main__':unittest.main()
