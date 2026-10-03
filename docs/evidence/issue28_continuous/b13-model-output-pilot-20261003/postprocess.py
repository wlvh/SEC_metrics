"""Read development proposals with existing reference lookup; no native credit."""
from pathlib import Path
from copy import deepcopy
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'scripts'))
from vnext.r6_semantic_review import _source_items
from vnext.continuous_request_context import _load_tokenizer
HERE=Path(__file__).parent
OLD=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls/0192')


def inspect(raw,source):
    answer=json.loads(raw)
    need=lambda yes,reason: None if yes else fail(reason)
    need(type(answer) is dict and set(answer)=={'reviewed_unit_indexes','relevant','required_assessments','unresolved'},'SHAPE')
    units=[u for u in source['units'] if u['kind']=='VISIBLE_TEXT']+[u for u in source['units'] if u['kind']=='NATIVE_FACTS'][:2]
    need(type(answer['reviewed_unit_indexes']) is list and all(type(i) is int for i in answer['reviewed_unit_indexes'])
         and sorted(answer['reviewed_unit_indexes'])==list(range(9)),'UNIT_CENSUS')
    need(type(answer['relevant']) is list and len(answer['relevant'])<=64,'ITEM_BOUND')
    policy=json.loads((OLD/'semantic-request.json').read_text())['category_definitions']
    lookup=[_source_items(u) for u in units]; resolved=[]; seen=set()
    for item in answer['relevant']:
        need(type(item) is dict and set(item)=={'kind','subject','time','scope','evidence','quantities','unresolved'},'ITEM_SHAPE')
        identity=json.dumps(item,ensure_ascii=False,sort_keys=True,separators=(',',':'))
        need(identity not in seen,'EXACT_DUPLICATE_PROPOSAL');seen.add(identity)
        need(item['kind'] in policy and all(type(item[k]) is str and item[k].strip() for k in ('subject','time','scope')),'FIELD')
        need(type(item['evidence']) is list and item['evidence'],'EVIDENCE')
        refs=[]
        for ref in item['evidence']:
            need(type(ref) is dict and set(ref)=={'unit_index','kind','source_index','quote'},'REFERENCE_SHAPE')
            i,j=ref['unit_index'],ref['source_index']
            need(type(i) is int and 0<=i<len(units) and type(j) is int,'REFERENCE_INTEGER')
            kind,items=lookup[i]
            need(ref['kind']=={'VISIBLE_BLOCK':'B','NATIVE_FACT':'F'}[kind] and j in items,'REFERENCE_OUTSIDE_UNIT')
            need(type(ref['quote']) is str and ref['quote'].strip() and ref['quote'] in items[j]['text'],'QUOTE_NOT_IN_SOURCE')
            refs.append({**ref,'original_unit_id':units[i]['unit_id'],'original_kind':kind})
        need(type(item['quantities']) is list and type(item['unresolved']) is list,'LIST_FIELD')
        for q in item['quantities']:
            need(type(q) is dict and set(q)=={'role','source_value','unit','period'} and all(type(v) is str and v.strip() for v in q.values()),'QUANTITY_SHAPE')
            need(q['role'] in {'ACTUAL_PRODUCTION','AVAILABLE_CAPACITY','SALES_OR_SHIPMENTS','PRODUCT_CAPABILITY','PLANNED','OTHER'},'QUANTITY_ROLE')
        need(all(type(v) is str for v in item['unresolved']),'UNRESOLVED_SHAPE')
        resolved.append({'proposal':item,'resolved_references':refs})
    need(type(answer['required_assessments']) is list and len(answer['required_assessments'])==5,'REQUIRED_CENSUS')
    anchors=json.loads((OLD.parent/'0190/semantic-request.json').read_text())['required_candidate_assessments']
    positions={u['unit_id']:i for i,u in enumerate(units)}
    seen=[]
    for row in answer['required_assessments']:
        need(type(row) is dict and set(row)=={'anchor_index','kind','relevant_indexes','reason'},'ANCHOR_SHAPE')
        i=row['anchor_index'];need(type(i) is int and 0<=i<5,'ANCHOR_INDEX');seen.append(i)
        need(row['kind'] in policy and type(row['reason']) is str and row['reason'].strip(),'ANCHOR_FIELD')
        need(type(row['relevant_indexes']) is list and len(row['relevant_indexes'])==len(set(row['relevant_indexes'])),'ANCHOR_LINKS')
        for j in row['relevant_indexes']:
            need(type(j) is int and 0<=j<len(resolved),'ANCHOR_LINK_INDEX')
            a=anchors[i];need(any(r['unit_index']==positions[a['unit_id']] and r['source_index']==a['source_index'] and r['kind']=='B' for r in answer['relevant'][j]['evidence']),'ANCHOR_LINK_SOURCE')
    need(sorted(seen)==list(range(5)) and type(answer['unresolved']) is list and all(type(s) is str for s in answer['unresolved']),'ANCHOR_OR_UNRESOLVED')
    tokenizer,_=_load_tokenizer();tokens=len(tokenizer.encode(raw.decode(),add_special_tokens=False).ids)
    overflow=any('OUTPUT_OVERFLOW' in s for s in answer['unresolved'])
    return {'status':'OUTPUT_REFERENCE_LIMIT_REJECTED' if tokens>4096 else 'MODEL_DECLARED_INCOMPLETE' if overflow else 'STRUCTURE_AND_REFERENCES_ONLY',
        'response_sha256':hashlib.sha256(raw).hexdigest(),'reference_output_tokens':tokens,
        'raw_answer_unchanged':answer,'resolved_proposals':resolved,
        'native_result_created':False,'semantic_acceptance':False,'full29unit_or_company_acceptance':False,
        'new_calls':[0,0,0]}


def fail(reason):raise ValueError('B13_DEVELOPMENT_'+reason)


if __name__=='__main__':
    source=json.loads((OLD/'source.json').read_text());summary={}
    for name in ('response.log','response-revised.log'):
        p=HERE/'independent-input'/name;result=inspect(p.read_bytes(),source)
        (HERE/(name+'.readout.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        summary[name]={k:result[k] for k in ('status','response_sha256','reference_output_tokens','semantic_acceptance')}
        summary[name]['proposal_count']=len(result['resolved_proposals'])
    (HERE/'readout-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
