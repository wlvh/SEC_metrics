import json,shutil,sys,time,subprocess,os
from pathlib import Path
w=Path('/workspace/work'); code=w/'sec-company-compute';src=w/'baseline-company-packages/enphase_energy'; provided=w/'company-d04-live-material/input'; original=w/'company-d04-live-original-runtime';view=w/'company-d04-live-preparation';view.mkdir(exist_ok=True)
shutil.copytree(original,view,dirs_exist_ok=True)
shutil.copytree(src/'evidence',view/'evidence',dirs_exist_ok=True);shutil.copyfile(src/'config/company_registry.csv',view/'config/company_registry.csv');shutil.copyfile(provided/'config/ordinary_going_concern_assessment.json',view/'config/ordinary_going_concern_assessment.json')
sys.path[:0]=[str(code/'scripts'),str(code)]
from vnext.company_processing import export_processing
start=time.monotonic(); report=export_processing(installed_root=view,output_root=w/'company-d04-live-processing',runtime_output_root=w/'company-d04-live-program',trust_root=w/'company-d04-live-trust',company_id='enphase_energy')
metadata=json.loads((w/'company-d04-live-processing/processing.json').read_text());provided_metadata=json.loads((provided/'processing.json').read_text());report['equals_provider_packet_and_runtime_index']=metadata==provided_metadata;assert metadata==provided_metadata
report['elapsed_seconds']=time.monotonic()-start;report['supplier_commit']='51f9cd7cccf5814cc1219c467f902aca271d8692';report['source_checkpoint_id']=json.loads((src/'config/ordinary_source_checkpoint.json').read_text())['checkpoint_id'];(w/'company-d04-live-prepare.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
for root in (w/'company-d04-live-processing',w/'company-d04-live-program',w/'company-d04-live-trust'):
 for p in [root,*root.rglob('*')]:
  if not p.is_symlink():p.chmod(p.stat().st_mode & ~0o222)
