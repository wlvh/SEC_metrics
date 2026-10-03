from copy import deepcopy
import json
from pathlib import Path
from postprocess import inspect, HERE, OLD
source=json.loads((OLD/'source.json').read_text())
raw=(HERE/'independent-input/response-revised.log').read_bytes();answer=json.loads(raw)
checks=[{'case':'real_revised_budget_rejected','passed':inspect(raw,source)['status']=='OUTPUT_REFERENCE_LIMIT_REJECTED'},
        {'case':'distinct_B454_assertions_share_source_and_survive','passed':len(inspect(raw,source)['resolved_proposals'])==39}]

def bad(name,change):
    x=deepcopy(answer);change(x)
    try:inspect(json.dumps(x,ensure_ascii=False,separators=(',',':')).encode(),source)
    except ValueError:checks.append({'case':name,'passed':True})
    else:raise AssertionError('Accepted '+name)

bad('boolean_unit_reference',lambda x:x['relevant'][0]['evidence'][0].__setitem__('unit_index',False))
bad('wrong_reference_kind',lambda x:x['relevant'][0]['evidence'][0].__setitem__('kind','F'))
bad('hallucinated_quote',lambda x:x['relevant'][0]['evidence'][0].__setitem__('quote','not a supplied quotation'))
bad('required_anchor_missing',lambda x:x['required_assessments'].pop())
bad('required_source_mismatched_link',lambda x:x['required_assessments'][2].__setitem__('relevant_indexes',[35]))
bad('identical_proposal_duplicate',lambda x:x['relevant'].append(deepcopy(x['relevant'][0])))
assert all(x['passed'] for x in checks)
(HERE/'postprocess-checks.json').write_text(json.dumps({'checks':checks,'source_or_raw_response_modified':False,'semantic_credit':False},indent=2)+'\n')
print(json.dumps(checks))
