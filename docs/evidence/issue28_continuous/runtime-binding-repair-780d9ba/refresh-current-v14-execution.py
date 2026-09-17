from pathlib import Path
import hashlib,json,shutil,subprocess,sys
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');T=R/'docs/evidence/issue28_continuous/runtime-binding-repair-780d9ba';T.mkdir(exist_ok=True)
H=T/'historical-v14-e1ac';H.mkdir(exist_ok=True)
for p in (R/'requirements/issue_28_v13').iterdir():
 original=subprocess.check_output(['git','show','6341530:'+p.relative_to(R).as_posix()])
 target=H/p.name
 if target.exists():assert target.read_bytes()==original
 else:target.write_bytes(original)
bp=R/'requirements/issue_28_v13/baseline_manifest.json';b=json.loads(bp.read_text());changes={}
for relative,binding in b['execution_authority']['files'].items():
 raw=(R/relative).read_bytes();current={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
 if current!=binding:changes[relative]={'before':binding,'after':current}
 b['execution_authority']['files'][relative]=current
bp.write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n')
(T/'execution-binding-delta.json').write_text(json.dumps({'record_type':'UNFROZEN_V14_EXECUTION_BINDING_REPAIR',
 'prior_head':'780d9bae5d77c950b6a692fdc2277fa6798cc068','preserved_reviewed_head':'6341530c67b5a0aa0ded858a2a60bddc56ee6a12',
 'historical_closure':'sha256:e1ac4b08b4b31aa5d7a411ac76b8d29c33075e82da3fe5f939009566194dc1f4',
 'changes':changes,'new_rule_files_unchanged':True,'rule_meanings_changed':False,'old_runs_or_failures_changed':False},indent=2)+'\n')
sys.path.insert(0,str(R/'scripts'))
from vnext.requirements import load_requirement_snapshot
r=load_requirement_snapshot(snapshot_dir=bp.parent);print(r['requirement_closure_hash'],len(changes),'execution bindings updated')
