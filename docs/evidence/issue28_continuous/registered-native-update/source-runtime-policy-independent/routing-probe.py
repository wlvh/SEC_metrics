import vnext
vnext.__path__.insert(0,'/tmp/sec_metrics_issue28_continuous/native-source-runtime-policy/after/scripts/vnext')
from vnext import r6_semantic_source as d,capacity_semantic_source as c,normal_annual_input_v2 as a
from pathlib import Path
from unittest.mock import patch
import tempfile,json,hashlib
rows=[]
with tempfile.TemporaryDirectory() as tmp:
 source=Path(tmp)
 for module,fn,downstream,metric in [(d,d.prepare_d04_semantic_source,'prepare_ordinary_going_concern_source','D04'),(c,c.prepare_capacity_semantic_source,'prepare_d04_semantic_source','B13'),(a,a.prepare_saved_annual_input,'prepare_original_input','ANNUAL')]:
  for explicit in (False,True):
   with patch.object(module,downstream,side_effect=RuntimeError('RAW_SOURCE_CALL_REACHED')) as actual:
    try:fn(repo_root=source,company_id='enphase_energy',ordinary_registered=explicit)
    except Exception as error:
     if explicit:
      assert str(error)=='RAW_SOURCE_CALL_REACHED',(metric,str(error))
      assert actual.call_args.kwargs['repo_root']==source
     else:
      assert 'RAW_SOURCE_CALL_REACHED'!=str(error)
      actual.assert_not_called()
     rows.append({'metric':metric,'explicit_ordinary':explicit,'error':str(error),'original_source_root_preserved':explicit})
  bad=source/'bad-runtime';(bad/module.POLICY_PATH).parent.mkdir(parents=True,exist_ok=True);(bad/module.POLICY_PATH).write_text('{}')
  with patch.object(module,'ROOT',bad),patch.object(module,downstream) as actual:
   try:fn(repo_root=source,company_id='enphase_energy',ordinary_registered=True)
   except Exception as error:rows.append({'metric':metric,'invalid_runtime_rejected':True,'error':str(error)});actual.assert_not_called()
   else:raise AssertionError('invalid runtime accepted')
out={'scope':'real policy path/bytes checks; downstream raw-source work deliberately stopped, not full factory or Run acceptance','checks':rows,'patch_sha256':hashlib.sha256(Path('/tmp/sec_metrics_issue28_continuous/native-source-runtime-policy.patch').read_bytes()).hexdigest()}
Path('docs/evidence/issue28_continuous/registered-native-update/source-runtime-policy-independent/routing-probe.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
