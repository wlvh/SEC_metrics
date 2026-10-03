"""Check the fixed #47 v2 rule and document #28's path-only adaptations."""
import hashlib
import json
from pathlib import Path
import subprocess


ROOT=Path(__file__).resolve().parents[5]
HERE=Path(__file__).resolve().parent
PEER='147957c400c3361ab26ee0b04bbb89b2a692cadd'


def show(path):
    return subprocess.check_output(['git','show',PEER+':'+path],cwd=ROOT)


module_path='scripts/vnext/d02_item_8_category_mentions.py'
terms_path='catalog/r6/D02_item_8_category_mention_v2.json'
peer_module=show(module_path).decode()
own_module=(ROOT/'scripts/vnext/d02_item8_category_28_v2.py').read_text()
assert peer_module.replace(terms_path,'catalog/r6/D02_item8_category_28_v2.json')==own_module
peer_terms=json.loads(show(terms_path))
own_terms=json.loads((ROOT/'catalog/r6/D02_item8_category_28_v2.json').read_text())
expected=dict(peer_terms)
expected['reader']='scripts/vnext/d02_item8_category_28_v2.py'
expected['supersedes']='catalog/r6/D02_item8_category_28_v1.json'
expected['why_this_file']=expected['why_this_file'].replace(
    'issue_47_v1 snapshot','issue_28_v13 development snapshot')
assert expected==own_terms
result={'peer_commit':PEER,
        'peer_module_git_blob':subprocess.check_output(['git','rev-parse',
            PEER+':'+module_path],cwd=ROOT,text=True).strip(),
        'peer_terms_git_blob':subprocess.check_output(['git','rev-parse',
            PEER+':'+terms_path],cwd=ROOT,text=True).strip(),
        'own_module_sha256':hashlib.sha256(own_module.encode()).hexdigest(),
        'adaptations':['two local terms-path references','terms.reader',
            'terms.supersedes','terms.why_this_file snapshot owner'],
        'algorithm_otherwise_byte_identical':True,
        'peer_runtime_imported':False,'new_real_calls':[0,0,0]}
(HERE/'peer-copy.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,sort_keys=True))
