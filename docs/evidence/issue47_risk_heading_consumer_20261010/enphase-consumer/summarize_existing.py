"""Read already completed CLI outputs; do not re-execute the company."""
import csv,hashlib,json
from pathlib import Path
state=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/enphase-statements-company-jvkm2nml/state')
base=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/enphase-d01-company-n_s47i45')
root=Path('work/d01-enphase-consumer');refs=json.loads((root/'existing-reference.json').read_text())['years']
rows=list(csv.DictReader((base/'read/metrics_matrix.csv').open()));selected=[r for r in rows if r['metric_id']=='D01']
assert len(rows)==24 and len(selected)==4
comparisons=[]
for row in selected:
 old=refs[row['fiscal_year']]['reference'];texts=row['value'].splitlines()
 assert texts==old['headings_read'] and row['accession']==old['accession']
 assert row['period_start']==row['fiscal_year']+'-01-01' and row['period_end']==row['fiscal_year']+'-12-31' and row['unit']=='text'
 comparisons.append({'fiscal_year':row['fiscal_year'],'heading_count':len(texts),'ordered_text_equal':True,'result_id':row['result_id'],'old_result_id':old['checked_identity']['bound_from']['result_id']})
failed=json.loads((state/'updates/D01/periods/FY2021/latest-check.json').read_text())
assert failed['reason']=='DETERMINISTIC_TEXT_HEADINGS_EXCEED_BOUND'
record={'initial_fiveyear':json.loads((root/'first-company.json').read_text()),'fouryear_operations':[json.loads((base/(name+'.json')).read_text()) for name in ['existing-four-D01-coordinates','repeat-forbidden-D01-factory','independent-read']],'comparisons':comparisons,'rows':rows,'FY2021_failed_check':failed,'state_root':str(state),'output_root':str(base),'new_calls':[0,0,0],'new_original_reading':False,'independent_reader_limitation':'FY2021 failure not listed after FY2022-2025 subset; public PR131 receiving follows'}
(root/'fouryear-existing-summary.json').write_text(json.dumps(record,indent=2)+'\n')
print([(r['fiscal_year'],r['heading_count']) for r in comparisons],flush=True)
