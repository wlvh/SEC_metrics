"""Ordinary C02 separates auditor independence from member qualification."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from vnext import c02_composition_text_results as api
from vnext import c02_board_composition_28_v3 as repaired
from vnext import historical_board_composition_v2 as previous
from vnext.canonical import sha256_bytes
from vnext.normal_run_v3 import prepare_case


ROOT = Path(__file__).resolve().parents[2]


def prepared(case):
    return api._prepared(**{k:v for k,v in case['text_arguments'].items()
                           if k != 'compiled_spec'})


def governance(proposals):
    return next((sid,p) for sid,p in proposals.items() if p.get('metric_id') == 'C02')


def selected_original(proposal):
    return {index for item in proposal['candidates'] for index in item['selected_source_blocks']}


class C02AuditorScopeFastTest(unittest.TestCase):
    def test_only_the_auditors_independence_is_excluded(self):
        own = frozenset({'audit','compensation'})
        other = ('The members of the Audit Committee believe the independent '
                 'external auditor is qualified.')
        self.assertIn('COMMITTEE_MEMBER_QUALIFICATION',
                      previous.statement_labels(other,own,period_start='2025-01-01'))
        self.assertEqual([],repaired.statement_labels(other,own,period_start='2025-01-01'))
        for auditor in ('outside auditor','public accounting firm'):
            text = f'The members of the Audit Committee believe the independent {auditor} is qualified.'
            self.assertEqual([],repaired.statement_labels(text,own,period_start='2025-01-01'))
        member = ('The members of the Audit Committee are independent and oversee '
                  'the Firm\'s independent external auditor.')
        self.assertIn('COMMITTEE_MEMBER_QUALIFICATION',
                      repaired.statement_labels(member,own,period_start='2025-01-01'))
        expert = ('The Board has determined that each member is financially literate '
                  'and is an audit committee financial expert as defined by the SEC.')
        self.assertIn('COMMITTEE_MEMBER_QUALIFICATION',
                      repaired.statement_labels(expert,own,period_start='2025-01-01'))

    def test_explicit_revision_cannot_change_another_metric_or_an_ungrouped_route(self):
        with self.assertRaisesRegex(ValueError,'ORDINARY_C02_AUDITOR_REVISION_SCOPE_WRONG_METRIC'):
            prepare_case(data_root=ROOT,company_id='jpmorgan_chase',metric_id='C02',
                         c02_composition=True,c02_auditor_revision=True)
        from vnext.ordinary_update_cycle import run_once
        with TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError,'UPDATE_C02_AUDITOR_REVISION_SCOPE_INVALID'):
                run_once(state_root=Path(temporary)/'state',source_root=ROOT,
                    company_id='jpmorgan_chase',metric_ids=['B01'],c02_auditor_revision=True)
            self.assertFalse((Path(temporary)/'state').exists())


class C02AuditorScopeMaterialTest(unittest.TestCase):
    def test_current_original_loses_only_the_auditor_decision_and_retains_member_facts(self):
        old = prepare_case(data_root=ROOT,company_id='jpmorgan_chase',metric_id='C02',
                           c02_composition=True,c02_grouped=True)
        same = prepare_case(data_root=ROOT,company_id='jpmorgan_chase',metric_id='C02',
                           c02_composition=True,c02_grouped=True,c02_auditor_revision=False)
        self.assertEqual(old,same)
        new = prepare_case(data_root=ROOT,company_id='jpmorgan_chase',metric_id='C02',
                           c02_composition=True,c02_grouped=True,c02_auditor_revision=True)
        a,b = prepared(old),prepared(new)
        sid,p = governance(a['proposals']); sid2,q = governance(b['proposals'])
        self.assertEqual(sid,sid2)
        self.assertEqual({3367},selected_original(p)-selected_original(q))
        self.assertEqual(set(),selected_original(q)-selected_original(p))
        self.assertIn(3409,selected_original(q))
        self.assertFalse(any(3367 in item['selected_source_blocks']+item['context_source_blocks']
                             for item in q['candidates']))
        args = {k:v for k,v in new['text_arguments'].items()
                if k not in ('compiled_spec','c02_selection_policy')}
        original = api.old.prepare_business_text_sources(metric_id='C02',**args)['documents'][sid]
        raw = new['text_arguments']['raw_bytes_by_id'][original['raw_asset_id']]
        for index in (3367,3409):
            block=original['blocks'][index]
            self.assertEqual(block['raw_span_sha256'],sha256_bytes(
                content=raw[block['raw_start_byte']:block['raw_end_byte']]))
        self.assertIn('retention of PwC',original['blocks'][3367]['text'])
        self.assertIn('financial expert',original['blocks'][3409]['text'])
        candidate=api.create_deterministic_text_candidate(**new['text_arguments'])
        evidence=api.build_text_evidence(candidate=candidate,**new['text_arguments'])
        self.assertEqual('PASS',evidence['status'])
        old_candidate=api.create_deterministic_text_candidate(**old['text_arguments'])
        with self.assertRaisesRegex(ValueError,'C02_COMPOSITION_CANDIDATE_REPLAY_CHANGED'):
            api.build_text_evidence(candidate=old_candidate,**new['text_arguments'])
        self.assertEqual('COMPOSITION_GROUPED_V3',new['input_binding']['c02_selection_policy'])
        self.assertEqual('catalog/r6/C02_board_disclosures_v4.md',new['spec_paths']['C02'])

    def test_unaffected_current_pfizer_selection_is_preserved(self):
        arguments=dict(data_root=ROOT,company_id='pfizer',metric_id='C02',
                       c02_composition=True,c02_grouped=True)
        a=prepared(prepare_case(**arguments))
        b=prepared(prepare_case(**arguments,c02_auditor_revision=True))
        _,p=governance(a['proposals']);_,q=governance(b['proposals'])
        self.assertEqual(selected_original(p),selected_original(q))
        self.assertEqual([x['text'] for x in p['candidates']],
                         [x['text'] for x in q['candidates']])


if __name__=='__main__':
    unittest.main()
