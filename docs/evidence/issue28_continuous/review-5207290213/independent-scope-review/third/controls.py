"""Bounded recheck of previously observed conditional and embedding controls."""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from tests.vnext.test_d04_native_assessment import request_for, response_for
from vnext.d04_native_assessment import validate_response, build_acceptance
from vnext.r6_semantic_source import _bytes
from vnext.canonical import content_hash

CASES = [
    ('If financing fails and there is substantial doubt about our ability to continue as a going concern, we sell the asset.', 'CONDITIONAL'),
    ('If financing fails, cash is insufficient and these conditions raise substantial doubt about our ability to continue as a going concern.', 'CONDITIONAL'),
    ('In 2024 management concluded that these conditions now raise substantial doubt about our ability to continue as a going concern.', 'UNRESOLVED'),
    ('If financing fails, cash is insufficient; there is substantial doubt about our ability to continue as a going concern.', 'UNRESOLVED'),
]
rows=[]
for statement, expected in CASES:
    request=request_for(statement)
    results=[]
    for kind,timing in [('DOUBT_DISCLOSED','CURRENT_REPORT'), ('CONDITIONAL_OR_BOILERPLATE','CONDITIONAL')]:
        response=response_for(request,kind,timing)
        try:
            checked=validate_response(request=request, raw_response=_bytes(response))
            observation={'accepted':True,'unresolved':checked['unresolved'],
                         'current_target_findings':checked['current_target_findings']}
        except ValueError as exc:
            observation={'accepted':False,'error':str(exc)}
        if expected=='CONDITIONAL':
            assert observation['accepted']==(timing=='CONDITIONAL')
            if observation['accepted']: assert observation['unresolved']==[]
        else:
            assert observation['accepted'] and observation['unresolved']
            prepared=SimpleNamespace(request_bytes=_bytes(request),source_bytes=b'{}')
            plan={k:content_hash(value=k) for k in ('selected_representation_hash','ai_invocation_plan_id','source_identity_hash','task_contract_hash')}
            try: build_acceptance(prepared=prepared,plan=plan,response_body=_bytes(response))
            except ValueError as exc: observation['native_acceptance_error']=str(exc)
            else: raise AssertionError('unresolved input acquired native acceptance')
        results.append({'kind':kind,'timing':timing,'observation':observation})
    rows.append({'statement':statement,'expected':expected,'results':results})
path=Path('scripts/vnext/d04_native_assessment.py');src=path.read_text()
names={'_assertion_clauses','_assertion_scope','_assessment_time_prefix','source_statement_relations','check_source_classifications'}
hashes={n.name:hashlib.sha256(ast.get_source_segment(src,n).encode()).hexdigest() for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name in names}
print(json.dumps({'status':'PASS','cases':rows,'function_sha256':hashes,'real_calls':[0,0,0],'full_disk_Run_executed':False},ensure_ascii=False,indent=2))
