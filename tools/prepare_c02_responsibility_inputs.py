"""Prepare offline C02 responsibility groups, preserving text and whole tables.

This does not answer a question, call a provider, acquire a source or create a
Run. Every group keeps the full original string pool/visible blocks/geometry.
Only whole tables are assigned between groups, in their original order.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from vnext.continuous_request_context import measure_request, with_request_limits
from vnext.request_limits import RequestLimits


def _need(condition, reason):
    if not condition:raise ValueError(reason)


def _bytes(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')


def prepare_groups(raw, *, limits=None, max_groups=8):
    limits = RequestLimits(output_tokens=8192) if limits is None else limits
    _need(type(limits) is RequestLimits and limits.max_context_tokens<=200000
          and limits.max_payload_bytes<=8*1024*1024 and limits.output_tokens<=8192,
          'C02_GROUP_RESOURCE_CEILING_EXCEEDED')
    _need(type(max_groups) is int and 1<=max_groups<=8,'C02_GROUP_COUNT_BOUND_INVALID')
    body=json.loads(with_request_limits(raw,limits=limits))
    data=json.loads(body['messages'][1]['content'])
    _need(set(data)=={'strings','block_count','geometry','tables'},'C02_GROUP_INPUT_FORMAT_UNSUPPORTED')
    _need(type(data['block_count']) is int and 0<=data['block_count']<=len(data['strings'])
          and all(type(s) is str for s in data['strings']),'C02_GROUP_STRINGS_INVALID')
    tables=data['tables'];ids=[t['i'] for t in tables]
    _need(tables and len(ids)==len(set(ids)),'C02_GROUP_TABLE_IDS_MISSING_OR_DUPLICATE')
    original_prompt=body['messages'][0]['content']
    _need(original_prompt.count('all HTML tables')==1,'C02_GROUP_PROMPT_FORMAT_UNSUPPORTED')
    original_prompt=original_prompt.replace('all HTML tables','the complete assigned HTML tables',1)

    def packet(start, end, number):
        request=copy.deepcopy(body)
        ownership=('This first group owns facts supported by visible text alone and facts requiring its assigned tables.'
                   if number==1 else
                   'This group owns only facts requiring its assigned tables; the first group owns visible-text-only facts.')
        request['messages'][0]['content']=(
            f'Responsibility group {number}. All original visible blocks and the complete string pool are supplied. '
            'Assigned tables are exactly input.tables[*].i. Each assigned table is complete. '
            'Other whole tables are assigned to sibling groups; do not treat an unassigned table as absent. '
            +ownership+' Use all supplied text for entity, time, qualification and relationship context. '
            'Keep the original fact and unresolved schema. State any relationship you cannot establish as unresolved.\n\n'
            'No group may establish global absence, whole-metric completeness or acceptance. '
            'Retain unresolved cross-group dependencies for separate reconciliation of both original answers.\n\n'
            +original_prompt)
        request['messages'][1]['content']=_bytes({**data,'tables':tables[start:end]}).decode('utf-8')
        wire=_bytes(request)
        measured=measure_request(wire,limits=limits,require_reference=True)
        return wire,measured

    _,frame=packet(0,0,1)
    _need(frame['fits'],'C02_GROUP_FULL_TEXT_FRAME_EXCEEDS_LIMIT')
    groups=[];start=0;measurements=1
    while start<len(tables):
        _need(len(groups)<max_groups,'C02_GROUP_COUNT_BOUND_EXCEEDED')
        number=len(groups)+1
        wire,measured=packet(start,start+1,number);measurements+=1
        _need(measured['fits'],'C02_GROUP_WHOLE_TABLE_EXCEEDS_LIMIT:'+ids[start])
        best=(start+1,wire,measured)
        low,high=start+2,len(tables)
        # Finite search over table boundaries; no shrinking table/source data.
        while low<=high:
            end=(low+high)//2;wire,measured=packet(start,end,number);measurements+=1
            if measured['fits']:best=(end,wire,measured);low=end+1
            else:high=end-1
        end,wire,measured=best
        groups.append({'number':number,'table_start':start,'table_end_exclusive':end,
                       'table_ids':ids[start:end],'request':wire,'measurement':measured})
        start=end
    reconstructed=[]
    for g in groups:
        decoded=json.loads(json.loads(g['request'])['messages'][1]['content'])
        _need(all(decoded[k]==data[k] for k in ('strings','block_count','geometry')),
              'C02_GROUP_COMMON_INPUT_CHANGED')
        reconstructed.extend(decoded['tables'])
    _need(reconstructed==tables,'C02_GROUP_TABLE_COVERAGE_CHANGED')
    return {'original_request_sha256':hashlib.sha256(raw).hexdigest(),
        'limits':limits.as_dict(),'visible_blocks_per_group':data['block_count'],
        'strings_per_group':len(data['strings']),'geometry_per_group':len(data['geometry']),
        'table_count':len(tables),'measurement_calls':measurements,
        'frame_measurement':frame,'groups':groups,'source_data_reconstruction_equal':True,
        'method_readiness':'PREPARATION_ONLY_NO_INDEPENDENT_ANSWER_OR_COMPLETENESS_ACCEPTANCE',
        'calls':{'provider':0,'paid':0,'sec':0}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args(argv)
    _need(not args.out.exists(),'C02_GROUP_OUTPUT_ALREADY_EXISTS')
    result=prepare_groups(args.request.read_bytes())
    args.out.mkdir(parents=True)
    for group in result['groups']:
        name=f'group-{group["number"]:02d}-request-body.json'
        (args.out/name).write_bytes(group.pop('request'))
        group['request_file']=name
    (args.out/'index.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'groups':len(result['groups']),'tables':result['table_count'],
                      'method_readiness':result['method_readiness'],'calls':result['calls']}))


if __name__=='__main__':main()
