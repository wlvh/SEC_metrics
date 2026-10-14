"""Small constructed D04 state; real configuration/controller, no financial credit."""
from contextlib import ExitStack
import argparse
import json
from pathlib import Path
import socket
import tempfile
from time import perf_counter
from unittest.mock import patch

from vnext import ordinary_current_update as update
from vnext.historical_d04_case import PROCESSING_FILES
from tests.vnext.processing_dependency_checks import processing_calls
from tests.vnext.test_saved_d04_replay import SavedD04ReplayTest

parser=argparse.ArgumentParser()
parser.add_argument('--receipt',required=True,type=Path)
options=parser.parse_args()
if options.receipt.exists():
    raise SystemExit('Receipt already exists; use a new output path')
root=update.ROOT
report={'record_type':'CONSTRUCTED_HISTORY_D04_DEPENDENCY_REPRODUCTION',
    'verification_scope':'NO_FINANCIAL_ORIGINAL_OR_MODEL_RESULT_ACCEPTANCE',
    'new_calls':[0,0,0],'cases':[]}
start=perf_counter()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
    with processing_calls(root) as observed:
        assessment=SavedD04ReplayTest().replay()
    report['actual_small_saved_replay_modules']=sorted(observed)
    report['replay_calls_current_producer']='scripts/vnext/current_d04_result.py' in observed
    report['replay_calls_current_comparator']='scripts/vnext/capacity_update_input.py' in observed
    for relative in ('scripts/vnext/current_d04_result.py','scripts/vnext/capacity_update_input.py'):
        with tempfile.TemporaryDirectory() as folder,ExitStack() as stack:
            state=Path(folder)/'state';records={};calls=[]
            def factory(**kwargs):
                calls.append(kwargs)
                return {'target_period':{'fiscal_year':2024}}
            def save(**kwargs):
                path=kwargs['output_root'];path.mkdir(parents=True)
                value={'manifest':{'company_id':'marriott_international','metric_id':'D04','source_proofs':[]},
                    'result':{'company_id':'marriott_international','metric_id':'D04',
                        'publication':'WITHHELD','period_end':'2024-12-31',
                        'reason_code':'CONSTRUCTED_CONTROL_ONLY',
                        'result_id':'constructed-history-d04-'+str(len(calls))}}
                records[str(path)]=value
                return value
            stack.enter_context(patch.object(update,'_source_census',return_value=[]))
            stack.enter_context(patch.object(update,'_current_sources',return_value=[]))
            stack.enter_context(patch.object(update,'save_calculated_case',side_effect=save))
            stack.enter_context(patch.object(update,'read_saved_result',side_effect=lambda **kw:records[str(kw['output_root'])]))
            args=dict(state_root=state,source_root=root,company_id='marriott_international',
                metric_id='D04',fiscal_year=2024,case_factory=factory,processing_files=PROCESSING_FILES)
            before=update._configuration(root,'marriott_international','D04',supplied_case=True)
            current_default=update._configuration(root,'marriott_international','D04')
            first=update.run_once(**args)
            original_record_path=Path(next(iter(records)))
            repeated=update.run_once(**args)
            assert len(calls)==1 and not repeated['calculation_performed']
            original=update.sha256_file
            with patch.object(update,'sha256_file',side_effect=lambda *,path:
                    'CONSTRUCTED_CURRENT_ONLY_CHANGE' if path==root/relative else original(path=path)):
                changed_config=update._configuration(root,'marriott_international','D04',supplied_case=True)
                changed_default=update._configuration(root,'marriott_international','D04')
                changed=update.run_once(**args)
                again=update.run_once(**args)
            report['cases'].append({'changed_unused_current_module':relative,
                'included_in_public_configuration':relative in before['processing_files'],
                'included_in_historical_declaration':relative in PROCESSING_FILES,
                'public_configuration_changed':not update._same_processing_configuration(before,changed_config),
                'current_default_configuration_changed':not update._same_processing_configuration(current_default,changed_default),
                'initial_status':first['status'],'same_input_repeat_status':repeated['status'],
                'changed_status':changed['status'],'changed_calculation_performed':changed['calculation_performed'],
                'factory_calls':len(calls),'same_changed_input_repeat_status':again['status'],
                'old_result_retained':original_record_path.is_dir()})
report['seconds']=perf_counter()-start
output=options.receipt
output.parent.mkdir(parents=True,exist_ok=True)
output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='actual_small_saved_replay_modules'},indent=2))
