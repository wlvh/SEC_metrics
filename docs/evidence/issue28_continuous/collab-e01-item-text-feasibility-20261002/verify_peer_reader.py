"""Verify #28's versioned E01 item parser copies the fixed peer algorithm."""
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[4]
PEER = '488a61734978adaa57e82ec0654e75a0af284cfb'
PEER_FILE = 'scripts/vnext/historical_event_items.py'
OWN_FILE = 'scripts/vnext/e01_item_text_28_v1.py'
original = subprocess.check_output(['git','show',PEER+':'+PEER_FILE],cwd=ROOT,
                                   text=True)
algorithm = original[original.index('_HEADING = re.compile('):
                     original.index('def _primary_bytes(')]
own = (ROOT/OWN_FILE).read_text()
assert own.endswith(algorithm)
blob = subprocess.check_output(['git','rev-parse',PEER+':'+PEER_FILE],
                               cwd=ROOT,text=True).strip()
print(json.dumps({'peer_commit':PEER,'peer_git_blob':blob,
    'algorithm_from_heading_rules_through_caption_only':'BYTE_IDENTICAL',
    'historical_route_registration_copied':False,
    'real_calls':[0,0,0]}))
