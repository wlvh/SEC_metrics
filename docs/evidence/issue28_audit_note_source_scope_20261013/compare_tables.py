"""Compare complete statement/note table cells and spans; no metric clearance."""
import hashlib,html,json,socket,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.normal_governance_input import _Sources
from vnext.table_grid import _AllTablesParser
x=json.loads(Path(sys.argv[2]).read_text());views=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
 for doc,start,end in zip(x['documents'],[975,979],[1848,1853]):
  source=_Sources(Path(sys.argv[1]),'marriott_international','1048286').read(doc['source_reference']['source_url'],accession=doc['filing']['accessionNumber'],role='financial_table_compare',media_type='text/html')
  text=source['raw_bytes'].decode('utf-8-sig');first=doc['visible_blocks'][start]['start'];last=doc['visible_blocks'][end]['start']
  fragment=text[first:last];parser=_AllTablesParser();parser.feed(fragment);parser.close()
  tables=[{'caption':' '.join(html.unescape(''.join(t.caption_parts)).split()),'rows':[
    [{'text':' '.join(html.unescape(''.join(c.raw_parts)).split()),'header':c.header,'rowspan':c.rowspan,'colspan':c.colspan} for c in row] for row in t.rows]} for t in parser.tables]
  views.append({'filing':doc['filing'],'start_character':first,'end_character':last,'tables':tables,'table_count':len(tables),'raw_cells':sum(len(r) for t in tables for r in t['rows'])})
a,b=[v['tables'] for v in views]
changed=[i for i,(u,v) in enumerate(zip(a,b)) if u!=v]
r={'source_shas':[d['primary_sha256'] for d in x['documents']], 'identical_table_structures_and_text':a==b,'views':[{k:v for k,v in w.items() if k!='tables'} for w in views],'changed_table_indices':changed,'source_admission_granted':False,'new_calls':[0,0,0]}
Path(sys.argv[3]).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False,indent=2))
