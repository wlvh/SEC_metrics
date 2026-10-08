from pathlib import Path
from datetime import datetime,timezone
import json,sys,re,hashlib,argparse
p=argparse.ArgumentParser(description='Rebind only new executor reference source quotes; no model response repair.')
p.add_argument('--code-root',type=Path,default=Path('.'))
p.add_argument('--full-input',type=Path,required=True)
p.add_argument('--previous-reference',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
sys.path.insert(0,str(a.code_root/'scripts'))
from vnext.historical_legal_review import validate_answer
from vnext.continuous_request_context import _load_tokenizer
request=json.loads((a.full_input/'request.json').read_bytes());texts={b['block_id']:b['text'] for b in request['blocks']};old=json.loads(a.previous_reference.read_bytes());answer=json.loads(json.dumps(old['contract_answer']))
manual={2876:'appeals and investigations',3864:'actively engaged in the defense',3937:'including product liability',3987:'certain legal matters of $567'}
words=re.compile(r'(?i)\b(?:patent|lawsuit|litigation|legal|claims?|suits?|complaint|proceed\w*|settle\w*|subpoena|CID|investigat\w*|defen\w*|plaintif\w*|contingen\w*|liability|insurance|indemnif\w*|accru\w*)\b')
def quote(name):
 text=texts[name];i=int(name[1:])
 if len(text)<=32:return text
 if i in manual:start=text.index(manual[i])
 else:
  m=words.search(text);start=max(0,m.start()-5) if m else 0
 start=min(start,max(0,len(text)-20))
 value=text[start:start+32]
 if len(value.rsplit(' ',1)[0])>=20:value=value.rsplit(' ',1)[0]
 assert min(20,len(text.strip()))<=len(value)<=32
 return value
for e in answer['decisions']:
 if e['decision']!='OUT_OF_SCOPE':e['quote']=quote(e['block_id'])
for e in answer['also_in_scope']:e['quote']=quote(e['block_id'])
validate_answer(request=request,raw_output=json.dumps(answer,ensure_ascii=False));literal=json.dumps(answer,ensure_ascii=False,separators=(',',':'))+'\n';tok,fallback=_load_tokenizer();assert tok is not None,fallback;count=len(tok.encode(literal,add_special_tokens=False).ids)
assert [(e['block_id'],e['decision']) for e in answer['decisions']]==[(e['block_id'],e['decision']) for e in old['contract_answer']['decisions']]
new={**old,'contract_answer':answer,'compact_reference_tokens':count,'reference_fits_output_limit':count<=4096,'new_source_quote_anchor_limit':32,'reference_representation_attempts':[{'source_anchor_characters':80,'tokens':4723,'fits':False},{'source_anchor_characters':48,'tokens':4153,'fits':False},{'source_anchor_characters':32,'tokens':count,'fits':count<=4096}],'third_shape_initial_short_heading_failure':'D02_REVIEW_QUOTE_NOT_THE_BLOCKS_OWN_WORDS:b3815; corrected source-window start to leave minimum20characters, unchanged contract','same_all_manual_IN_OUT_and_extra_positive_blocks':True,'new_reference_only_not_failed_response_trimmed':True}
a.out.mkdir(parents=True,exist_ok=False);path=a.out/'executor-reference-v3.json';path.write_text(json.dumps(new,ensure_ascii=False,indent=1)+'\n');(a.out/'contract-reference-compact-v3.json').write_text(literal);assert count<=4096
frozen={'reference_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'frozen_at':datetime.now(timezone.utc).isoformat(),'source_complete_before_reference':True,'independent_answer_or_current_v4_selector_read_before_freeze':False,'calls':[0,0,0]};(a.out/'reference-frozen-at-rebuild.json').write_text(json.dumps(frozen,indent=1)+'\n')
print('Finalbounded32char newsource-anchor representation; tokens',count,'fits',count<=4096,'114samepositive/150decisions unchanged; SHA',frozen['reference_sha256'])
