"""Read-only diagnostic inventory. Never emit accepted assessments or rewrite calls."""
from pathlib import Path
import json,hashlib,collections
from vnext.capacity_reference_contract import restore_base_request,_expand_compact_response,_owners
from vnext.capacity_semantic_review import _restore_units
from vnext.r6_semantic_review import _source_items
from vnext.canonical import content_hash,sha256_file
root=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls/0170');out=Path(__file__).resolve().parent
paths=['intent.json','terminal.json','source.json','semantic-request.json','wire/raw-response.bin','wire/assistant-output.bin']
before={name:sha256_file(path=root/name) for name in paths}
request=json.loads((root/'semantic-request.json').read_text());original=json.loads((root/'wire/assistant-output.bin').read_text());base=restore_base_request(request);expanded=_expand_compact_response(original,request);units=_restore_units(base['units'],base['shared_source_dictionaries']);owners=_owners(base);rows=[];duplicates=collections.defaultdict(list)
for number,(raw,finding) in enumerate(zip(original['findings'],expanded['findings']),1):
 references=[]
 for ref in finding['evidence']:
  key=(ref['kind'],ref['source_unit_index'],ref['source_index']) if ref['kind']=='NATIVE_SUPPLEMENT' else (ref['kind'],ref['source_index'])
  owner=owners[key];kind,items=_source_items(units[owner]);item=items[ref['source_index']]
  references.append({'reference':ref,'unit_index':owner,'unit_id':units[owner]['unit_id'],'source_item':item})
 duplicate_key=content_hash(value=finding);duplicates[duplicate_key].append(number)
 rows.append({'row':number,'raw_tuple':raw,'decoded_classification':{k:finding[k] for k in ['kind','subject','timing']},'reason':finding['reason'],'references':references,'identical_finding_id':duplicate_key})
for row in rows:row['duplicate_rows']=duplicates[row['identical_finding_id']]
result={'record_type':'FAILED_RESPONSE_DIAGNOSTIC_ONLY','source_call':170,'raw_hashes':before,'program_mapping':'Exact zero-based codebook decoding; no shifted or inferred codes','codebooks':request['response_protocol']['classification_codebooks'],'definitions':request['category_definitions'],'rows':rows,'unit_review_census':original['units'],'credit':'NONE; no modified response, Candidate, Evidence, Run or accepted classification set emitted'}
(out/'all-110-rows.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
lines=['# 原170逐行诊断输入（不产生成功信用）','']
for row in rows:
 if row['row']!=row['duplicate_rows'][0]:continue
 texts=[ref['source_item'].get('text',ref['source_item'].get('raw_xml','')) for ref in row['references']]
 lines += [f"## 原行 {row['duplicate_rows']} / {row['raw_tuple'][3]}",f"分类：{row['decoded_classification']}",f"解释：{row['reason']}",'原文：'+'\n'.join(texts),'']
(out/'unique-source-reading.md').write_text('\n'.join(lines)+'\n')
assert before=={name:sha256_file(path=root/name) for name in paths}
print({'rows':len(rows),'unique':len(duplicates),'source_kinds':dict(collections.Counter(ref['reference']['kind'] for row in rows for ref in row['references']))})
