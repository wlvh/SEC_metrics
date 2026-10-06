"""Transport coverage and resource bounds; no model answer or acceptance tests."""
import json
import unittest

from tools.prepare_c02_responsibility_inputs import prepare_groups
from vnext.request_limits import RequestLimits


def request(tables=6):
    data={'strings':['Repeated context with exact whitespace\n','◾'],
          'block_count':1,'geometry':[[1,1,False]],
          'tables':[{'i':f'table_{i:06d}','s':[20,1],'c':0,'g':0,
                     'x':[[r,0,1] for r in range(20)]} for i in range(tables)]}
    body={'model':'deepseek-flash','temperature':0,'max_tokens':64,'stream':False,
          'thinking':{'type':'disabled'},
          'response_format':{'type':'json_object'},'messages':[
              {'role':'system','content':'You receive all visible blocks and all HTML tables. Return facts and unresolved.'},
              {'role':'user','content':json.dumps(data,ensure_ascii=False,separators=(',',':'))}]}
    return json.dumps(body,ensure_ascii=False,separators=(',',':')).encode()


class C02ResponsibilityInputTest(unittest.TestCase):
    def test_whole_tables_and_all_common_text_reconstruct_original_in_order(self):
        raw=request();limits=RequestLimits(output_tokens=64,max_context_tokens=650)
        original=json.loads(json.loads(raw)['messages'][1]['content']);result=prepare_groups(raw,limits=limits)
        self.assertGreater(len(result['groups']),1)
        tables=[]
        for g in result['groups']:
            body=json.loads(g['request']);data=json.loads(body['messages'][1]['content'])
            self.assertEqual({k:data[k] for k in ('strings','block_count','geometry')},
                             {k:original[k] for k in ('strings','block_count','geometry')})
            self.assertEqual(body['max_tokens'],64)
            self.assertIn('No group may establish global absence',body['messages'][0]['content'])
            self.assertLessEqual(g['measurement']['context_tokens'],650)
            tables.extend(data['tables'])
        self.assertEqual(tables,original['tables'])
        self.assertEqual(result['calls'],{'provider':0,'paid':0,'sec':0})

    def test_duplicate_table_identity_cannot_hide_missing_coverage(self):
        body=json.loads(request());data=json.loads(body['messages'][1]['content'])
        data['tables'][1]['i']=data['tables'][0]['i'];body['messages'][1]['content']=json.dumps(data)
        with self.assertRaisesRegex(ValueError,'TABLE_IDS_MISSING_OR_DUPLICATE'):
            prepare_groups(json.dumps(body).encode(),limits=RequestLimits(output_tokens=64))

    def test_unfit_common_frame_or_whole_table_stops_without_shrinking_source(self):
        with self.assertRaisesRegex(ValueError,'FULL_TEXT_FRAME_EXCEEDS_LIMIT'):
            prepare_groups(request(),limits=RequestLimits(output_tokens=64,max_context_tokens=100))
        body=json.loads(request(tables=1));data=json.loads(body['messages'][1]['content'])
        data['tables'][0].update(s=[1000,1],x=[[r,0,1] for r in range(1000)])
        body['messages'][1]['content']=json.dumps(data)
        with self.assertRaisesRegex(ValueError,'WHOLE_TABLE_EXCEEDS_LIMIT'):
            prepare_groups(json.dumps(body).encode(),limits=RequestLimits(output_tokens=64,max_context_tokens=400))

    def test_group_bound_stops_instead_of_unbounded_attempts(self):
        with self.assertRaisesRegex(ValueError,'GROUP_COUNT_BOUND_EXCEEDED'):
            prepare_groups(request(),limits=RequestLimits(output_tokens=64,max_context_tokens=650),max_groups=1)

    def test_original_context_and_received_output_limits_cannot_be_raised(self):
        for limits in (RequestLimits(max_context_tokens=200001),RequestLimits(output_tokens=8193),
                       RequestLimits(max_payload_bytes=8*1024*1024+1)):
            with self.subTest(limits=limits),self.assertRaisesRegex(ValueError,'RESOURCE_CEILING_EXCEEDED'):
                prepare_groups(request(),limits=limits)


if __name__=='__main__':unittest.main()
