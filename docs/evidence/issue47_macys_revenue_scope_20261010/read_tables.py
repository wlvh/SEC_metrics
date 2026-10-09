import json,hashlib
from pathlib import Path
from vnext.financial_structured import _InlineTableIndex
source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs');state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/statement-pilot-macys-20261009/state');items=[]
for year in [2022,2023]:
 p=state/'updates/B01/periods'/('FY'+str(year));v=json.loads((p/'current-result.json').read_text());records=[json.loads(x) for x in (p/'results'/v['version']/'records.jsonl').read_text().splitlines()];ref=next(r for r in records if r['record_type']=='SOURCE_REFERENCE' and r['source_role']=='target_primary');blob=next(r for r in records if r.get('raw_asset_id')==ref['raw_asset_id'] and r['record_type']=='RAW_BLOB');raw=(source/blob['storage_uri']).read_bytes();assert 'sha256:'+hashlib.sha256(raw).hexdigest()==ref['raw_asset_id'];index=_InlineTableIndex(raw);index.feed(raw.decode('utf-8-sig'));index.close();tables=[]
 for t in index.tables:
  rows=[[''.join(c.raw_parts) for c in row] for row in t.rows]
  joined=' '.join(' '.join(r) for r in rows).casefold()
  if 'total revenue' in joined and ('net sales' in joined or 'other revenue' in joined):tables.append({'table_order':t.order if hasattr(t,'order') else None,'rows':rows})
 items.append({'fiscal_year':year,'source_reference':ref,'source_blob':blob,'tables':tables})
Path('work/macys-revenue-scope/original-table-relations.json').write_text(json.dumps(items,indent=2)+'\n');print([(i['fiscal_year'],len(i['tables'])) for i in items])
