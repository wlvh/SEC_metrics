"""Restore the reviewed #28 mixed acquisition, preserving every index binding."""
import hashlib
import json
from pathlib import Path
import tarfile
import sys

code=Path('/workspace/work/sec-company-compute')
packet=code/'docs/evidence/issue28_continuous/ordinary-document-identity'
out=Path('/workspace/work/ordinary-mixed-restored-complete')
out.mkdir()
index=json.loads((packet/'material-index.json').read_text())
def digest(raw): return {'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
archive=packet/index['archive']
assert digest(archive.read_bytes()) == index['archive_binding']
fallback=code/'docs/evidence/issue28_continuous/ordinary-continuity-policy'
other=json.loads((fallback/'archive-members.json').read_text())
fallback_archive=fallback/'native-continuity-material.tar.gz'
assert hashlib.sha256(fallback_archive.read_bytes()).hexdigest()==other['archive_sha256']
repairs=[]
with tarfile.open(archive) as primary, tarfile.open(fallback_archive) as frozen:
    for name,binding in index['files'].items():
        if not (name.startswith('actual-ledger/') or name=='live-c04-logical-native-final/data/salesforce/config/ordinary_source_checkpoint.json'):continue
        expected={k:binding[k] for k in ('sha256','size')}
        if 'archive_member' in binding:
            raw=primary.extractfile(binding['archive_member']).read()
        else:
            raw=(code/binding['repository_path']).read_bytes()
            if digest(raw)!=expected:
                matches=[p for p,b in other['members'].items() if b==expected]
                assert matches, 'NO_ORIGINAL_BYTES:'+name
                raw=frozen.extractfile(matches[0]).read()
                repairs.append({'path':name,'original_archive':str(fallback_archive),'member':matches[0],**expected})
        assert digest(raw)==expected,name
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
checkpoint=out/'live-c04-logical-native-final/data/salesforce/config/ordinary_source_checkpoint.json'
sys.path[:0]=[str(code/'scripts')]
from vnext.continuous_sec_acquisition import validate_acquisition_checkpoint
from vnext.normal_source_authority import MANIFEST_PATH
cp=json.loads(checkpoint.read_text())
raw,old,admitted=validate_acquisition_checkpoint(out/'actual-ledger/source-inputs',cp,json.loads((code/MANIFEST_PATH).read_text()))
summary={'status':'FULL_MIXED_CHECKPOINT_VALIDATED','checkpoint_id':cp['checkpoint_id'],'ledger_sha256':cp['ledger_sha256'],'captures':len(cp['captures']),'companies':sorted({r['receipt']['company_id'] for r in cp['captures']}),'real_sec_credit':cp['real_sec_credit'],'repairs':repairs,'new_calls':[0,0,0]}
(out/'restore-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary),flush=True)
