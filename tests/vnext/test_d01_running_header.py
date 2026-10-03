"""Pinned page-label exclusion, preserved headings and explicit successor."""
import unittest
from pathlib import Path
from unittest.mock import patch

from vnext.canonical import content_hash
from vnext import d01_running_header_28_v1 as new
from vnext import risk_signals as old
from vnext.normal_run_v3 import text_api


def document(texts):
    data = {'company_id':'test', 'period_end':'2025-12-31', 'source_reference_id':'test-ref',
        'raw_asset_id':'test-raw', 'registrant_names':['Test Company'], 'source_reasons':[],
        'sections':{'ITEM_1A':{'status':'LOCATED','candidates':[{'start_block':0,'end_block_exclusive':len(texts)}]}},
        'blocks':[{'block_index':i,'linked':False,'leading_emphasis':{'text':s,
            'raw_start_byte':i*100,'raw_end_byte':i*100+len(s),'raw_span_sha256':'test-span'}} for i,s in enumerate(texts)]}
    return {**data,'text_document_id':content_hash(value=data)}


class D01RunningHeaderTest(unittest.TestCase):
    def test_two_part_labels_excluded_while_frozen_default_unchanged(self):
        doc = document(['Part I','Parts I and II','Operational Risk','Parts II and III'])
        self.assertEqual(['Parts I and II','Operational Risk','Parts II and III'],
                         [x['text'] for x in old.risk_factor_headings(document=doc)['headings']])
        self.assertEqual(['Operational Risk'],[x['text'] for x in new.risk_factor_headings(document=doc)['headings']])

    def test_real_heading_with_part_words_and_repeated_locators_retained(self):
        texts = ['Parts I and II could create risk','Parts of our business are affected','Credit Risk','Credit Risk']
        doc = document(texts)
        self.assertEqual(old.risk_factor_headings(document=doc),new.risk_factor_headings(document=doc))
        self.assertEqual(2,len(new.risk_factor_headings(document=doc)['headings'][-1]['locators']))

    def test_tampered_document_is_not_filtered_into_acceptance(self):
        doc = document(['Parts I and II','Credit Risk']);doc['blocks'][0]['leading_emphasis']['text']='Credit Risk'
        with self.assertRaisesRegex(ValueError,'TEXT_DOCUMENT_HASH_CHANGED'):
            new.risk_factor_headings(document=doc)

    def test_source_compiler_keeps_exact_pinned_substitutions(self):
        self.assertEqual(new.SEVERAL_PARTS,new.risk_factor_headings.historical_substitutions)
        self.assertEqual(new.SELECTOR_IMPORT,new.derive_candidate.historical_substitutions)
        with self.assertRaisesRegex(ValueError,'SUBSTITUTION_NOT_FOUND_ONCE'):
            new._successor(old.risk_factor_headings,(('not-existing-code','x'),))

    def test_disk_code_drift_refused_before_successor_construction(self):
        original = Path.read_text
        target = Path(old.risk_factor_headings.__code__.co_filename)
        def changed(path,*args,**kwargs):
            text=original(path,*args,**kwargs)
            return text.replace('reasons = list(document["source_reasons"])','reasons = []') if path==target else text
        with patch.object(Path,'read_text',changed):
            with self.assertRaisesRegex(ValueError,'SOURCE_IS_NOT_LOADED_CODE'):
                new._successor(old.risk_factor_headings,new.SEVERAL_PARTS)

    def test_shared_text_api_default_and_wrong_metric_are_preserved(self):
        from vnext import d01_emphasis_results,d01_emphasis_results_v3
        self.assertIs(d01_emphasis_results,text_api('D01')[0])
        self.assertIs(d01_emphasis_results_v3,text_api('D01',d01_running_header=True)[0])
        with self.assertRaisesRegex(ValueError,'WRONG_METRIC'):
            text_api('C02',d01_running_header=True)


if __name__=='__main__':
    unittest.main()
