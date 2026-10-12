"""Explicit excerpt capacity, original contracts and real replay; no acceptance."""
import copy,json
from pathlib import Path
import tempfile
import unittest

from tests.vnext import test_text_results as fixtures
from tests.vnext.test_text_coverage import BODY,annual,binding
from vnext.specs import compile_spec,compile_spec_file,SpecError
from vnext.text_results import create_deterministic_text_candidate,replay_text_result,verify_text_result,render_text_payload
from vnext.canonical import canonical_json_bytes
from vnext.records import validate_record

ROOT=Path(__file__).resolve().parents[2]
RENDERER='ORDERED_NEWLINE_128_V2'


def successor_front():
    front=fixtures.spec_front();front['quality_rule']={'deterministic_text_method':'RISK_FACTOR_HEADINGS_V1'}
    front['text_policy'].update(renderer=RENDERER,max_items=128)
    return front


def arguments(count=68,front=None):
    source=BODY.replace('<p>A supply constraint could affect production.</p>',
        ''.join('<p><b>Risk number %s</b>. Disclosure remains separate.</p>' % i for i in range(count)))
    return fixtures.source_arguments(binding(annual(source)),front=front or successor_front())


class TextItemCapacityTest(unittest.TestCase):
    def test_68_full_titles_roundtrip_without_cutting_or_changing_old_encoding_fields(self):
        args=arguments();candidate=create_deterministic_text_candidate(**args)
        self.assertEqual(len(candidate['selected']),68)
        reviewed=fixtures.reviewed(args,candidate=candidate)
        result,trace,observations=replay_text_result(**reviewed)
        self.assertEqual(len(observations),68)
        self.assertEqual(result['text_payload']['renderer'],RENDERER)
        self.assertEqual(result['value'],'\n'.join('Risk number %s' % i for i in range(68)))
        self.assertEqual(result['value_kind'],'TEXT_V1')
        self.assertEqual(set(result['text_payload']),{'version','content_kind','renderer','items',
            'coverage_hashes','candidate_hash','review_unit_hash','approval_effect_hash'})
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'records.json';path.write_bytes(canonical_json_bytes(value={'result':result,'trace':trace,'observations':observations}))
            stored=json.loads(path.read_bytes())
            self.assertEqual(verify_text_result(**stored,**reviewed),(result,trace,observations))
            self.assertEqual(validate_record(record=stored['result']),result)

    def test_128_items_are_supported_but_129_are_not_silently_trimmed(self):
        for count in (128,129):
            with self.subTest(count=count):
                args=arguments(count)
                if count==128:
                    candidate=create_deterministic_text_candidate(**args)
                    result,_,obs=replay_text_result(**fixtures.reviewed(args,candidate=candidate))
                    self.assertEqual(len(obs),128);self.assertEqual(len(result['text_payload']['items']),128)
                else:
                    with self.assertRaisesRegex(ValueError,'HEADINGS_EXCEED_BOUND'):
                        create_deterministic_text_candidate(**args)

    def test_original_64_contract_and_smaller_successor_contract_remain_real_limits(self):
        for renderer,max_items in (('ORDERED_NEWLINE_V1',64),(RENDERER,64)):
            front=successor_front();front['text_policy'].update(renderer=renderer,max_items=max_items)
            with self.subTest(renderer=renderer),self.assertRaisesRegex(ValueError,'HEADINGS_EXCEED_BOUND'):
                create_deterministic_text_candidate(**arguments(68,front))
        front=fixtures.spec_front();front['text_policy']['max_items']=65
        with self.assertRaises(SpecError):fixtures.compiled(front)

    def test_old_policy_result_and_trace_are_unchanged(self):
        args=fixtures.reviewed();before=replay_text_result(**args)
        self.assertEqual(before,verify_text_result(result=before[0],trace=before[1],observations=before[2],**args))
        self.assertEqual(before[0]['text_payload']['renderer'],'ORDERED_NEWLINE_V1')
        self.assertEqual(len(before[0]['text_payload']['items']),2)
        original=compile_spec_file(path=ROOT/'catalog/r6/D01_risk_factor_headings.md',dependency_specs={})
        self.assertEqual(original['compiled']['text_policy']['max_items'],64)
        self.assertEqual(original['compiled']['text_policy']['renderer'],'ORDERED_NEWLINE_V1')

    def test_renderer_and_compiler_refuse_unknown_capacity_bad_types_and_overlimit(self):
        for renderer,limit in (('unknown',128),(RENDERER,129),(RENDERER,True),([],128)):
            front=successor_front();front['text_policy'].update(renderer=renderer,max_items=limit)
            with self.subTest(renderer=renderer,limit=limit),self.assertRaises(SpecError):fixtures.compiled(front)
        args=arguments();result,_,_=replay_text_result(**fixtures.reviewed(args,candidate=create_deterministic_text_candidate(**args)))
        old=copy.deepcopy(result['text_payload']);old['renderer']='ORDERED_NEWLINE_V1'
        with self.assertRaisesRegex(ValueError,'ITEMS_INVALID'):render_text_payload(payload=old)
        unknown=copy.deepcopy(result['text_payload']);unknown['renderer']='unknown'
        with self.assertRaisesRegex(ValueError,'PROTOCOL_UNSUPPORTED'):render_text_payload(payload=unknown)
        wrong=copy.deepcopy(result['text_payload']);wrong['renderer']=[]
        with self.assertRaisesRegex(ValueError,'PROTOCOL_UNSUPPORTED'):render_text_payload(payload=wrong)

    def test_new_renderer_cannot_be_bound_to_an_old_or_smaller_spec_in_direct_builder(self):
        from vnext.text_results import build_text_result_and_trace
        args=arguments();result,_,_=replay_text_result(**fixtures.reviewed(args,candidate=create_deterministic_text_candidate(**args)))
        front=successor_front();front['text_policy'].update(renderer='ORDERED_NEWLINE_V1',max_items=64)
        old=fixtures.compiled(front)
        with self.assertRaisesRegex(ValueError,'TEXT_PAYLOAD_SPEC_POLICY_CHANGED'):
            build_text_result_and_trace(compiled_spec=old,target=args['target'],payload=result['text_payload'])
        front['text_policy'].update(renderer=RENDERER,max_items=64)
        smaller=fixtures.compiled(front)
        with self.assertRaisesRegex(ValueError,'TEXT_PAYLOAD_SPEC_ITEM_LIMIT'):
            build_text_result_and_trace(compiled_spec=smaller,target=args['target'],payload=result['text_payload'])

    def test_character_bound_and_source_coverage_are_not_relaxed_by_more_items(self):
        front=successor_front();front['text_policy']['max_text_chars']=20
        with self.assertRaisesRegex(ValueError,'CONTENT_EXCEEDS_BOUND'):
            create_deterministic_text_candidate(**arguments(3,front))
        front=successor_front();front['text_policy']['max_text_chars']=64001
        with self.assertRaises(SpecError):fixtures.compiled(front)
        args=arguments();changed=copy.deepcopy(args)
        changed['target']['entity']='999'
        with self.assertRaisesRegex(ValueError,'filing identity differs from registry authority'):
            create_deterministic_text_candidate(**changed)

    def test_new_catalog_changes_only_explicit_capacity_not_business_selection(self):
        old=compile_spec_file(path=ROOT/'catalog/r6/D01_risk_factor_headings.md',dependency_specs={})
        new=compile_spec_file(path=ROOT/'catalog/ordinary_risk_headings/D01_128.md',dependency_specs={})
        original=copy.deepcopy(old['compiled']);successor=copy.deepcopy(new['compiled'])
        successor['text_policy']['renderer']=original['text_policy']['renderer']
        successor['text_policy']['max_items']=original['text_policy']['max_items']
        self.assertEqual(successor,original)
        self.assertNotEqual(old['spec_closure_hash'],new['spec_closure_hash'])
