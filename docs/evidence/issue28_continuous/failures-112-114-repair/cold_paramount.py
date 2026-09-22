from pathlib import Path
import sys,json,time
base=Path('/tmp/issue28_paramount_lossless_recorded_v3');sys.path.insert(0,str(base/'data'));sys.path.insert(0,str(base/'data/scripts'));started=time.monotonic()
def audit(event,args):
 if event.startswith('socket.') or event in {'subprocess.Popen','os.system'}:raise AssertionError('OFFLINE_COLD_FORBIDDEN:'+event)
sys.addaudithook(audit)
from vnext.ordinary_projection import render_ordinary_run
from vnext.capacity_assessment_input import EXPORT_PATHS
from vnext import run_store
assert Path(run_store.__file__).is_relative_to(base/'data')
export=json.loads((base/'data'/EXPORT_PATHS['D04']).read_text());assert '\u037e' in json.dumps(export,ensure_ascii=False)
expected=json.loads((base/'summary.json').read_text());rendered=render_ordinary_run(data_root=base/'data',run_dir=base/'run')
assert rendered['receipt']['result_id']==expected['result_id'] and rendered['receipt']['semantic_assessment_mode']=='RECORDED_TEST_ONLY'
for name,raw in rendered['files'].items():assert raw==(base/'rows'/name).read_bytes()
result={'status':'PASS_NEW_PARAMOUNT_INSTALLED_PY39_COLD_READ','result_id':expected['result_id'],'unicode_preserved_in_registered_export':True,'public_rows_identical':True,'new_calls':[0,0,0],'seconds':round(time.monotonic()-started,3)}
Path(__file__).with_name('paramount-cold-summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
