"""CLI period-loss controls; no network, ledger or constructed financial result."""
import contextlib
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.vnext_company import main


class HistoryOnlinePeriodGuardTest(unittest.TestCase):
    def args(self, *extra):
        return ['run', '--company', 'ford_motor_company', '--metric', 'B01',
                '--call-context', '/constructed/context-must-not-be-read.json',
                '--work-dir', '/constructed/state', '--output-dir', '/constructed/output', *extra]

    def test_history_online_range_refuses_before_public_online_or_call_context(self):
        with patch('vnext.company_online.run_online_company', side_effect=AssertionError('No online operation')) as online, \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            main(self.args('--period', 'fiscal-years', '--fiscal-year-start', '2021', '--fiscal-year-end', '2025'))
        self.assertEqual(caught.exception.code, 2)
        online.assert_not_called()

    def test_latest_online_cannot_silently_discard_either_year_bound(self):
        for extra in [('--fiscal-year-start', '2021'), ('--fiscal-year-end', '2025'),
                      ('--fiscal-year-start', '2021', '--fiscal-year-end', '2025')]:
            with self.subTest(extra=extra), patch('vnext.company_online.run_online_company',
                    side_effect=AssertionError('No online operation')) as online, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                main(self.args(*extra))
            self.assertEqual(caught.exception.code, 2)
            online.assert_not_called()

    def test_current_online_without_history_arguments_keeps_original_dispatch(self):
        with patch('vnext.company_online.run_online_company', return_value={'status': 'FLOW_COMPLETED'}) as online, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(self.args('--period', 'latest-complete-fy')), 0)
        self.assertEqual(online.call_args.kwargs['company_id'], 'ford_motor_company')
        self.assertEqual(online.call_args.kwargs['metric_ids'], ['B01'])
        self.assertEqual(online.call_args.kwargs['call_context'], Path('/constructed/context-must-not-be-read.json'))

    def test_saved_history_still_forwards_actual_requested_range(self):
        with patch('vnext.company_local.run_local', return_value={'status': 'FLOW_COMPLETED'}) as saved, \
                patch('vnext.company_online.run_online_company', side_effect=AssertionError('No online operation')) as online, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['run', '--company', 'ford_motor_company', '--metric', 'B01',
                '--period', 'fiscal-years', '--fiscal-year-start', '2021', '--fiscal-year-end', '2025',
                '--source-root', '/constructed/saved', '--work-dir', '/constructed/state',
                '--output-dir', '/constructed/output']), 0)
        self.assertEqual(saved.call_args.kwargs['period'], 'fiscal-years')
        self.assertEqual(saved.call_args.kwargs['fiscal_year_start'], 2021)
        self.assertEqual(saved.call_args.kwargs['fiscal_year_end'], 2025)
        online.assert_not_called()
