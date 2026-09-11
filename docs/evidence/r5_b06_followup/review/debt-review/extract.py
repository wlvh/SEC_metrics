from pathlib import Path
import xml.etree.ElementTree as E,json,hashlib,re
R=Path('/Users/lyuhongwang/Developer/SEC_metrics'); O=Path(__file__).parent
companies={'Southwest':'southwest_airlines_92380_000009238026000004/luv-20251231_htm.xml','Lumen':'lumen_technologies_18926_000001892626000014/lumn-20251231_htm.xml','Pfizer':'pfizer_78003_000007800326000026/pfe-20251231_htm.xml','JPM':'jpmorgan_chase_19617_000162828026008131/jpm-20251231_htm.xml','Ford':'ford_motor_company_37996_000003799626000015/f-20251231_htm.xml','Salesforce':'salesforce_1108524_000110852426000060/crm-20260131_htm.xml','Macys':'macy_s_794367_000162828026021721/m-20260131_htm.xml'}
all=[]
for company,p in companies.items():
 p=R/'evidence/accession_materials'/p; root=E.parse(p).getroot(); ctx={x.attrib['id']:E.tostring(x,encoding='unicode') for x in root if x.tag.endswith('}context')}; units={x.attrib['id']:E.tostring(x,encoding='unicode') for x in root if x.tag.endswith('}unit')}; facts=[]; notes=[]
 for n in root:
  tag=n.tag.split('}')[-1]; text=n.text or ''; cref=n.get('contextRef'); c=ctx.get(cref,''); instant=re.findall(r'<[^>]*instant>(.*?)</[^>]*instant>',c)
  if re.search(r'Debt|Borrow|Lease|Equity|Discount|Premium|IssuanceCost',tag,re.I) and cref and instant and instant[0] in ['2025-12-31','2026-01-31']:
   facts.append({'concept':n.tag,'value':text,'context_id':cref,'context_xml':c,'unit':n.get('unitRef'),'unit_xml':units.get(n.get('unitRef')),'decimals':n.get('decimals')})
  if tag.endswith('TextBlock') and re.search(r'Debt|Borrow|Lease|BalanceSheet',tag,re.I):
   try:
    h=E.fromstring('<root>'+text+'</root>'); clean=' '.join(' '.join(h.itertext()).split()); rows=[]
    for t in h.iter():
     if t.tag.split('}')[-1]=='tr': rows.append(' | '.join(' '.join(' '.join(z.itertext()).split()) for z in t if z.tag.split('}')[-1] in ['td','th']))
   except E.ParseError: clean=' '.join(re.sub('<[^>]+>',' ',text).split());rows=[]
   notes.append({'concept':n.tag,'context_id':cref,'text':clean,'table_rows':rows,'raw_text_sha256':hashlib.sha256(text.encode()).hexdigest()})
 result={'company':company,'source':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'facts':facts,'notes':notes}
 (O/(company+'.json')).write_text(json.dumps(result,indent=2));
 (O/(company+'-notes.txt')).write_text('\n\n'.join(n['concept']+'\n'+n['text']+'\nTABLE ROWS\n'+'\n'.join(n['table_rows']) for n in notes)); all.append({k:result[k] for k in ['company','source','sha256']})
 print(company,len(facts),'facts',len(notes),'notes')
(O/'source-index.json').write_text(json.dumps(all,indent=2))
