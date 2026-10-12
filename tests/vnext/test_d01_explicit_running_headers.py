"""Explicit D01 successor; constructed originals are not company acceptance."""
import copy
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_text_coverage import BODY, annual, binding
from tests.vnext.test_text_results import source_arguments
from vnext import d01_emphasis_results as d01
from vnext import ordinary_saved_result as saved
from vnext import ordinary_current_update as update
from vnext.canonical import content_hash
from vnext.risk_signals import risk_factor_headings
from vnext.specs import compile_spec_file
from vnext.text_coverage import build_text_document


class ExplicitD01HeaderTest(unittest.TestCase):
    def args(self, *, additions='<p><b>Parts I and II</b></p>'):
        body = BODY.replace('<p>A supply constraint could affect production.</p>',
            '<p><b>Supply constraints may affect production</b>. Actual narrative stays separate.</p>'+additions)
        args = source_arguments(binding(annual(body)))
        spec = compile_spec_file(path=REPO_ROOT/'catalog/r6/D01_risk_factor_headings.md', dependency_specs={})
        scope = spec['compiled']['required_claims']
        args['compiled_spec'] = spec
        args['target'].update(scope=scope, scope_key=content_hash(value=scope))
        return args

    def candidate(self, policy=None, **kwargs):
        args=self.args(**kwargs)
        if policy is not None:args['d01_emphasis_policy']=policy
        return args,d01.create_deterministic_text_candidate(**args)

    def test_explicit_successor_excludes_complete_header_default_and_v2_unchanged(self):
        oldargs,old=self.candidate()
        v2args,v2=self.candidate(d01.POLICY)
        args,new=self.candidate(d01.RUNNING_HEADER_POLICY)
        self.assertEqual(old,v2)
        self.assertEqual([c['text'] for c in old['selected'].values()],
            ['Supply constraints may affect production','Parts I and II'])
        self.assertEqual([c['text'] for c in new['selected'].values()],['Supply constraints may affect production'])
        self.assertNotEqual(old['candidate_hash'],new['candidate_hash'])
        self.assertEqual(d01.verify_deterministic_text_candidate(candidate=new,**args),new)
        self.assertEqual(d01.verify_deterministic_text_candidate(candidate=old,**oldargs),old)
        self.assertEqual(d01.verify_deterministic_text_candidate(candidate=v2,**v2args),v2)

    def test_evidence_rebuilds_the_same_explicit_selection_and_rejects_old_candidate(self):
        args,new=self.candidate(d01.RUNNING_HEADER_POLICY)
        evidence=d01.build_text_evidence(candidate=new,**args)
        self.assertTrue(evidence)
        _,old=self.candidate(d01.POLICY)
        with self.assertRaisesRegex(ValueError,'CANDIDATE_REPLAY_CHANGED'):
            d01.build_text_evidence(candidate=old,**args)

    def test_risk_sentence_with_the_same_prefix_is_kept_and_exact_span_preserved(self):
        title='Parts I and II of the supply chain may be disrupted'
        args,new=self.candidate(d01.RUNNING_HEADER_POLICY,additions='<p><b>'+title+'</b>. Later explanation.</p>')
        claim=new['selected']['excerpt_1'];self.assertEqual(claim['text'],title)
        raw=next(iter(args['raw_bytes_by_id'].values()))
        self.assertIn(title.encode(),raw[claim['raw_start_byte']:claim['raw_end_byte']])

    def test_underlined_heading_survives_while_repeated_combined_headers_do_not(self):
        args,new=self.candidate(d01.RUNNING_HEADER_POLICY,additions=
            '<p><b>Parts I and II</b></p><p><span style="text-decoration:underline">Cybersecurity threats may affect operations</span>. Explanation.</p><p><b>Parts I and II</b></p>')
        self.assertEqual([c['text'] for c in new['selected'].values()],
            ['Supply constraints may affect production','Cybersecurity threats may affect operations'])
        d01.build_text_evidence(candidate=new,**args)

    def test_wrong_entity_period_missing_section_and_changed_raw_still_refuse(self):
        args,_=self.candidate(d01.RUNNING_HEADER_POLICY)
        variants=[]
        changed=copy.deepcopy(args);changed['target']['entity']='54321';variants.append(changed)
        changed=copy.deepcopy(args);changed['target']['period_end']='2024-12-31';variants.append(changed)
        changed=copy.deepcopy(args);rawid=next(iter(changed['raw_bytes_by_id']))
        changed['raw_bytes_by_id'][rawid]=changed['raw_bytes_by_id'][rawid].replace(b'Item 1A. Risk Factors',b'Appendix Risks');variants.append(changed)
        for changed in variants:
            with self.subTest(target=changed['target']),self.assertRaises(ValueError):
                d01.create_deterministic_text_candidate(**changed)

    def test_changed_document_and_non_boolean_policy_are_refused(self):
        source=binding(annual(BODY));document=build_text_document(**source)
        document['period_end']='2024-12-31'
        with self.assertRaisesRegex(ValueError,'HASH_CHANGED'):
            risk_factor_headings(document=document,exclude_combined_part_headers=True)
        with self.assertRaisesRegex(ValueError,'POLICY_INVALID'):
            risk_factor_headings(document=document,exclude_combined_part_headers=1)

    def test_explicit_company_factory_gate_does_not_open_default_d01(self):
        self.assertIn('D01',saved.EXPLICIT_CASE_METRICS)
        self.assertNotIn('D01',saved.SAVED_METRIC_IDS)
        with TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'ROUTE_NOT_IMPLEMENTED'):
                saved.create_saved_result(source_root=REPO_ROOT,output_root=Path(temp)/'result',company_id='marriott_international',metric_id='D01')
            with self.assertRaisesRegex(ValueError,'METRIC_UNSUPPORTED'):
                update.run_once(source_root=REPO_ROOT,state_root=Path(temp)/'state',company_id='marriott_international',metric_id='D01')
            with self.assertRaisesRegex(ValueError,'METRIC_UNSUPPORTED'):
                update.run_once(source_root=REPO_ROOT,state_root=Path(temp)/'state',company_id='marriott_international',metric_id='D01',fiscal_year=2024)
            with patch.object(update,'_configuration',side_effect=RuntimeError('Reached explicit path')):
                result=update.run_once(source_root=REPO_ROOT,state_root=Path(temp)/'state',company_id='marriott_international',metric_id='D01',fiscal_year=2024,case_factory=lambda **kwargs:None)
                self.assertEqual(result['reason'],'Reached explicit path')

    def test_unknown_or_wrong_metric_successor_policy_is_rejected(self):
        args=self.args();args['d01_emphasis_policy']='UNKNOWN'
        with self.assertRaisesRegex(ValueError,'POLICY_INVALID'):d01.create_deterministic_text_candidate(**args)
        args['d01_emphasis_policy']=d01.RUNNING_HEADER_POLICY
        args['compiled_spec']['compiled']['metric_id']='D02'
        with self.assertRaisesRegex(ValueError,'SPEC_INVALID'):d01.create_deterministic_text_candidate(**args)


if __name__=='__main__':unittest.main()
