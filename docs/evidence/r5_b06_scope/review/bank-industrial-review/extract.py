from pathlib import Path
import json,hashlib,re,xml.etree.ElementTree as E
from html.parser import HTMLParser
O=Path(__file__).parent;B=Path('/Users/lyuhongwang/Documents/Codex/2026-09-11/r5-b06-followup/debt-review')
class P(HTMLParser):
 def __init__(self):super().__init__();self.text=[]
 def handle_data(self,d):self.text.append(d)
def text(raw):
 p=P();p.feed(raw);return ' '.join(' '.join(p.text).split())
for name in ['JPM','Ford']:
 old=json.loads((B/(name+'.json')).read_text());raw=Path(old['source']).read_bytes();assert hashlib.sha256(raw).hexdigest()==old['sha256'];root=E.fromstring(raw);ns={'x':'http://www.xbrl.org/2003/instance','d':'http://xbrl.org/2006/xbrldi'};contexts={x.attrib['id']:x for x in root.findall('x:context',ns)}
 notes=[];facts=[]
 for i,e in enumerate(root):
  n=e.tag.split('}')[-1]
  if n.endswith('TextBlock') and re.search('Borrow|LongTermDebt|Repurchase|VariableInterest|Consolidat|Condensed|EquityNote|Lessee|DebtDisclosure|CarryingValues|RelatedPartyTransactionImpactingBalance|SegmentReporting',n):
   v={'element_index':i,'concept':e.tag,'context':e.attrib.get('contextRef'),'raw_fact_text_sha256':hashlib.sha256((e.text or '').encode()).hexdigest(),'text':text(e.text or '')};notes.append(v)
  c=contexts.get(e.attrib.get('contextRef',''))
  if c is not None and c.find('x:period/x:instant',ns) is not None and c.find('x:period/x:instant',ns).text=='2025-12-31' and re.search('Debt|Borrow|FederalFunds|Repurchase|SecuritiesLoaned|FinanceLeaseLiability|StockholdersEquity|Liabilities|^Assets$',n):
   facts.append({'element_index':i,'concept':e.tag,'value':e.text,'unit':e.attrib.get('unitRef'),'context':e.attrib['contextRef'],'entity':c.find('x:entity/x:identifier',ns).text,'dimensions':[{'dimension':x.attrib['dimension'],'member':x.text} for x in c.findall('.//d:explicitMember',ns)]})
 (O/(name+'-raw-review.json')).write_text(json.dumps({'source':old['source'],'source_sha256':old['sha256'],'notes':notes,'facts':facts},indent=2))
 for v in notes:(O/(name+'-'+v['concept'].split('}')[-1]+'.txt')).write_text(v['text'])
 print(name,'notes',len(notes),'facts',len(facts))
