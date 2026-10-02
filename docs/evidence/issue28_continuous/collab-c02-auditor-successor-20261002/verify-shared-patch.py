"""Verify #28 consumes only the fixed shared auditor-scope repair."""
import hashlib
import json
from pathlib import Path
import subprocess


ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
OWN_BASE='0bc24734736bb1e6cb34fbcf7ab9fece6951764e'
PEER_PATCH='72858e3c023bed0c90f3217f381aec5725e15fbc'
PEER_HEAD='54eb39d47718dea25812ea05ceb5a085078ff611'


def show(ref,path):
    return subprocess.check_output(['git','show',ref+':'+path],cwd=ROOT,text=True)


def expression(source):
    start=source.index('_NOT_DIRECTOR_INDEPENDENCE = re.compile(')
    return source[start:source.index('# Words that make a sentence',start)]


old=show(OWN_BASE,'scripts/vnext/historical_board_composition_v2.py')
peer_old=show(PEER_PATCH+'^','scripts/vnext/historical_board_composition_v3.py')
peer_new=show(PEER_PATCH,'scripts/vnext/historical_board_composition_v3.py')
own=(ROOT/'scripts/vnext/c02_board_composition_28_v3.py').read_text()
assert expression(old)==expression(peer_old)
assert expression(own)==expression(peer_new)
old_doc='''    Why there are two files: ``historical_board_composition.py`` keeps the
    bytes #28's issue_28_v13 records for its ordinary C02 route (the reader as
    of 546d10d1). A path one Issue's generation binds is not edited by the
    other, so #47's repairs continue here; #28 takes a later version by copying
    a pinned commit's bytes into the path it owns.
'''
new_doc='''    This explicit #28 version retains its existing period-aware selector and
    applies only the auditor-independence scope correction from #47 commit
    72858e3c. The older selector paths and their installed Runs retain their
    bytes; no historical route or peer runtime is imported.
'''
assert old.replace(expression(old),expression(peer_new)).replace(old_doc,new_doc)==own
result={'peer_read_head':PEER_HEAD,'peer_patch_commit':PEER_PATCH,
    'peer_patch_module_git_blob':subprocess.check_output(['git','rev-parse',
        PEER_PATCH+':scripts/vnext/historical_board_composition_v3.py'],cwd=ROOT,text=True).strip(),
    'own_base_commit':OWN_BASE,'own_base_selector_git_blob':subprocess.check_output([
        'git','rev-parse',OWN_BASE+':scripts/vnext/historical_board_composition_v2.py'],
        cwd=ROOT,text=True).strip(),
    'own_successor_sha256':hashlib.sha256(own.encode()).hexdigest(),
    'only_algorithm_delta':'EXACT_SHARED_NOT_DIRECTOR_INDEPENDENCE_EXPRESSION',
    'other_delta':'DOCSTRING_OWN_VERSIONED_RECEIVING_PATH',
    'peer_runtime_or_history_imported':False,'new_real_calls':[0,0,0]}
(HERE/'shared-patch.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,sort_keys=True))
