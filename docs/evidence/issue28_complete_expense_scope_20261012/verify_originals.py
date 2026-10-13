"""Independent raw witnesses from the existing saved original statements."""
import argparse,hashlib,json,socket
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from vnext.normal_governance_input import _Sources
from vnext.deterministic_router import parse_accession_xbrl_source
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
company='paramount_skydance_paramount_global';records=[]
proofs=json.loads((Path(__file__).parent/'original-probe-plan.json').read_text())['actual_scopes']
for scope in proofs:
 annual=scope['annual_input'];filing=annual['filing'];expected=scope['reported_totals'][0]
 with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
  selected=_Sources(a.source_root,company,'813828').auditor_filing(filing)
 primary=next(x for x in selected if x['raw_blob']['media_type']=='text/html')
 raw=primary['raw_bytes'];sha=hashlib.sha256(raw).hexdigest()
 assert 'sha256:'+sha==expected['total']['source_reference']['raw_asset_id']
 parsed=parse_accession_xbrl_source(raw_bytes=raw)
 from vnext.financial_structured import _InlineTableIndex
 index=_InlineTableIndex(raw);index.feed(raw.decode('utf-8-sig'));index.close()
 checks=[]
 for kind,witness in [('revenue',expected['total']),('complete_expense',expected['complete_expense_statement']['expense']),('operating_income',expected['complete_expense_statement']['operating_income'])]:
  fact=next(f for f in parsed.facts if f['ordinal']==witness['ordinal'])
  context=parsed.contexts[fact['context_ref']]
  assert fact['qualified_name']==witness['concept'] and fact['context_ref']==witness['context_ref']
  assert index.units[fact['unit_ref']]['measures']==['iso4217:USD'] and not index.units[fact['unit_ref']]['divide']
  assert index.namespaces['iso4217']=={'http://www.xbrl.org/2003/iso4217'}
  assert str(int(context['entity_identifier']))=='813828' and not context['dimensions'] and not context['typed_dimension_count']
  assert context['period_start']==annual['table_input']['target_period']['period_start'] and context['period_end']==annual['table_input']['target_period']['period_end']
  amount=Decimal(fact['text'].replace(',','').replace('\u00a0','').strip())*Decimal(10)**int(fact.get('scale') or 0)
  if fact.get('sign')=='-':amount=-amount
  assert amount==Decimal(witness['value'])
  checks.append({'kind':kind,'ordinal':fact['ordinal'],'concept':fact['qualified_name'],'original_text':fact['text'],'sign':fact.get('sign'),'scale':fact.get('scale'),'value':str(amount),'context':{k:context[k] for k in ('entity_identifier','period_start','period_end','typed_dimension_count')}})
 for definition in expected.get('issuer_header_definition',[]):
  span=raw[definition['raw_start_byte']:definition['raw_end_byte']]
  assert hashlib.sha256(span).hexdigest()==definition['raw_span_sha256']
  assert 'Paramount Global and its consolidated subsidiaries' in span.decode('utf-8')
  assert 'Unless the context requires otherwise' in span.decode('utf-8')
  checks.append({'kind':'issuer_definition','raw_span':span.decode('utf-8'),'sha256':hashlib.sha256(span).hexdigest()})
 assert Decimal(checks[0]['value'])-Decimal(checks[1]['value'])==Decimal(checks[2]['value'])
 records.append({'filing':filing,'sha256':sha,'checks':checks,'basis':'Raw original facts/context/sign/scale and original definition bytes; does not alone prove full statement scope'})
current=Decimal(records[0]['checks'][0]['value']);prior=Decimal(records[1]['checks'][0]['value'])
ratio=(current-prior)/prior
result={'records':records,'growth_from_two_originals':str(ratio),'new_calls':[0,0,0],'scope':'Independent original witness check; full-scope validation remains in the shared reader and company path'}
a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'originals':len(records),'growth':str(ratio),'new_calls':[0,0,0]}))
