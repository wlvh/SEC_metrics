#!/usr/bin/env python3
"""Bounded B06 source intake, native candidate Run and offline cold read."""
import argparse,json,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from vnext import b06_new_source as work
from vnext import b06_disclosure as disclosure
from vnext.canonical import canonical_json_bytes,sha256_file,strict_json_file
from vnext.run_store import load_frozen_run


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['install-rules','run','read']);p.add_argument('--data-root',type=Path,required=True);p.add_argument('--run-dir',type=Path);p.add_argument('--company-id');p.add_argument('--output-json',type=Path)
    a=p.parse_args();data=a.data_root.resolve()
    if data==ROOT or ROOT in data.parents:raise ValueError('EXTERNAL_INPUT_ROOT_REQUIRED')
    if a.command=='install-rules':work.install_rules(data);return
    if a.run_dir is None or a.output_json is None:p.error('run/read require --run-dir and --output-json')
    if a.output_json.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    identity={'implementation_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip() if (ROOT/'.git').exists() else 'PORTABLE_PINNED_CHECKPOINT',
              'implementation_sha256':sha256_file(path=ROOT/'scripts/vnext/b06_new_source.py'),'rules_sha256':sha256_file(path=ROOT/'scripts/vnext/b06_disclosure.py'),
              'business_calls':{'provider':0,'paid':0,'sec':0}}
    start={**identity,'command':a.command}
    try:
        if a.command=='run':
            if not a.company_id:p.error('run requires --company-id')
            selected=work.select_input(data_root=data,company_id=a.company_id)
            primary=(data/selected['proofs'][-1]['request_repo_relative_path']).read_bytes();raw=(data/selected['proofs'][-2]['request_repo_relative_path']).read_bytes()
            start.update(selected=selected,original_proposal=disclosure.propose(raw=raw,primary=primary,target=work._target(selected)))
            work._write(a.output_json.with_suffix('.start.json'),start)
            outcome=work.create_primary_run(data_root=data,run_dir=a.run_dir.resolve(),company_id=a.company_id)
        else:
            manifest,records,_=load_frozen_run(run_dir=a.run_dir.resolve(),repo_root=data)
            outcome={'manifest':manifest,'results':[r for r in records if r['record_type']=='METRIC_RESULT'],'record_count':len(records),'business_calls':{'provider':0,'paid':0,'sec':0}}
        result={**identity,'status':'COMPLETED','outcome':outcome}
    except Exception as e:
        result={**identity,'status':'FAILED','error_type':type(e).__name__,'error':str(e),'start':start}
    work._write(a.output_json,result)
    print(json.dumps({'status':result['status'],'output':str(a.output_json),'error':result.get('error')},ensure_ascii=False))
    if result['status']!='COMPLETED':raise SystemExit(1)

if __name__=='__main__':main()
