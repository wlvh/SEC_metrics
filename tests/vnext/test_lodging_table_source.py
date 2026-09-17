"""Three original annual layouts and source-level lodging counterexamples."""
import copy
import hashlib
import json
import re
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from sec_urls import accession_document_url
from vnext.annual_update import saved_source
from vnext.normal_annual_input import annual_period
from vnext.normal_annual_input_v2 import prepare_saved_annual_input
from vnext.normal_source_authority import verify_saved_source_proofs
from vnext.sources import raw_blob_record,source_reference_record
from vnext.lodging_table_source import inspect_lodging_table_source,prepare_saved_lodging_source


class LodgingTableSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arguments_by_year={};cls.results={}
        with original_sources_only():prepared=prepare_saved_annual_input(repo_root=ROOT,company_id='marriott_international')
        inventory=prepared['source_proofs'][0]
        block=json.loads((ROOT/inventory['request_repo_relative_path']).read_text())['filings']['recent']
        for year in [2023,2024,2025]:
            filing=next({k:v[i] for k,v in block.items()} for i,f in enumerate(block['form'])
                        if f=='10-K' and block['reportDate'][i]==str(year)+'-12-31')
            with original_sources_only():
                saved=saved_source(repo_root=ROOT,url=accession_document_url(cik=int(prepared['entity']),
                    accession=filing['accessionNumber'],document_name=filing['primaryDocument']),accession=filing['accessionNumber'])
                proof=saved['proof'];verify_saved_source_proofs(data_root=ROOT,proofs=[inventory,proof])
                blob=raw_blob_record(repo_root=ROOT,repo_relative_path=proof['request_repo_relative_path'],media_type='text/html')
                ref=source_reference_record(raw_blob=blob,company_id=prepared['company_id'],source_url=proof['source_url'],
                    accession=filing['accessionNumber'],document_name=filing['primaryDocument'],source_role='target_primary',request_attempt_id=proof['request_attempt_id'])
                args={'raw':saved['raw'],'blob':blob,'reference':ref,'filing':filing,'company_id':prepared['company_id'],
                      'cik':prepared['entity'],'period':annual_period(raw=saved['raw'],cik=prepared['entity'],filing=filing)}
                cls.arguments_by_year[year]=args
                cls.results[year]=inspect_lodging_table_source(**args)

    def changed(self,transform):
        args=copy.deepcopy(self.arguments_by_year[2025]);raw=transform(args['raw'])
        self.assertTrue(raw!=args['raw'],'Mutation did not change source bytes')
        blob={**args['blob'],'raw_asset_id':'sha256:'+hashlib.sha256(raw).hexdigest(),'byte_length':len(raw)}
        old=args['reference'];ref=source_reference_record(raw_blob=blob,company_id=old['company_id'],source_url=old['source_url'],
            accession=old['accession'],document_name=old['document_name'],source_role=old['source_role'],request_attempt_id=old['request_attempt_id'])
        args.update(raw=raw,blob=blob,reference=ref)
        with original_sources_only():return inspect_lodging_table_source(**args)

    def table_change(self,transform):
        span=self.results[2025]['selection']['context']['table_source_span'];a,b=span['start_byte'],span['end_byte']
        return self.changed(lambda raw:raw[:a]+transform(raw[a:b])+raw[b:])

    def test_three_real_originals_preserve_year_scope_raw_locators_and_page_split(self):
        expected={2023:('0.692','124.7',66),2024:('0.698','128.23',67),2025:('0.693','128.8',68)}
        for year,(occupancy,revpar,count) in expected.items():
            p=self.results[year];facts=p['selection']['facts']
            self.assertEqual((occupancy,revpar),(facts['B10']['value'],facts['B11']['value']))
            self.assertEqual(count,p['table_count'])
            self.assertFalse(p['ai_response_used']);self.assertFalse(p['qualification_credit']);self.assertFalse(p['native_run_created'])
            for f in facts.values():
                self.assertEqual({'property_population':'comparable','operating_scope':'systemwide','geography':'worldwide'},f['scope'])
                self.assertEqual(year,f['period']['fiscal_year'])
                self.assertTrue(f['source_witnesses']['geography']['raw_text'].startswith('\nWorldwide'))
                self.assertEqual(str(year),f['source_witnesses']['year']['text'])
        intro=self.results[2024]['selection']['context']['introduction']
        self.assertEqual(2,len(intro['blocks']));self.assertEqual(2,len(intro['pagination_omitted']))
        with original_sources_only():current=prepare_saved_lodging_source(repo_root=ROOT,company_id='marriott_international')
        self.assertEqual(self.results[2025]['selection']['facts'],current['component']['selection']['facts'])

    def test_extra_population_qualifier_cannot_keep_the_approved_scope(self):
        with self.assertRaises(ValueError):
            self.table_change(lambda raw:raw.replace(b'Comparable Systemwide Properties',b'Comparable Systemwide Properties excluding resorts'))

    def test_scope_label_in_another_table_cannot_bind_the_amount(self):
        span=self.results[2025]['selection']['context']['table_source_span'];a,b=span['start_byte'],span['end_byte']
        def move(raw):
            changed=raw[:a]+raw[a:b].replace(b'Comparable Systemwide Properties',b'Other Properties')+raw[b:]
            return changed.replace(b'</body>',b'<table><tr><td>Comparable Systemwide Properties</td></tr></table></body>',1)
        with self.assertRaisesRegex(ValueError,'POPULATION_SECTION_NOT_UNIQUE'):
            self.changed(move)

    def test_quoted_table_introduction_cannot_establish_current_period(self):
        block=self.results[2025]['selection']['context']['introduction']['blocks'][0]
        a,b=block['start_byte'],block['end_byte']
        with self.assertRaisesRegex(ValueError,'INTRODUCTION_UNPROVEN'):
            self.changed(lambda raw:raw[:a]+b'<q>'+raw[a:b]+b'</q>'+raw[b:])

    def test_competing_same_target_table_is_not_silently_ignored(self):
        span=self.results[2025]['selection']['context']['table_source_span'];a,b=span['start_byte'],span['end_byte']
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_COMPETING_TARGET'):
            self.changed(lambda raw:raw.replace(b'</body>',raw[a:b]+b'</body>',1))

    def test_duplicate_worldwide_row_is_ambiguous(self):
        def duplicate(table):
            rows=list(re.finditer(rb'<tr\b[^>]*>.*?</tr>',table,re.S))
            candidates=[m for m in rows if b'Worldwide' in m[0]]
            self.assertEqual(2,len(candidates));m=candidates[-1]
            return table[:m.end()]+m[0]+table[m.end():]
        with self.assertRaisesRegex(ValueError,'WORLDWIDE_ROW_NOT_UNIQUE'):
            self.table_change(duplicate)

    def test_actual_period_must_come_from_table_introduction_and_year_column(self):
        for before,after in [(b'properties for 2025, and 2025 compared to 2024',b'properties for 2024, and 2024 compared to 2023'),
                             (b'properties for 2025,',b'properties for the fourth quarter of 2025,')]:
            with self.subTest(after=after),self.assertRaises(ValueError):
                self.changed(lambda raw:raw.replace(before,after,1))

    def test_quarter_or_currency_override_in_local_note_is_not_ignored(self):
        span=self.results[2025]['selection']['context']['table_source_span'];end=span['end_byte']
        for note in [b'<p>(3)These statistics cover three months ended December 31, 2025.</p>',
                     b'<p>(3)All amounts are in Canadian dollars.</p>']:
            with self.subTest(note=note),self.assertRaises(ValueError):
                self.changed(lambda raw:raw[:end]+note+raw[end:])

    def test_currency_and_amount_unit_need_original_source_support(self):
        with self.assertRaisesRegex(ValueError,'DOLLAR_DEFINITION'):
            self.changed(lambda raw:raw.replace(b'constant U.S. dollar basis',b'constant Canadian dollar basis'))
        with self.assertRaises(ValueError):
            self.table_change(lambda raw:raw.replace(b'Occupancy',b'TEMP_ROLE').replace(b'Average Daily Rate',b'Occupancy').replace(b'TEMP_ROLE',b'Average Daily Rate'))

    def test_source_hash_and_full_document_cannot_be_replaced_by_same_numbers(self):
        args=copy.deepcopy(self.arguments_by_year[2025]);args['raw']+=b' '
        with self.assertRaisesRegex(ValueError,'SOURCE_BINDING_CONFLICT'):inspect_lodging_table_source(**args)
        with self.assertRaisesRegex(ValueError,'FULL_PRIMARY_REQUIRED'):
            self.changed(lambda raw:raw.replace(b'</body>',b'',1))


if __name__=='__main__':unittest.main()
