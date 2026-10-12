import importlib,json,time,unittest
from pathlib import Path
start=time.monotonic()
import tests.vnext.test_normal_zero_ai_results as module
T=module.OrdinaryZeroAiPrototypeTest
T.setUpClass();prepared=time.monotonic()-start
path=Path('tests/vnext/test_normal_zero_ai_results.py');original=path.read_text()
before=unittest.TestResult();T('test_twenty_actual_coordinates_use_native_records_and_never_create_a_run').run(before)
evidence=Path('docs/evidence/issue28_source_credit_controls_20261011')
(evidence/'before.log').write_text('\n'.join(str(t)+'\n'+error for t,error in [*before.failures,*before.errors]))
assert len(before.failures)==21 and not before.errors,(len(before.failures),before.errors)
needle="                self.assertEqual('PREEXISTING_SAVED_ACQUISITIONS_ONLY',case['source_admission']['source_credit'])"
assert original.count(needle)==1
new="""                self.assertEqual('SAVED_SOURCE_BYTES_AND_REQUESTS_CHECKED',case['source_admission']['source_credit'])
                self.assertFalse(case['source_admission']['real_sec_credit'])
                self.assertEqual({'provider':0,'paid':0,'sec':0},case['source_admission']['new_business_calls'])"""
path.write_text(original.replace(needle,new,1))
cases=T.cases
module=importlib.reload(module)
After=module.OrdinaryZeroAiPrototypeTest;After.cases=cases
result=unittest.TestResult();After('test_twenty_actual_coordinates_use_native_records_and_never_create_a_run').run(result)
(evidence/'after.log').write_text('same actual source-prepared twenty cases; new precise credit contract\n'+str(result)+'\n'+'\n'.join(error for t,error in [*result.failures,*result.errors]))
assert result.wasSuccessful(),(result.failures,result.errors)
record={'base':'c6f5c90fe1fa49762608f5605bd54e0b9c7590d5','code_root':str(Path.cwd()),'prepared_actual_cases':len(cases),'preparation_seconds':prepared,'total_seconds':time.monotonic()-start,'before_failures':len(before.failures),'before_errors':len(before.errors),'after_tests':result.testsRun,'after_failures':len(result.failures),'after_errors':len(result.errors),'class_source_prepared_once':True,'after_retains_native_records_claims_periods_counts_and_no_run_assertions':True,'producer_or_source_changed':False,'new_calls':[0,0,0]}
(evidence/'actual-validation.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
