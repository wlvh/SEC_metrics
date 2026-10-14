"""Same-body capture provenance is not a changed D04 annual selection."""
from copy import deepcopy
import unittest

from tests.vnext.test_capacity_semantic_review import source_packet
from vnext.canonical import content_hash
from vnext.capacity_update_input import source_equivalence
from vnext.d04_native_assessment import native_source


def seal(source):
    source['semantic_source_id'] = content_hash(value={
        k: v for k, v in source.items() if k != 'semantic_source_id'})
    return source


def pair(metric='D04'):
    source = source_packet()
    source.update(metric_id=metric, source_proofs=[{
        'source_url': 'https://data.sec.gov/api/xbrl/companyfacts/CIK0001463101.json',
        'accession': 'annual', 'document_name': 'CIK0001463101.json',
        'content_sha256': 'a' * 64, 'request_attempt_id': 'original',
        'request_repo_relative_path': 'saved/companyfacts.json'}])
    facts = {'source_url': source['source_proofs'][0]['source_url'],
        'accession': 'annual', 'company_id': source['company_id'],
        'document_name': 'CIK0001463101.json', 'request_attempt_id': 'original',
        'source_repo_relative_path': 'saved/companyfacts.json',
        'target_period': {'period_start': '2025-01-01', 'period_end': '2025-12-31'}}
    source['prepared_annual_input'].update(companyfacts_input=facts,
        original_input={'companyfacts_input': deepcopy(facts)})
    if metric == 'D04':
        source['record_type'] = 'D04_COMPLETE_SEMANTIC_SOURCE'
        source['prepared_annual_input']['table_input']['target_period'] = {
            'period_start': '2025-01-01', 'period_end': '2025-12-31', 'fiscal_year': 2025}
        source['documents'][0].update(language_candidate_block_indices=[], native_candidate_ordinals=[])
        source = native_source(seal(source), complete_response_contract=True)
    original = seal(source)
    current = deepcopy(original)
    current['source_proofs'][0]['request_attempt_id'] = 'new-capture'
    for annual in [current['prepared_annual_input'], current['prepared_annual_input']['original_input']]:
        annual['companyfacts_input']['request_attempt_id'] = 'new-capture'
    return seal(current), original

def fiscal_pair():
    current,original=pair()
    for source in (original,current):
        a=source['prepared_annual_input'];period=a['table_input']['target_period']
        a['filing']={'accessionNumber':'annual','primaryDocument':'annual.htm'}
        a['company_id']=source['company_id']
        proof={'source_url':'https://www.sec.gov/Archives/edgar/data/1463101/annual/annual.htm',
            'accession':'annual','document_name':'annual.htm','content_sha256':'c'*64}
        source['source_proofs'].append(proof)
        body={'record_type':'FISCAL_YEAR_LABEL_SOURCE_INSPECTION','schema_version':1,
            'primary_sha256':'c'*64,'companyfacts_sha256':'a'*64,'entity':'1463101','accession':'annual',
            'actual_period':{k:period[k] for k in ('period_start','period_end')},
            'status':'METADATA_LABEL_ONLY','dei_fiscal_year':2025,
            'companyfacts_fiscal_year_values':[2025],
            'companyfacts_rows':[{'locator':{'taxonomy':'us-gaap','concept':'Assets','unit':'USD','index':0},
                                 'fiscal_year_raw':2025,'period_end':'2025-12-31'}]}
        a['fiscal_year_label_resolution']['source_inspection']={**body,'inspection_id':content_hash(value=body)}
    current['source_proofs'][0].update(content_sha256='b'*64,request_repo_relative_path='saved/refreshed-companyfacts.json')
    for a in (current['prepared_annual_input'],current['prepared_annual_input']['original_input']):
        a['companyfacts_input']['source_repo_relative_path']='saved/refreshed-companyfacts.json'
    i=current['prepared_annual_input']['fiscal_year_label_resolution']['source_inspection'];i['companyfacts_sha256']='b'*64
    i['inspection_id']=content_hash(value={k:v for k,v in i.items() if k!='inspection_id'})
    return seal(current),seal(original)


