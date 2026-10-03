"""Reuse actual pending assessments; add source-linked PENDING review only."""
from pathlib import Path
import json,hashlib,sys,time,socket
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'scripts'))
from vnext.c02_model_review_view import build_development_review_view
HERE=Path(__file__).parent
known=json.loads((ROOT/'docs/evidence/issue28_continuous/c02-model-native-mapping-20261003/result.json').read_text())
OUTPUT=Path('/private/tmp/issue28-c02-source-linked-review-20261003-full');OUTPUT.mkdir(exist_ok=False)
summary={'tested_base':'dee04f5fe118eef823f1079caa3bc213742ed991','new_uncommitted_module':True,'samples':[],'new_calls':[0,0,0]}
for case in known['samples']:
 parent=Path(case['folder']);before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in parent.rglob('*') if p.is_file()}
 start=time.monotonic()
 with patch.object(socket.socket,'connect',side_effect=RuntimeError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=RuntimeError('NO_DNS')):
  out=build_development_review_view(parent_directory=parent,data_root=known['data_root'],company_id=case['company_id'],expected_candidate_hash=case['candidate_hash'],expected_review_unit_hash=case['review_unit_hash'])
 folder=OUTPUT/case['company_id'];folder.mkdir()
 (folder/'context.json').write_bytes(out['review_context_bytes']);(folder/'review.md').write_bytes(out['rendered_review_bytes'])
 meta={k:out[k] for k in ('view_hash','identity','review_unit','native_result_or_run_created','provider_credit','new_business_calls')}
 (folder/'view.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
 refs=out['identity']['source_context']['citations'];missing=[c['block_index'] for c in refs if not c['selected_excerpt_roles']]
 after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in parent.rglob('*') if p.is_file()}
 assert before==after and out['review_unit']['status']=='PENDING' and not out['review_unit']['system_approval_eligible']
 summary['samples'].append({'company_id':case['company_id'],'parent':str(parent),'data_root':known['data_root'],'output':str(folder),'expected_candidate_hash':case['candidate_hash'],'expected_parent_unit_hash':case['review_unit_hash'],'new_view_hash':out['view_hash'],'new_unit_hash':out['review_unit']['review_unit_hash'],'seconds':round(time.monotonic()-start,3),'parent_bytes_unchanged':True,'citations':len(refs),'uncertainty_only_blocks':missing,'entry_count':len(out['identity']['source_context']['entries']),'current_system_approval':False})
 print(json.dumps(summary['samples'][-1]),flush=True)
(HERE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
