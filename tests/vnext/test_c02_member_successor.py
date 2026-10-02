"""Ordinary C02 receives the shared member-clause scope repair."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from vnext import c02_board_composition_28_v3 as old
from vnext import c02_board_composition_28_v4 as current
from vnext import c02_composition_text_results as api
from vnext.normal_run_v3 import prepare_case
from tests.vnext.test_c02_auditor_successor import prepared, governance, selected_original


ROOT = Path(__file__).resolve().parents[2]


class C02MemberScopeFastTest(unittest.TestCase):
    def test_unreviewed_member_rule_cannot_write_new_runs_or_update_state(self):
        from vnext.normal_run_v3 import create_normal_run, _create_case_run
        from vnext.ordinary_update_cycle import run_once
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, 'ORDINARY_C02_MEMBER_RULE_VALIDATION_SUSPENDED'):
                create_normal_run(data_root=root/'data', run_dir=root/'run',
                    company_id='jpmorgan_chase', metric_id='C02', c02_composition=True,
                    c02_grouped=True, c02_auditor_revision=True, c02_member_revision=True)
            with self.assertRaisesRegex(ValueError, 'ORDINARY_C02_MEMBER_RULE_VALIDATION_SUSPENDED'):
                _create_case_run(data_root=root/'data', run_dir=root/'run',
                    company_id='jpmorgan_chase', metric_id='C02',
                    case={'input_binding':{'c02_selection_policy':'COMPOSITION_GROUPED_V4'}},
                    requirement={})
            with self.assertRaisesRegex(ValueError, 'UPDATE_C02_MEMBER_RULE_VALIDATION_SUSPENDED'):
                run_once(state_root=root/'state', source_root=ROOT,
                    company_id='jpmorgan_chase', metric_ids=['C02'],
                    c02_auditor_revision=True, c02_member_revision=True)
            self.assertEqual([], list(root.iterdir()))

    def test_disclaimer_is_excluded_and_member_determinations_are_preserved(self):
        own = frozenset({'audit', 'compensation'})
        disclaimer = ('The members of the Audit Committee are not professionally engaged '
                      'in the practice of accounting or auditing; as noted above, the '
                      'Audit Committee’s responsibility is to monitor and oversee these processes.')
        self.assertIn('COMMITTEE_COMPOSITION_STATEMENT',
                      old.statement_labels(disclaimer, own, period_start='2025-01-01'))
        self.assertEqual([], current.statement_labels(disclaimer, own, period_start='2025-01-01'))
        for status in ('independent', 'financially literate', 'not employees of the Company'):
            self.assertIn('COMMITTEE_COMPOSITION_STATEMENT', current.statement_labels(
                'The members of the Audit Committee are ' + status + '.',
                own, period_start='2025-01-01'))
        self.assertIn('COMMITTEE_COMPOSITION_STATEMENT', current.statement_labels(
            'The members of the Audit Committee include Mr. Smith and Ms. Jones.',
            own, period_start='2025-01-01'))
        self.assertEqual([], current.statement_labels(
            'The members of the Audit Committee are responsible for overseeing the independent external auditor.',
            own, period_start='2025-01-01'))

    def test_explicit_successor_requires_its_dependencies_and_correct_metric(self):
        with self.assertRaisesRegex(ValueError, 'ORDINARY_C02_MEMBER_REVISION_SCOPE_WRONG_METRIC'):
            prepare_case(data_root=ROOT, company_id='jpmorgan_chase', metric_id='C02',
                         c02_composition=True, c02_grouped=True, c02_member_revision=True)
        from vnext.ordinary_update_cycle import run_once
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'state'
            with self.assertRaisesRegex(ValueError, 'UPDATE_C02_MEMBER_REVISION_SCOPE_INVALID'):
                run_once(state_root=path, source_root=ROOT, company_id='jpmorgan_chase',
                         metric_ids=['C02'], c02_member_revision=True)
            self.assertFalse(path.exists())


class C02MemberScopeMaterialTest(unittest.TestCase):
    def test_current_original_loses_only_the_disclaimer_and_retains_actual_qualifications(self):
        kwargs = dict(data_root=ROOT, company_id='jpmorgan_chase', metric_id='C02',
                      c02_composition=True, c02_grouped=True, c02_auditor_revision=True)
        prior = prepare_case(**kwargs)
        same = prepare_case(**kwargs, c02_member_revision=False)
        self.assertEqual(prior, same)
        new = prepare_case(**kwargs, c02_member_revision=True)
        a, b = prepared(prior), prepared(new)
        sid, p = governance(a['proposals'])
        sid2, q = governance(b['proposals'])
        self.assertEqual(sid, sid2)
        self.assertEqual({3436}, selected_original(p) - selected_original(q))
        self.assertEqual(set(), selected_original(q) - selected_original(p))
        self.assertIn(3409, selected_original(q))
        self.assertFalse(any(3436 in x['selected_source_blocks'] + x['context_source_blocks']
                             for x in q['candidates']))
        self.assertFalse(any(3367 in x['selected_source_blocks'] + x['context_source_blocks']
                             for x in q['candidates']))
        candidate = api.create_deterministic_text_candidate(**new['text_arguments'])
        self.assertEqual('PASS', api.build_text_evidence(
            candidate=candidate, **new['text_arguments'])['status'])
        with self.assertRaisesRegex(ValueError, 'C02_COMPOSITION_CANDIDATE_REPLAY_CHANGED'):
            api.build_text_evidence(candidate=api.create_deterministic_text_candidate(
                **prior['text_arguments']), **new['text_arguments'])
        self.assertEqual('COMPOSITION_GROUPED_V4', new['input_binding']['c02_selection_policy'])
        self.assertEqual('catalog/r6/C02_board_disclosures_v5.md', new['spec_paths']['C02'])


if __name__ == '__main__':
    unittest.main()
