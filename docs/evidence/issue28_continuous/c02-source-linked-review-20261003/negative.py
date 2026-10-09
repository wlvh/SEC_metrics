from pathlib import Path
import json,sys,shutil,socket
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'scripts'))
from vnext.c02_model_review_view import read_development_review_view
from vnext.review import create_system_review_decision,ReviewError
from vnext.requirements import load_requirement_snapshot
HERE=Path(__file__).parent;case=json.loads((HERE/'summary.json').read_text())['samples'][0]
folder=Path('/private/tmp/issue28-c02-source-linked-negative-20261003');shutil.copytree(case['output'],folder)
kw={'directory':folder,'parent_directory':case['parent'],'data_root':case['data_root'],'company_id':case['company_id'],'expected_candidate_hash':case['expected_candidate_hash'],'expected_review_unit_hash':case['expected_parent_unit_hash'],'expected_view_hash':case['new_view_hash']}
original=(folder/'review.md').read_bytes();(folder/'review.md').write_bytes(original+b'\nManufactured approval')
checks=[]
with patch.object(socket.socket,'connect',side_effect=RuntimeError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=RuntimeError('NO_DNS')):
 try:read_development_review_view(**kw)
 except ValueError as e:assert 'SAVED_VIEW_CHANGED' in str(e);checks.append({'case':'real_display_changed','rejected':str(e)})
 else:raise AssertionError('accepted changed display')
 meta=json.loads((folder/'view.json').read_text());meta['view_hash']='sha256:'+'0'*64;(folder/'view.json').write_text(json.dumps(meta))
 try:read_development_review_view(**kw)
 except ValueError as e:assert 'EXPECTED_VIEW_ID_CHANGED' in str(e);checks.append({'case':'self_declared_view_substitution','rejected':str(e)})
 else:raise AssertionError('accepted identity substitution')
 unit=json.loads((Path(case['output'])/'view.json').read_text())['review_unit']
 req=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/ai_first_v3_3_1')
 try:create_system_review_decision(review_unit=unit,required_claims=unit['required_claims'],decided_at_utc='2026-10-03T11:00:00Z',requirement=req)
 except ReviewError as e:checks.append({'case':'system_approval_on_real_pending_view','rejected':str(e)})
 else:raise AssertionError('Created SYSTEM decision')
(HERE/'negative-summary.json').write_text(json.dumps(checks,indent=2)+'\n');print(json.dumps(checks))
