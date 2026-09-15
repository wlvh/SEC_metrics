"""B06 nonpositive denominator: original material and isolated false guards."""
import copy
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from vnext import b06_guarded_result_v3 as guard
from vnext.canonical import content_hash, sha256_bytes
from vnext.observations import scope_key
from vnext.sources import source_reference_record
from vnext.specs import compile_spec_file
from vnext.records import validate_record

ROOT = Path(__file__).resolve().parents[2]
PERIOD = {"fiscal_year": 2025, "period_start": "2025-01-01", "period_end": "2025-12-31"}


def synthetic(value=-10000000):
    """TEST_ONLY source bytes: these have no saved-acquisition or Run credit."""
    namespaces = ('xmlns:xbrli="http://www.xbrl.org/2003/instance" '
        'xmlns:dei="http://xbrl.sec.gov/dei/2025" xmlns:us-gaap="http://fasb.org/us-gaap/2025" '
        'xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:iso4217="http://www.xbrl.org/2003/iso4217"')
    contexts = ('<xbrli:context id="annual"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">1</xbrli:identifier>'
        '</xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate>'
        '</xbrli:period></xbrli:context><xbrli:context id="end"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">1</xbrli:identifier>'
        '</xbrli:entity><xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period></xbrli:context>'
        '<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>')
    dei = {"EntityCentralIndexKey": "1", "DocumentFiscalYearFocus": "2025", "DocumentFiscalPeriodFocus": "FY",
           "DocumentType": "10-K", "DocumentPeriodEndDate": "2025-12-31", "AmendmentFlag": "false"}
    inline_dei = ''.join('<ix:nonNumeric name="dei:'+key+'" contextRef="annual">'+text+'</ix:nonNumeric>' for key,text in dei.items())
    xml_dei = ''.join('<dei:'+key+' contextRef="annual">'+text+'</dei:'+key+'>' for key,text in dei.items())
    amount = str(abs(value) // 1000000)
    sign = ' sign="-"' if value < 0 else ''
    inline = '<ix:nonFraction name="us-gaap:StockholdersEquity" contextRef="end" unitRef="usd" scale="6" decimals="-6"'+sign+'>'+amount+'</ix:nonFraction>'
    if value < 0: inline = '('+inline+')'
    primary = ('<html '+namespaces+'><body>'+contexts+inline_dei+'<table><tr><td>Stockholders equity</td><td>'+inline+'</td></tr></table></body></html>').encode()
    xml = ('<xbrli:xbrl '+namespaces+'>'+contexts+xml_dei+'<us-gaap:StockholdersEquity contextRef="end" unitRef="usd" decimals="-6">'+str(value)+'</us-gaap:StockholdersEquity></xbrli:xbrl>').encode()
    accession = '0000000001-26-000001'
    facts = {'cik': 1, 'facts': {'us-gaap': {'StockholdersEquity': {'units': {'USD': [
        {'val': value, 'end':'2025-12-31','accn':accession,'form':'10-K','fp':'FY','fy':2025,'filed':'2026-02-01'}]}}}}}
    facts_raw = json.dumps(facts).encode()
    scope = {'entity_scope':'consolidated'}
    target = {'company_id':'test_company','entity':'1','accession':accession,'period_start':'2025-12-31',
              'period_end':'2025-12-31','scope':scope,'scope_key':scope_key(scope=scope)}
    def reference(raw, name, role):
        if role == 'companyfacts': name = 'CIK0000000001.json'
        blob={'record_type':'RAW_BLOB','raw_asset_id':'sha256:'+sha256_bytes(content=raw),
              'byte_length':len(raw),'media_type':'application/xml','storage_uri':'TEST_ONLY/'+name}
        url = ('https://data.sec.gov/api/xbrl/companyfacts/'+name if role == 'companyfacts'
               else 'https://www.sec.gov/Archives/edgar/data/1/000000000126000001/'+name)
        return source_reference_record(raw_blob=blob,company_id='test_company',source_url=url,
            accession=accession,document_name=name,source_role=role,request_attempt_id='request:TEST_ONLY')
    return {'primary':primary,'xml':xml,'facts_raw':facts_raw,'facts_source':reference(facts_raw,'facts.json','companyfacts'),
            'target':target,'period':PERIOD,'filing':{'form':'10-K','reportDate':'2025-12-31'}}, reference


class B06GuardSourceTest(unittest.TestCase):
    def test_zero_and_negative_make_native_null_results_without_debt(self):
        spec=compile_spec_file(path=ROOT/guard.SPEC_PATH,dependency_specs={})
        for number in (0,-10000000):
            with self.subTest(value=number):
                args,ref=synthetic(number);proof=guard._rebuild_equity(**args)
                result,trace,observations=guard._terminal_records(spec=spec,target=args['target'],proof=proof,
                    source=ref(args['xml'],'filing.xml','auditor_facts'),filed='2026-02-01',form='10-K')
                self.assertEqual('NOT_MEANINGFUL',result['quality'])
                self.assertEqual('DENOMINATOR_NONPOSITIVE',result['reason_code'])
                self.assertIsNone(result['value']);self.assertIsNone(result['unit'])
                self.assertEqual(['equity'],[o['semantic_role'] for o in observations])
                self.assertEqual('NOT_EVALUATED',trace['steps'][0]['debt_completeness'])
                self.assertFalse(trace['steps'][0]['numerator_evaluated'])
                for record in [result,trace,*observations]:validate_record(record=record)

    def test_positive_and_boolean_cannot_trigger_nonpositive_record(self):
        args,ref=synthetic(10000000);proof=guard._rebuild_equity(**args)
        spec=compile_spec_file(path=ROOT/guard.SPEC_PATH,dependency_specs={})
        for value in ('10000000',False):
            proof['value']=value
            with self.assertRaisesRegex(guard.B06GuardError,'NONPOSITIVE_PROOF_REQUIRED'):
                guard._terminal_records(spec=spec,target=args['target'],proof=proof,
                    source=ref(args['xml'],'filing.xml','auditor_facts'),filed='2026-02-01',form='10-K')

    def test_sign_scale_unit_namespace_period_and_subject_conflicts_reject(self):
        original,_=synthetic()
        mutations=[('primary',lambda b:b.replace(b' sign="-"',b'')),
            ('primary',lambda b:b.replace(b'scale="6"',b'scale="3"')),
            ('xml',lambda b:b.replace(b'iso4217:USD',b'iso4217:EUR')),
            ('xml',lambda b:b.replace(b'http://fasb.org/us-gaap/2025',b'http://example.test/us-gaap/2025')),
            ('xml',lambda b:b.replace(b'<xbrli:instant>2025-12-31',b'<xbrli:instant>2024-12-31')),
            ('xml',lambda b:b.replace(b'id="end"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">1',
                                    b'id="end"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">2'))]
        for key,mutate in mutations:
            with self.subTest(key=key,mutation=mutate):
                args=dict(original);args[key]=mutate(args[key]);self.assertNotEqual(original[key],args[key])
                with self.assertRaises(ValueError):guard._rebuild_equity(**args)

    def test_unknown_or_conflicting_equity_does_not_hide_behind_one_negative_report(self):
        args,_=synthetic();duplicate=b'<us-gaap:StockholdersEquity contextRef="end" unitRef="usd" decimals="-6">10000000</us-gaap:StockholdersEquity>'
        args['xml']=args['xml'].replace(b'</xbrli:xbrl>',duplicate+b'</xbrli:xbrl>')
        with self.assertRaisesRegex(ValueError,'SAME_PRECISION_CONFLICT'):guard._rebuild_equity(**args)

    def test_same_filing_companyfacts_conflict_is_not_tolerated(self):
        args,ref=synthetic();facts=json.loads(args['facts_raw']);facts['facts']['us-gaap']['StockholdersEquity']['units']['USD'][0]['val']=10000000
        args['facts_raw']=json.dumps(facts).encode();args['facts_source']=ref(args['facts_raw'],'facts.json','companyfacts')
        with self.assertRaisesRegex(guard.B06GuardError,'COMPANYFACTS_CONFLICT'):guard._rebuild_equity(**args)

    def test_finest_value_keeps_the_locator_of_the_source_that_reported_it(self):
        args,ref=synthetic()
        args['primary']=args['primary'].replace(b'>10</ix:nonFraction>',b'>10.5</ix:nonFraction>').replace(b'decimals="-6"',b'decimals="0"')
        facts=json.loads(args['facts_raw']);facts['facts']['us-gaap']['StockholdersEquity']['units']['USD'][0]['val']=-10500000
        args['facts_raw']=json.dumps(facts).encode();args['facts_source']=ref(args['facts_raw'],'facts.json','companyfacts')
        proof=guard._rebuild_equity(**args)
        self.assertEqual('-10500000',proof['value']);self.assertEqual('primary',proof['observation_source_kind'])
        self.assertEqual('-10000000',proof['xml']['chosen']['value'])
        spec=compile_spec_file(path=ROOT/guard.SPEC_PATH,dependency_specs={})
        _,_,observations=guard._terminal_records(spec=spec,target=args['target'],proof=proof,
            source=ref(args['primary'],'filing.htm','target_primary'),filed='2026-02-01',form='10-K')
        self.assertEqual('sha256:'+sha256_bytes(content=args['primary']),observations[0]['source_binding']['raw_asset_id'])
        self.assertEqual('-10500000',observations[0]['value'])

    def test_hidden_or_visibly_opposite_equity_is_not_accepted(self):
        args,_=synthetic();args['primary']=args['primary'].replace(b'(<ix:nonFraction',b'<ix:nonFraction').replace(b'</ix:nonFraction>)',b'</ix:nonFraction>')
        with self.assertRaisesRegex(guard.B06GuardError,'VISIBLE_SIGN_OR_SCALE_CONFLICT'):guard._rebuild_equity(**args)
        args,_=synthetic();args['primary']=args['primary'].replace(b'<table><tr><td>Stockholders equity</td><td>',b'<div>').replace(b'</td></tr></table>',b'</div>')
        with self.assertRaisesRegex(guard.B06GuardError,'VISIBLE_CELL_REQUIRED'):guard._rebuild_equity(**args)


class B06GuardOriginalMaterialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(socket.socket,'connect',side_effect=AssertionError('network')):
            cls.actual={company:guard.prepare_guarded_b06_result(repo_root=ROOT,company_id=company)
                        for company in ('marriott_international','lumen_technologies','southwest_airlines')}

    def test_marriott_and_lumen_are_guarded_without_debt_disclosure_parser(self):
        for company,value in [('marriott_international','-3771000000'),('lumen_technologies','-1117000000')]:
            item=self.actual[company]
            self.assertEqual('NOT_MEANINGFUL',item['status']);self.assertEqual(value,item['equity_proof']['value'])
            self.assertEqual('NOT_EVALUATED',item['debt_completeness'])
            self.assertEqual(1,len(item['observations']));self.assertEqual('equity',item['observations'][0]['semantic_role'])
            self.assertEqual('NOT_CREATED',item['native_run_status']);self.assertFalse(item['production_authorized'])
            self.assertEqual({'provider':0,'paid':0,'sec':0},item['calls'])
        with patch('vnext.b06_disclosure.propose',side_effect=AssertionError('debt parser must not run')):
            self.assertEqual(self.actual['marriott_international'],guard.prepare_guarded_b06_result(repo_root=ROOT,company_id='marriott_international'))

    def test_positive_source_continues_without_any_result(self):
        item=self.actual['southwest_airlines'];self.assertEqual('CONTINUE_DEBT_PATH',item['status'])
        self.assertIsNone(item['result']);self.assertIsNone(item['trace']);self.assertEqual([],item['observations'])
        self.assertEqual('7981000000',item['equity_proof']['value'])

    def test_actual_guard_survives_json_save_and_independent_raw_rebuild(self):
        for company in ('marriott_international','lumen_technologies'):
            stored=json.loads(json.dumps(self.actual[company]))
            self.assertEqual(self.actual[company],stored)
            self.assertEqual(stored,guard.verify_guarded_b06_result(candidate=stored,repo_root=ROOT,company_id=company))

    def test_disk_components_rebuild_in_a_fresh_process(self):
        code = """
import json, pathlib, sys
root, source = map(pathlib.Path, sys.argv[1:])
sys.path.insert(0, str(root / 'scripts'))
def audit(event, args):
    if event.startswith('socket.'):
        raise RuntimeError('Material replay forbids network')
sys.addaudithook(audit)
from vnext.b06_guarded_result_v3 import verify_guarded_b06_result
for company, candidate in json.loads(source.read_text()).items():
    actual = verify_guarded_b06_result(candidate=candidate, repo_root=root, company_id=company)
    assert actual == candidate
print('PASS three original components after JSON disk reload')
"""
        with tempfile.TemporaryDirectory(prefix='b06-guard-cold-json-') as directory:
            path = Path(directory) / 'components.json'
            path.write_text(json.dumps(self.actual))
            result = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT), str(path)],
                cwd=directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            self.assertEqual(0, result.returncode, result.stdout)
            self.assertIn('PASS three original components', result.stdout)

    def test_rehashed_false_guard_or_complete_debt_cannot_survive_raw_replay(self):
        original=self.actual['marriott_international']
        for change in ('debt','result'):
            item=copy.deepcopy(original)
            if change=='debt':item['debt_completeness']=True
            else:item['result']['quality']='EXACT';item['result']['value']='0';item['result']['unit']='ratio'
            item['component_id']=content_hash(value={k:v for k,v in item.items() if k!='component_id'})
            with self.assertRaisesRegex(guard.B06GuardError,'REPLAY_CHANGED'):
                guard.verify_guarded_b06_result(candidate=item,repo_root=ROOT,company_id='marriott_international')

    def test_changed_raw_bytes_after_admission_cannot_enter_guard(self):
        prepared=guard._prepare_b06(repo_root=ROOT,company_id='marriott_international')
        changed=copy.deepcopy(prepared);changed['primary']['raw_bytes']+=b' '
        with patch.object(guard,'_prepare_b06',return_value=changed):
            with self.assertRaisesRegex(guard.B06GuardError,'SOURCE_CHANGED_AFTER_ADMISSION'):
                guard.prepare_guarded_b06_result(repo_root=ROOT,company_id='marriott_international')

    def test_imported_spec_cannot_enable_a_different_guard(self):
        with tempfile.TemporaryDirectory(prefix='b06-guard-spec-') as directory:
            path=Path(directory)/guard.SPEC_PATH;path.parent.mkdir(parents=True)
            path.write_text((ROOT/guard.SPEC_PATH).read_text().replace('"nonpositive"','"positive"'))
            with self.assertRaisesRegex(guard.B06GuardError,'INSTALLED_SPEC_REQUIRED'):
                guard.prepare_guarded_b06_result(repo_root=Path(directory),company_id='marriott_international')


if __name__=='__main__':unittest.main()
