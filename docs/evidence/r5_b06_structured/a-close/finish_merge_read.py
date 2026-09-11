from pathlib import Path
import json,sys,hashlib,subprocess
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');B=Path(__file__).parents[1];G=Path('/Users/lyuhongwang/Documents/Codex/2026-09-10/annual-update-continuity/group-ownership');sys.path[:0]=[str(R),str(R/'scripts')]
from vnext import annual_continuity as f
from vnext.canonical import strict_json_file
j=json.loads((B/'a-close/post-merge-command.json').read_text());log=(B/'a-close/post-merge-command.log').read_bytes();assert hashlib.sha256(log).hexdigest()==j['log_sha256'];passed=[s.split()[1] for s in log.decode().splitlines() if s.startswith('READ_PASS ')];assert len(passed)==3
checks=[]
for root in [G.parent/'live',G.parent/'continuation/live',G/'live']:
 binding=strict_json_file(path=root/'stage/stage-binding.json');stage=binding['stage'];closed=strict_json_file(path=root/'budget/closed.json');assert closed['stage_id']==stage['stage_id']
 try:f.validate_stage(stage,execution=True)
 except ValueError as e:
  expected='CONTINUITY_STAGE_CLOSED' if root==G/'live' else 'CONTINUITY_STAGE_REQUIREMENT_CHANGED';assert str(e)==expected
  checks.append({'root':str(root),'rejection':str(e),'closed':closed})
 else:raise AssertionError('Old stage allowed')
 if root!=G/'live':f._previous_stage_proof(binding)
base=json.loads((B/'a-close/baseline.json').read_text());assert hashlib.sha256((R/'outputs/active_publication.json').read_bytes()).hexdigest()==base['active_bytes_sha256'];assert subprocess.check_output(['git','stash','list'],text=True)==base['stash'];parents=subprocess.check_output(['git','show','-s','--format=%P','HEAD'],text=True).split();assert parents[1]=='437d438dbfbca65ff34be2dab453ac77c425a97f'
(B/'a-close/post-merge-read.json').write_text(json.dumps({'status':'PASS_MERGE_COMPATIBILITY_READ_ONLY','head':f.code_identity(),'parents':parents,'fresh_native_views_read':passed,'first_command':j,'first_command_limit':'All three verified views/native sources read before overly narrow test assertion on historical stage rejection. Old frozen Requirement differs from current, so correct current execution rejection is REQUIREMENT_CHANGED; no product failure or retry.','closed_stages_verified':checks,'actual_active_unchanged':True,'business_calls':[0,0,0]},indent=2)+'\n');print('PASS completion; old failures preserved and old execution rejected by exact content identity')
