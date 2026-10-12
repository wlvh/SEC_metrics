"""Bounded direct original read, separate from the financial inspector's output."""
import hashlib,html,json,re
from pathlib import Path
E=Path(__file__).parent
r=json.loads((E/'actual-company.json').read_text())['results'][0]
m=json.loads((Path(r['first']['metrics'][0]['result_root'])/'manifest.json').read_text())
p=next(p for p in m['source_proofs'] if p['document_name']=='jpm-20251231.htm')
raw=(Path(m['source_root'])/p['request_repo_relative_path']).read_bytes()
assert hashlib.sha256(raw).hexdigest()==p['content_sha256']
s=raw.decode('utf-8-sig')
match=re.search(r'<ix:nonFraction\b(?=[^>]*\bcontextRef="c-2126")(?=[^>]*\bname="us-gaap:Revenues")[^>]*>42,758</ix:nonFraction>',s)
assert match is not None
left=s.rfind('<table',0,match.start());right=s.index('</table>',match.end())+len('</table>')
table=s[left:right]
visible=lambda v:' '.join(html.unescape(re.sub('<[^>]*>',' ',v)).split())
table_text=visible(table)
assert 'Total international' in table_text and 'in millions' in table_text and '2025' in table_text
row_start=s.rfind('<tr',left,match.start());row_end=s.index('</tr>',match.end())+len('</tr>')
row=s[row_start:row_end];row_text=visible(row)
assert 'Total international' in row_text and '42,758' in row_text
context=re.search(r'<xbrli:context\b[^>]*id="c-2126"[^>]*>.*?</xbrli:context>',s).group()
assert '0000019617' in context and '2025-01-01' in context and '2025-12-31' in context
assert 'jpm:TotalInternationalMember' in context
assert re.search(r'<xbrli:unit\b[^>]*id="usd"[^>]*>.*?iso4217:USD.*?</xbrli:unit>',s)
definition='Revenue is composed of net interest income and noninterest revenue.'
near=visible(s[right:right+22000])
assert definition in near
assert 'unitRef="usd"' in match.group() and 'scale="6"' in match.group()
value=42758*10**6;assert str(value)==r['csv']['value']
report={'method':'Direct original HTML/native context/linked footnote read, not a full visual audit',
 'source_url':p['source_url'],'source_path':p['request_repo_relative_path'],'raw_sha256':p['content_sha256'],
 'original_table_sha256':hashlib.sha256(table.encode()).hexdigest(),'table_text':table_text,
 'international_row_text':row_text,'native_fact':match.group(),'native_context':context,
 'definition':definition,'scope':'Total international, source-defined net interest plus noninterest revenue',
 'value':value,'unit':'USD','period_start':'2025-01-01','period_end':'2025-12-31',
 'regional_sum_used':False,'new_calls':[0,0,0]}
(E/'original-source.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS_DIRECT_ORIGINAL_INTERNATIONAL_NET_REVENUE',value,p['content_sha256'])
print(row_text)
print(definition)
