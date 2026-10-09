"""Fixed peer v3 diagnosis only; no ordinary selector or runtime is changed."""
import hashlib,json,subprocess,sys,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
HERE=Path(__file__).resolve().parent
PEER='60c6b4d6a2cbe7a7df69fc839600629c0785701c'
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.text_business_candidates import _LEGAL
module_path='scripts/vnext/d02_item_8_category_mentions.py'
terms_path='catalog/r6/D02_item_8_category_mention_v3.json'
code=subprocess.check_output(['git','show',PEER+':'+module_path],cwd=ROOT)
terms=subprocess.check_output(['git','show',PEER+':'+terms_path],cwd=ROOT)
with tempfile.TemporaryDirectory(prefix='issue28-peer-d02-v3-') as temp:
    local=Path(temp)/'terms.json';local.write_bytes(terms)
    source=code.decode().replace('_TERMS_PATH = Path(__file__).resolve().parents[2] / "catalog/r6/D02_item_8_category_mention_v3.json"', '_TERMS_PATH = Path('+repr(str(local))+')')
    assert source!=code.decode()
    m=types.ModuleType('vnext._peer_d02_diagnostic');m.__file__=str(Path(temp)/'peer.py')
    exec(compile(source,str(m.__file__),'exec'),m.__dict__)
    cases=[('reported_P2','During 2025, our company faced litigation, regulatory proceedings and fines.'),
           ('known_named_subject_limit','Kestrel defended regulatory proceedings, litigation and fines.'),
           ('known_open_verb_limit','In 2025, litigation, fines and penalties increased.'),
           ('adviser_category_control','We engage outside counsel to advise us on finance, regulatory, litigation and other matters.')]
    rows=[{'case':label,'text':text,'actual':m.classify(text=text,keyword=_LEGAL)} for label,text in cases]
    assert rows[0]['actual']['left_out'] is False
    assert rows[1]['actual']['left_out'] is True
    assert rows[2]['actual']['left_out'] is True
    assert rows[3]['actual']['left_out'] is True
body={'record_type':'ISSUE28_PEER_D02_V3_BOUNDED_DIAGNOSIS','peer_sha':PEER,
      'module_git_blob':subprocess.check_output(['git','rev-parse',PEER+':'+module_path],cwd=ROOT,text=True).strip(),
      'module_sha256':hashlib.sha256(code).hexdigest(),'terms_sha256':hashlib.sha256(terms).hexdigest(),
      'rows':rows,'material_type':'FOUR_SYNTHETIC_SENTENCES; NO_RESULT_IMPACT_INFERRED',
      'reported_P2_closed_at_function_only':True,'known_remaining_exclusion_limits_reproduced':True,
      'own_v2_runtime_gate':'REMAINS_SUSPENDED','v3_code_received_into_runtime':False,
      'new_real_calls':[0,0,0],'whole_result_credit':False}
(HERE/'peer-v3-known-limits.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'peer_sha':PEER,'cases':[{ 'case':r['case'],'left_out':r['actual']['left_out']} for r in rows], 'runtime_received':False}))
