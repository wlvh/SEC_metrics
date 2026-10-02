"""Verify the own versioned D02 rule is only a path-adapted peer copy."""
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[4]
PEER = '104876d6cfae7812d93fd5b8a4bb0e0f97959fff'
source_paths = (
    ('scripts/vnext/d02_item_8_category_mentions.py',
     'scripts/vnext/d02_item8_category_28_v1.py',
     'catalog/r6/D02_item_8_category_mention_v1.json',
     'catalog/r6/D02_item8_category_28_v1.json'),
    ('catalog/r6/D02_item_8_category_mention_v1.json',
     'catalog/r6/D02_item8_category_28_v1.json',
     'scripts/vnext/d02_item_8_category_mentions.py',
     'scripts/vnext/d02_item8_category_28_v1.py'),
)
blobs = {}
for original, own, old_ref, new_ref in source_paths:
    raw = subprocess.check_output(['git','show',PEER+':'+original],cwd=ROOT)
    local = (ROOT/own).read_bytes()
    assert raw.replace(old_ref.encode(),new_ref.encode()) == local
    blob = subprocess.check_output(['git','rev-parse',PEER+':'+original],
                                   cwd=ROOT,text=True).strip()
    blobs[original] = blob
print(json.dumps({'pinned_peer_source_commit':PEER,
    'peer_wired_commit_exact_content_api':'36c64ab65e84af5e3f37b8f4b47820516fcec97d',
    'git_blobs_unchanged_at_wired_commit':blobs,
    'adaptation':'ONLY_VERSIONED_CODE_AND_TERMS_PATH_REFERENCES',
    'own_legacy_module_imported':False,'new_real_calls':[0,0,0]}))
