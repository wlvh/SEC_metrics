"""Read #28's saved D02 Item 8 candidates against the pinned peer v2 rule."""
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch


ROOT=Path(__file__).resolve().parents[5]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]


def blocked(*args,**kwargs):
    raise AssertionError('NETWORK_FORBIDDEN')


with (patch.object(socket.socket,'connect',side_effect=blocked),
      patch.object(socket,'getaddrinfo',side_effect=blocked),
      patch('sec_http.urlopen',side_effect=blocked)):
    from vnext.normal_run_v3 import prepare_case
    from vnext.d02_text_results_v3 import prepare_business_text_sources
    from vnext.d02_item8_category_28_v1 import classify as v1
    from vnext.d02_item8_category_28_v2 import classify as v2
    from vnext.text_business_candidates import _LEGAL
    examples=(
        'We face litigation, which could result in a significant loss.',
        'Litigation, brought by a customer against us in 2025, remains unresolved.',
    )
    synthetic=[{'v1_left_out':v1(text=text,keyword=_LEGAL)['left_out'],
                'v2_left_out':v2(text=text,keyword=_LEGAL)['left_out'],
                'text':text} for text in examples]
    rows=[]
    for company in ('lumen_technologies','pfizer','paramount_skydance_paramount_global',
                    'enphase_energy'):
        case=prepare_case(data_root=ROOT,company_id=company,metric_id='D02')
        sources=prepare_business_text_sources(metric_id='D02',**{
            key:value for key,value in case['text_arguments'].items()
            if key!='compiled_spec'})
        excerpts=[excerpt for proposal in sources['proposals'].values()
                  for excerpt in proposal['D02']['candidates']
                  if excerpt['section_id']=='ITEM_8']
        v1_removed=[];v2_removed=[];changed=[]
        for excerpt in excerpts:
            a=v1(text=excerpt['text'],keyword=_LEGAL)['left_out']
            b=v2(text=excerpt['text'],keyword=_LEGAL)['left_out']
            identity={'block_index':excerpt['block_index'],
                      'source_reference_id':excerpt['source_reference_id'],
                      'raw_span_sha256':excerpt['raw_span_sha256']}
            if a:v1_removed.append(identity)
            if b:v2_removed.append(identity)
            if a!=b:changed.append({**identity,'v1_left_out':a,'v2_left_out':b})
        rows.append({'company_id':company,'item8_keyword_candidates':len(excerpts),
                     'v1_removed':v1_removed,'v2_removed':v2_removed,
                     'changed':changed})
result={'record_type':'ISSUE28_D02_V2_SAVED_ITEM8_COMPARISON',
        'peer_source_commit':'147957c400c3361ab26ee0b04bbb89b2a692cadd',
        'source_root':str(ROOT),'synthetic':synthetic,'rows':rows,
        'new_real_calls':[0,0,0],'new_result_or_run':False,
        'content_acceptance':False}
(HERE/'compare-current.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'synthetic_fixed':sum(x['v1_left_out'] and not x['v2_left_out']
                                          for x in synthetic),
                  'saved_item8_candidates':sum(x['item8_keyword_candidates'] for x in rows),
                  'saved_differences':sum(len(x['changed']) for x in rows),
                  'calls':[0,0,0]}),flush=True)
