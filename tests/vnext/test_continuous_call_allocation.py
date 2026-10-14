"""Ordinary shared-budget reservation controls; no real provider or SEC I/O."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vnext.canonical import content_hash
from vnext.continuous_call_ledger import recorded_ledger
from vnext.invocation_control import _exclusive_write_json
from tests.vnext import test_continuous_call_ledger as existing


class ContinuousAllocationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = (Path(self.tmp.name)/'ledger').resolve()
        self.ledger = recorded_ledger(root=self.root, limits=(2, 2, 2))
        self.fixture = existing.ContinuousCallLedgerTest()
        self.tasks = [{'task_id':'marriott/D02/FY2025','channel':'PROVIDER',
                       'company_id':'marriott_international','metric_id':'D02','fiscal_year':2025}]

    def reservation(self, tasks=None, counts=(1, 1, 0)):
        body = {'record_type':'CONTINUOUS_CALL_ALLOCATION_V1',
                'binding_id':self.ledger.binding['binding_id'],
                'budget_root':str(self.root),'execution_mode':'RECORDED_TEST_ONLY',
                'executor':'issue47','approval_url':'recorded-test-only',
                'maximum_counts':list(counts),'maximum_request_input_tokens':20,
                'maximum_total_input_tokens':30,'maximum_output_tokens':4096,
                'tasks':self.tasks if tasks is None else tasks,
                'counts_at_reservation':[0,0,0]}
        return {**body,'allocation_id':content_hash(value=body)}

    def install_fixture(self, value=None):
        _exclusive_write_json(path=self.root/'history-20261014-allocation.json',
                              value=value or self.reservation())

    def claim(self, name, **options):
        return self.ledger.claim(channel='PROVIDER',request_digest=content_hash(value=name),
            requirement=existing.REQ,plan_id=content_hash(value={'plan':name}),
            purpose='remaining_development_feasibility',**options)

    def allocated(self, name='allocated', **options):
        selected={'budget_allocation_id':self.reservation()['allocation_id'],
                  'budget_allocation_task':self.tasks[0],
                  'allocation_executor':'issue47','estimated_input_tokens':12}
        selected.update(options)
        return self.claim(name, **selected)

    def test_unallocated_claim_cannot_spend_reserved_balance(self):
        with self.ledger.locked():
            self.install_fixture()
            path,intent=self.claim('outside-1');self.fixture.terminal(self.ledger,path,intent)
            with self.assertRaisesRegex(ValueError,'RESERVED_BALANCE'):
                self.claim('outside-2')

    def test_reservation_is_idempotent_under_original_lock(self):
        from vnext.continuous_call_allocation import reserve
        with self.ledger.locked():
            first=reserve(self.ledger,self.reservation())
            self.assertEqual(first,reserve(self.ledger,self.reservation()))
            self.assertEqual([0,0,0],self.ledger.snapshot()['counts'])
        with recorded_ledger(root=self.root,limits=(2,2,2)).locked() as again:
            self.assertEqual([1,1,0],again.snapshot()['allocation']['reserved_counts'])
        with self.assertRaisesRegex(ValueError,'LOCK_REQUIRED'):
            reserve(self.ledger,self.reservation())

    def test_allocated_claim_consumes_once_even_when_failed(self):
        with self.ledger.locked():
            self.install_fixture();path,intent=self.allocated()
            self.fixture.terminal(self.ledger,path,intent)
            state=self.ledger.snapshot()
            self.assertEqual([1,1,0],state['counts'])
            self.assertEqual([0,0,0],state['allocation']['reserved_counts'])
            with self.assertRaisesRegex(ValueError,'TASK_CONSUMED'):
                self.allocated('new-digest-cannot-reset-task')
            self.claim('outside-still-has-its-one-slot')

    def test_wrong_executor_scope_id_or_tokens_reject_before_claim(self):
        changes=[{'allocation_executor':'issue28'},
                 {'budget_allocation_id':'unknown'},
                 {'budget_allocation_task':{**self.tasks[0],'metric_id':'B13'}},
                 {'estimated_input_tokens':21}, {'estimated_input_tokens':None}]
        with self.ledger.locked():
            self.install_fixture()
            for change in changes:
                with self.subTest(change=change),self.assertRaises(ValueError):
                    self.allocated(**change)
            self.assertEqual([0,0,0],self.ledger.snapshot()['counts'])

    def test_pending_claim_keeps_reservation_consumption_and_original_stop(self):
        with self.ledger.locked():
            self.install_fixture();self.allocated()
        with recorded_ledger(root=self.root,limits=(2,2,2)).locked() as again:
            state=again.snapshot()
            self.assertEqual([1,1,0],state['counts'])
            self.assertEqual([0,0,0],state['allocation']['reserved_counts'])
            self.assertEqual(['PROVIDER'],state['stopped_channels'])

    def test_changed_record_or_overallocation_cannot_be_used(self):
        from vnext.continuous_call_allocation import reserve
        with self.ledger.locked():
            path,intent=self.claim('before-reservation');self.fixture.terminal(self.ledger,path,intent)
            tasks=[self.tasks[0],{**self.tasks[0],'task_id':'other','fiscal_year':2024}]
            value=self.reservation(tasks=tasks,counts=(2,2,0))
            value.pop('allocation_id');value['counts_at_reservation']=[1,1,0]
            value['allocation_id']=content_hash(value=value)
            with self.assertRaisesRegex(ValueError,'COUNT_EXCEEDED'):
                reserve(self.ledger,value)
            self.install_fixture();(self.root/'history-20261014-allocation.json').write_text('{}')
            with self.assertRaises(ValueError):self.ledger.snapshot()

    def test_total_input_upper_bound_is_shared_between_allocated_tasks(self):
        tasks=[self.tasks[0],{**self.tasks[0],'task_id':'other','fiscal_year':2024}]
        with self.ledger.locked():
            value=self.reservation(tasks=tasks,counts=(2,2,0));self.install_fixture(value)
            options={'budget_allocation_id':value['allocation_id'],'estimated_input_tokens':20}
            path,intent=self.allocated(**options);self.fixture.terminal(self.ledger,path,intent)
            with self.assertRaisesRegex(ValueError,'TOTAL_INPUT_EXCEEDED'):
                self.allocated('second',budget_allocation_task=tasks[1],**options)

    def test_new_allocation_does_not_consume_or_reopen_old_batch33_groups(self):
        from vnext import continuous_batch33
        with self.ledger.locked():
            self.install_fixture();(self.root/'batch33-authorization.json').write_text('{}')
            with patch.object(continuous_batch33,'read_authorization',return_value={'original_stop_ordinal':0}):
                path,intent=self.allocated();self.fixture.terminal(self.ledger,path,intent)
                self.assertNotIn('batch_authorization_id',intent)
                self.assertEqual([1,1,0],self.ledger.snapshot()['counts'])
                self.assertFalse(self.ledger._batch_observation[1]['resumed'])
                self.assertEqual({},self.ledger._batch_observation[1]['attempts'])

    def test_budget_record_does_not_open_new_metric_transport(self):
        from vnext.current_request_configuration import load_current_configuration,live_scope
        from vnext.request_limits import DEFAULT_LIMITS
        from tests.vnext.common import REPO_ROOT
        configuration=load_current_configuration(repo_root=REPO_ROOT)
        for metric in ('D02','E01'):
            with self.subTest(metric=metric),self.assertRaisesRegex(ValueError,'LIVE_EXECUTION_NOT_AUTHORIZED'):
                live_scope(configuration=configuration,metric_id=metric,limits=DEFAULT_LIMITS)

    def test_sec_reservation_consumes_the_same_sec_counter(self):
        sec={'task_id':'macys/SEC/FY2019','channel':'SEC','company_id':'macys','url':'recorded-test-only'}
        with self.ledger.locked():
            value=self.reservation(tasks=self.tasks+[sec],counts=(1,1,1));self.install_fixture(value)
            with self.assertRaisesRegex(ValueError,'REQUEST_SCOPE_INVALID'):
                self.ledger.claim(channel='SEC',request_digest=content_hash(value='wrong-sec'),
                    requirement=existing.REQ,plan_id=content_hash(value='wrong-sec-plan'),
                    purpose='remaining_development_feasibility',budget_allocation_id=value['allocation_id'],
                    budget_allocation_task={**sec,'url':'outside-the-approved-url'},allocation_executor='issue47')
            self.assertEqual([0,0,0],self.ledger.snapshot()['counts'])
            path,intent=self.ledger.claim(channel='SEC',request_digest=content_hash(value='sec'),
                requirement=existing.REQ,plan_id=content_hash(value='sec-plan'),
                purpose='remaining_development_feasibility',budget_allocation_id=value['allocation_id'],
                budget_allocation_task=sec,allocation_executor='issue47')
            state=self.ledger.snapshot()
            self.assertEqual([0,0,1],state['counts'])
            self.assertEqual([1,1,0],state['allocation']['reserved_counts'])
            self.assertEqual(['SEC'],state['stopped_channels'])
