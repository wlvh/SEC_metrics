"""Prompt identity/authority checks, without model calls or changing acceptance."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from vnext import annual_continuity as flow
from vnext import reader_input
from vnext.canonical import content_hash
from vnext.table_task_contracts import table_task_execution_plan,resolve_table_task_contract,TableTaskContractError
from vnext.requirements import load_requirement_snapshot
ROOT=Path(__file__).resolve().parents[2]

def saved_requirement():
    # Read the frozen prompt rule; R5 code does not reopen its old execution grant.
    return load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v8')

class AnnualGroupPromptTest(unittest.TestCase):
    def test_prompt_changes_only_instruction_and_its_task_identities(self):
        req=saved_requirement();task_id=req['continuity_policy']['task_contract_id']
        old=table_task_execution_plan(repo_root=ROOT,task_contract_id=task_id)
        new=table_task_execution_plan(repo_root=ROOT,task_contract_id=task_id,requirement=req)
        a,b=old['runtime_task_contract'],new['runtime_task_contract']
        self.assertEqual({'system_prompt','system_prompt_hash','task_spec_semantic_hash'},
                         {k for k in a if a[k]!=b[k]})
        rule=json.loads((ROOT/'config/annual_continuity_request.json').read_text())
        self.assertEqual(a['system_prompt']+'\n\n'+rule['instruction'],b['system_prompt'])
        self.assertEqual(content_hash(value=b['system_prompt']),b['system_prompt_hash'])
        self.assertEqual(b,reader_input.build_reader_task_contract(repo_root=ROOT,task_contract_id=task_id,requirement=req))
        self.assertEqual({'system_prompt_hash','task_spec_semantic_hash'},
                         {k for k in old['run_binding'] if old['run_binding'][k]!=new['run_binding'][k]})
        for forbidden in ('Marriott','FY2024','FY2025','69.7','69.8','table_000011','row_index','column_index'):
            self.assertNotIn(forbidden,rule['instruction'])
        for needed in ('header=false','nearest preceding','same row-label column','below the numeric cell','even when their numeric values are equal'):
            self.assertIn(needed,rule['instruction'])

    def test_no_requirement_and_other_task_retain_original_prompt(self):
        req=saved_requirement()
        before=resolve_table_task_contract(repo_root=ROOT,task_contract_id='lodging_revpar_table_v2')
        after=resolve_table_task_contract(repo_root=ROOT,task_contract_id='lodging_revpar_table_v2',requirement=req)
        self.assertEqual(before,after)
        bad=copy.deepcopy(req);bad['execution_authority']['files'].pop('config/annual_continuity_request.json')
        with self.assertRaisesRegex(TableTaskContractError,'Requirement differs'):
            resolve_table_task_contract(repo_root=ROOT,task_contract_id=req['continuity_policy']['task_contract_id'],requirement=bad)

    def test_prompt_file_tamper_is_rejected_without_rewriting_repository(self):
        req=saved_requirement();real=ROOT/'config/annual_continuity_request.json';original=Path.read_bytes
        # Only filesystem input is injected. The actual resolver and rule SHA
        # checks still execute; no validator result is replaced.
        def changed(path):return original(path)+b' ' if path==real else original(path)
        with patch.object(Path,'read_bytes',changed):
            with self.assertRaisesRegex(TableTaskContractError,'rule bytes differ'):
                resolve_table_task_contract(repo_root=ROOT,task_contract_id=req['continuity_policy']['task_contract_id'],requirement=req)

    def test_stage_three_counts_two_closed_attempts_before_new_slots(self):
        stage={'schema_version':3,'maximum_provider_paid_sec_calls':[2,2,0],
            'normal_provider_calls':2,'conditional_repair_calls':0,
            'update_period_ends':['2024-12-31','2025-12-31'],
            'previous_stage':{'counts':{'provider':1,'paid':1},'cumulative_counts':{'provider':2,'paid':2}},
            'cumulative_provider_paid_sec_limit':[4,4,0]}
        self.assertEqual(0,flow._stage_limits(stage)['sec'])
        plan=lambda year:{'selection':{'filing':{'period_end':year}}}
        flow._validate_next_input(stage,plan('2024-12-31'),{'provider_reserved':0,'provider':0,'paid':0})
        flow._validate_next_input(stage,plan('2025-12-31'),{'provider_reserved':1,'provider':1,'paid':1})
        with self.assertRaisesRegex(ValueError,'NORMAL_BUDGET_EXHAUSTED'):
            flow._validate_next_input(stage,plan('2025-12-31'),{'provider_reserved':2,'provider':2,'paid':2})
        changed=copy.deepcopy(stage);changed['cumulative_provider_paid_sec_limit']=[3,3,0]
        with self.assertRaisesRegex(ValueError,'CUMULATIVE_BUDGET_EXCEEDED'):
            flow._validate_next_input(changed,plan('2025-12-31'),{'provider_reserved':1,'provider':1,'paid':1})

if __name__=='__main__':unittest.main()
