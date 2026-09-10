"""Bind the approved label repair to a new unactivated five-file revision.

No historical snapshot, source attempt, activation or live plan is rewritten.
"""
from copy import deepcopy
from pathlib import Path
import json
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from vnext.canonical import content_hash, sha256_file, atomic_write_json, strict_json_file
from vnext.requirements import load_requirement_snapshot
from vnext import requirement_profile_v1 as v1, requirement_profile_v4 as v4
from vnext.r4_label_policy import approved_label_choice, DECISION_ID


def binding(path):
    return {"sha256":sha256_file(path=path),"size":path.stat().st_size}


def write_revision(repo_root=REPO_ROOT):
    root = repo_root.resolve()
    target = root / "requirements/issue_28_v3"
    if not (target / "CONTRACT.md").is_file() or target.is_symlink():
        raise ValueError("The explicit new R4 Contract is required")
    if (root / "docs/evidence/issue_28_v3_transition_activation.json").exists():
        raise ValueError("An activated revision cannot be regenerated")
    parent_dir = root / "requirements/issue_28_v2"
    parent = load_requirement_snapshot(snapshot_dir=parent_dir)
    baseline = deepcopy(parent["baseline"])
    capture = strict_json_file(path=root / v4.POLICY_PATH)
    source = {"source_id":"OWNER_R4_LABEL_POLICY","kind":"OWNER_TASK_POLICY",
        "source_url":"codex-task:" + capture["task_id"],
        "source_sha256":v1.sha256_bytes(content=capture["approval_text"].encode()),
        "author":capture["author"],"published_at_utc":capture["observed_at_utc"],
        "text":capture["approval_text"],"evidence_path":v4.POLICY_PATH}
    files = {p.name:binding(p) for p in sorted(parent_dir.iterdir())}
    tree = subprocess.check_output(['git','rev-parse','HEAD:requirements/issue_28_v2'],cwd=root,text=True).strip()
    baseline.update(requirement_id="issue_28_v3",contract_revision="ISSUE_28_V3",
        requirement_generation="PROFILE_DRIVEN_V4",created_at_utc=capture["observed_at_utc"],
        supersedes_requirement={"requirement_id":"issue_28_v2","requirement_closure_hash":parent["requirement_closure_hash"]},
        parent={"requirement_id":"issue_28_v2","requirement_closure_hash":parent["requirement_closure_hash"],
            "hashes":parent["hashes"],"snapshot_files":files,"snapshot_binding_hash":content_hash(value=files),
            "snapshot_git_tree":tree},policy_evidence=baseline["policy_evidence"] + [source])
    engine = root / 'scripts/vnext/requirement_profile_v4.py'
    baseline['validator']={'path':engine.relative_to(root).as_posix(),'semantic_version':'4',
        'sha256':sha256_file(path=engine),'dependencies':{'scripts/vnext/'+name:binding(root/'scripts/vnext'/name)
        for name in ('requirement_profile_v1.py','requirement_profile_v3.py','canonical.py','r4_label_policy.py')}}
    paths = set(baseline['execution_authority']['files']) | {v4.POLICY_PATH}
    for prefix in ('scripts','tools'):
        paths.update(p.relative_to(root).as_posix() for p in (root/prefix).rglob('*.py'))
    if any((root/p).is_symlink() for p in paths):
        raise ValueError('Execution inputs contain symlinks')
    baseline['execution_authority']['files']={p:binding(root/p) for p in sorted(paths)}
    register = strict_json_file(path=parent_dir/'decision_register.json')
    register.update(requirement_id='issue_28_v3',issue_contract_revision='ISSUE_28_V3')
    register['decisions'].append({'decision_id':DECISION_ID,'status':'APPROVED','choice':approved_label_choice(),
        'approved_by':capture['author'],'approved_at_utc':capture['observed_at_utc'],'supersedes_decision_id':None,
        'evidence':source['source_url'],'policy_provenance':{'source_id':source['source_id'],
            'section':'scope_label_representation','scope':'POLICY_CONTENT_ONLY'}})
    effective,_=v1.resolve_decision_chains(decisions=register['decisions']+register['pending_decisions'])
    profile={'schema_version':1,'record_type':'REQUIREMENT_INVARIANT_PROFILE','requirement_id':'issue_28_v3',
        'profile_semantic_version':'4','invariants':sorted([{'invariant_id':'INV-'+k.removeprefix('S-'),'decision_id':k}
            for k,d in effective.items() if d['status']=='APPROVED'],key=lambda x:x['invariant_id'])}
    transfer = strict_json_file(path=parent_dir/'transfer_manifest.json')
    fragments=[{'decision_id':k,'source_path':path,'source_value_hash':content_hash(value=value),
        'parent_effective_record_hash':v1.decision_record_hash(decision=d),'disposition':'CARRY_FORWARD',
        'successor_decision_id':k,'successor_path':path,'transfer_mode':'EXACT_VALUE',
        'rationale':'Preserve the exact inherited policy; the additive label Decision only selects source representation.'}
        for k,d in sorted(parent['effective_decisions'].items()) if d['status']=='APPROVED'
        for path,value in sorted(v1.choice_fragments(value=d['choice']).items())]
    transfer.update(requirement_id='issue_28_v3',parent_requirement_id='issue_28_v2',
        parent_requirement_closure_hash=parent['requirement_closure_hash'],parent_snapshot_files=files,
        parent_snapshot_binding_hash=content_hash(value=files),fragments=fragments,
        fragment_classification_counts={'CARRY_FORWARD':len(fragments),'SUPERSEDED':0,'HISTORICAL_ONLY':0},
        pending_decision_transfers=[{'decision_id':k,'disposition':'CARRY_FORWARD',
            'parent_record_hash':v1.decision_record_hash(decision=d),'qualification_credit':'NONE'}
            for k,d in parent['effective_decisions'].items() if d['status']!='APPROVED'])
    for name,value in [('decision_register.json',register),('invariant_profile.json',profile),('transfer_manifest.json',transfer)]:
        atomic_write_json(path=target/name,value=value)
    baseline['snapshot_files']={name:binding(target/name) for name in sorted(v1.PROFILE_BOUND_FILES)}
    atomic_write_json(path=target/'baseline_manifest.json',value=baseline)
    result=load_requirement_snapshot(snapshot_dir=target)
    v1.validate_execution_authority(repo_root=root,requirement=result)
    return {'requirement_id':result['requirement_id'],'requirement_closure_hash':result['requirement_closure_hash'],
        'activation_state':result['activation_state'],'execution_files':len(paths),'carried_fragments':len(fragments)}


if __name__ == '__main__':
    print(json.dumps(write_revision(),sort_keys=True))