class D04CompanyfactsProvenanceTest(unittest.TestCase):
    def test_refreshed_companyfacts_with_same_complete_fiscal_input_and_task_can_reuse(self):
        current,original=fiscal_pair();saved=deepcopy(original)
        receipt=source_equivalence(current=current,original=original)
        self.assertEqual(receipt['companyfacts_label_input_body_changes'][0]['original_sha256'],'a'*64)
        self.assertEqual(receipt['companyfacts_label_input_body_changes'][0]['current_sha256'],'b'*64)
        self.assertFalse(receipt['original_provider_bytes_rewritten'])
        self.assertFalse(receipt['new_provider_execution'])
        self.assertEqual(saved,original)

    def test_companyfacts_refresh_does_not_hide_fiscal_rows_body_period_or_binding_changes(self):
        for change in ('rows','label','inspection-id','proof-hash','body','period','descriptor','foreign-url','primary-hash'):
            current,original=fiscal_pair();a=current['prepared_annual_input'];i=a['fiscal_year_label_resolution']['source_inspection']
            if change=='rows':i['companyfacts_rows'][0]['period_end']='2024-12-31'
            elif change=='label':i['dei_fiscal_year']=2026
            elif change=='inspection-id':i['inspection_id']='sha256:'+'f'*64
            elif change=='proof-hash':current['source_proofs'][0]['content_sha256']='e'*64
            elif change=='body':current['source_proofs'][1]['content_sha256']='e'*64
            elif change=='period':a['table_input']['target_period']['period_end']='2026-12-31'
            elif change=='descriptor':a['companyfacts_input']['source_repo_relative_path']='unbound.json'
            elif change=='foreign-url':current['source_proofs'][0]['source_url']='https://data.sec.gov/api/xbrl/companyfacts/CIK0009999999.json'
            else:i['primary_sha256']='e'*64
            if change not in {'inspection-id'}:i['inspection_id']=content_hash(value={k:v for k,v in i.items() if k!='inspection_id'})
            with self.subTest(change=change),self.assertRaises(ValueError):
                source_equivalence(current=seal(current),original=original)

    def test_same_body_attempt_change_reuses_complete_original(self):
        current, original = pair()
        saved = deepcopy(original)
        receipt = source_equivalence(current=current, original=original)
        self.assertFalse(receipt['original_provider_bytes_rewritten'])
        self.assertFalse(receipt['new_provider_execution'])
        self.assertEqual(original, saved)
        self.assertEqual(receipt['original_source_id'], original['semantic_source_id'])

    def test_different_body_subject_period_or_path_still_rejected(self):
        for field in ['body', 'subject', 'period', 'path']:
            current, original = pair()
            if field == 'body': current['source_proofs'][0]['content_sha256'] = 'b' * 64
            elif field == 'subject': current['prepared_annual_input']['entity'] = '99999'
            elif field == 'period': current['prepared_annual_input']['table_input']['target_period']['period_end'] = '2026-12-31'
            else: current['prepared_annual_input']['companyfacts_input']['source_repo_relative_path'] = 'other.json'
            with self.subTest(field=field), self.assertRaises(ValueError):
                source_equivalence(current=seal(current), original=original)

    def test_attempt_must_match_its_original_source_proof(self):
        current, original = pair()
        current['prepared_annual_input']['companyfacts_input']['request_attempt_id'] = 'unbound'
        with self.assertRaisesRegex(ValueError, 'ANNUAL_SELECTION_CHANGED'):
            source_equivalence(current=seal(current), original=original)

    def test_other_annual_attempt_fields_are_not_globally_erased(self):
        current, original = pair()
        original['prepared_annual_input']['another_source'] = {'request_attempt_id': 'original'}
        current['prepared_annual_input']['another_source'] = {'request_attempt_id': 'new'}
        with self.assertRaisesRegex(ValueError, 'ANNUAL_SELECTION_CHANGED'):
            source_equivalence(current=seal(current), original=seal(original))

    def test_b13_policy_is_not_widened(self):
        current, original = pair('B13')
        with self.assertRaisesRegex(ValueError, 'ANNUAL_SELECTION_CHANGED'):
            source_equivalence(current=current, original=original)

    def test_refreshed_primary_submissions_with_same_full_task_can_reuse(self):
        current, original = pair()
        proof = {'source_url': 'https://data.sec.gov/submissions/CIK0001463101.json',
            'accession': '', 'document_name': 'CIK0001463101.json',
            'content_sha256': '1' * 64, 'request_attempt_id': 'old-index'}
        original['source_proofs'].append(proof)
        current['source_proofs'].append({**proof, 'content_sha256': '2' * 64,
                                       'request_attempt_id': 'fresh-index'})
        receipt = source_equivalence(current=seal(current), original=seal(original))
        self.assertFalse(receipt['new_provider_execution'])
        self.assertEqual(receipt['discovery_only_body_changes'][0]['source_url'], proof['source_url'])

    def test_discovery_refresh_cannot_hide_changed_task_or_other_metadata(self):
        for change in ['task', 'annual', 'foreign-cik', 'history-shard']:
            current, original = pair()
            url = ('https://data.sec.gov/submissions/CIK0001463101.json' if change in {'task','annual'}
                   else 'https://data.sec.gov/submissions/CIK0009999999.json' if change == 'foreign-cik'
                   else 'https://data.sec.gov/submissions/CIK0001463101-submissions-001.json')
            name = url.rsplit('/', 1)[-1]
            proof = {'source_url': url, 'accession': '', 'document_name': name,
                     'content_sha256': '1' * 64}
            original['source_proofs'].append(proof)
            current['source_proofs'].append({**proof, 'content_sha256': '2' * 64})
            if change == 'task': current['units'][0]['payload']['blocks'][0]['text'] = 'New relevant disclosure'
            if change == 'annual': current['prepared_annual_input']['table_input']['target_period']['period_end'] = '2026-12-31'
            with self.subTest(change=change), self.assertRaises(ValueError):
                source_equivalence(current=seal(current), original=seal(original))


if __name__ == '__main__':
    unittest.main()
