"""Actual continuity terminals and fully re-signed counterexamples."""
from pathlib import Path
import json,shutil,sys,socket,os,unittest
from unittest.mock import patch
from vnext import run_store
from vnext.zero_ai_r2 import _manual_result_trace
from vnext.observations import structured_observation
from vnext.calculator import calculate_observation_metric
from vnext.specs import compile_spec_file
from vnext.canonical import content_hash
from vnext.records import validate_record

@unittest.skipUnless(os.environ.get('CONTINUITY_NATIVE_BATCH'),'Requires completed six-coordinate native batch')
class ContinuityRunMaterialTest(unittest.TestCase):
    def test_source_rebuilt_continuity_terminals_reject_other_reasons_and_numbers(self):
        base=Path(os.environ['CONTINUITY_NATIVE_BATCH']).resolve();out=Path(os.environ['CONTINUITY_ATTACK_ROOT']).resolve();assert not out.exists();out.mkdir()
        company='paramount_skydance_paramount_global';data=base/'data'/company
        summary=json.loads((base/'summary.json').read_text());rows=summary['coordinates'];assert len(rows)==6
        for row in rows:
         assert row['status']=='OPEN_CANDIDATE' and row['public_row_status']=='CANDIDATE_ROW_PREPARED'
         if row['metric_id'] in {'B02','B04','B05','B07'}:
          assert row['result']['quality']=='NOT_MEANINGFUL' and row['result']['value'] is None
         else:assert row['result']['quality']=='EXACT'
        run=base/'runs'/company/'B02';original=[json.loads(s) for s in (run/'records.jsonl').read_text().splitlines()]
        result=next(r for r in original if r['record_type']=='METRIC_RESULT');trace=next(r for r in original if r['record_type']=='EXECUTION_TRACE')
        spec=compile_spec_file(path=data/'catalog/ordinary_zero_ai/B02.md',dependency_specs={})
        target={k:trace['calculation_target'][k] for k in ['company_id','period_start','period_end','accession','entity','scope','scope_key']}
        source=next(r for r in original if r['record_type']=='SOURCE_REFERENCE' and r['source_role']=='target_primary')
        checks=[]
        with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')):
         for name in ['unrelated_empty_input_reason','fabricated_numeric_result']:
          dest=out/name;shutil.copytree(run,dest)
          if name=='unrelated_empty_input_reason':
           new_result,new_trace=_manual_result_trace(metric_id='B02',company_id=company,period_start=result['period_start'],
            period_end=result['period_end'],scope=target['scope'],spec_closure_hash=spec['spec_closure_hash'],
            applicability='APPLICABLE',quality='NOT_MEANINGFUL',reason_code='NON_POSITIVE_EQUITY',input_observation_ids=[],
            steps=[{'event':'NON_POSITIVE_EQUITY'}],accession=target['accession'],entity=target['entity'],unit=None)
           extra=[]
          else:
           observation=structured_observation(metric_id='B02',semantic_role='metric_result',company_id=company,
            period_start=result['period_start'],period_end=result['period_end'],scope=target['scope'],value='1',unit='ratio',quality='EXACT',
            source_binding={**{k:source[k] for k in ['accession','document_name','raw_asset_id','source_reference_id','source_role']},'entity':target['entity']})
           new_result,new_trace=calculate_observation_metric(compiled_spec=spec,target={k:target[k] for k in ['company_id','period_start','period_end','scope','scope_key']},company_traits=['non_financial'],observation=observation)
           extra=[observation]
          changed=[r for r in original if r['record_type'] not in {'METRIC_RESULT','EXECUTION_TRACE'}]+extra+[new_trace,new_result]
          for record in changed:validate_record(record=record)
          (dest/'records.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in changed))
          try:run_store._mechanically_replay_open_run(run_dir=dest,repo_root=data,require_complete_results=True)
          except ValueError as error:
           assert 'COMPLETE_COMPUTATION_GRAPH_CHANGED' in str(error),str(error)
           checks.append({'case':name,'result':'REJECTED','reason':str(error),'all_records_structurally_valid':True})
          else:raise AssertionError('Invalid terminal accepted')
         (out/'summary.json').write_text(json.dumps({'status':'PASS','six_native_rows_verified':True,'attacks':checks,'calls':[0,0,0]},indent=2)+'\n')
        print(json.dumps(checks))

if __name__=='__main__':unittest.main()
