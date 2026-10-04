from pathlib import Path
from collections import Counter
from unittest.mock import patch
import json,sys,hashlib,argparse
parser=argparse.ArgumentParser(description='Offline complete current USD native census; no semantic role or credit.')
parser.add_argument('--code-root',type=Path,default=Path('.'))
parser.add_argument('--capture',type=Path,required=True)
parser.add_argument('--prior-inventory',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
sys.path.insert(0,str(args.code_root/'scripts'))
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.text_results_v2 import _ReportedFactMetadata,_verified_context
from vnext.historical_bond_sections import source_value
from vnext.governance_signals import _qname
capture=args.capture
prepared=json.loads((capture/'prepared.json').read_bytes());sources=json.loads((capture/'sources.json').read_bytes())
prior=json.loads(args.prior_inventory.read_bytes())
end=prepared['filing']['reportDate'];out=args.out;out.mkdir(exist_ok=False)
all_rows={};summary={}
with patch('socket.socket',side_effect=AssertionError('NO_NETWORK')):
 for kind in ['primary','xml']:
  raw=(capture/(kind+'.bin')).read_bytes();assert hashlib.sha256(raw).hexdigest()==sources[kind]['captured_sha256']
  parsed=parse_accession_xbrl_source(raw_bytes=raw);meta=_ReportedFactMetadata();meta.feed(raw.decode('utf-8-sig'));meta.close();assert meta.ordinal==len(parsed.facts)
  rows=[];unit_counts=Counter();current=0
  for fact in parsed.facts:
   context=parsed.contexts[fact['context_ref']]
   if not context['period_start']==context['period_end']==end:continue
   current+=1;unit=meta.units.get(fact['unit_ref']) if fact['unit_ref'] else None
   unit_counts[json.dumps(unit,sort_keys=True)]+=1
   if unit!={'measures':[('http://www.xbrl.org/2003/iso4217','USD')],'divided':False}:continue
   info=meta.facts[fact['ordinal']]
   proof=_verified_context(native={**context,'dimensions':dict(context['dimensions'])},metadata=meta)
   try:value,issue=source_value(fact,info),None
   except ValueError as error:value,issue=None,str(error)
   rows.append({'source_kind':kind,'ordinal':fact['ordinal'],'concept_qname':list(info['concept']),
    'source_text':fact['text'],'numeric_attributes':info['attrs'],'format_qname':list(_qname(info['attrs']['format'],info['namespaces'])) if info['attrs'].get('format') else None,'nil_attributes':[{'qname':list(_qname(k,info['namespaces'])),'value':v} for k,v in info['attrs'].items() if _qname(k,info['namespaces'])==('http://www.w3.org/2001/XMLSchema-instance','nil')],'context':proof,'declared_unit':unit,'normalized_source_value':value,
    'normalization_issue':issue,'semantic_debt_role_assigned':False,
    'in_prior_153_candidate_inventory':fact['ordinal'] in {r['ordinal'] for r in prior[kind]}})
  all_rows[kind]=rows
  summary[kind]={'all_parsed_native_facts':len(parsed.facts),'all_current_instant_facts':current,
   'current_unit_counts':dict(unit_counts),'all_current_USD_monetary_facts':len(rows),
   'prior_candidates_still_present_as_current_USD':sum(r['in_prior_153_candidate_inventory'] for r in rows),
   'additional_current_USD':sum(not r['in_prior_153_candidate_inventory'] for r in rows),
   'normalization_unresolved':sum(r['normalization_issue'] is not None for r in rows)}
(out/'all-current-monetary-facts.json').write_text(json.dumps(all_rows,ensure_ascii=False,indent=1)+'\n')
(out/'census.json').write_text(json.dumps({'report_end':end,'sources':summary,'calls':[0,0,0],
 'new_runs':0,'new_acceptances':0,'definition_or_semantic_debt_completeness_granted':False},indent=1)+'\n')
for kind,rows in all_rows.items():
 lines=[]
 for row in rows:
  if row['in_prior_153_candidate_inventory']:continue
  lines.append(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
 (out/(kind+'-additional-current-monetary.txt')).write_text(''.join(lines))
print(json.dumps(summary,indent=1))
