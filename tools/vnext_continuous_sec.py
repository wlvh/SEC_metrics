#!/usr/bin/env python3
"""Acquire one declared SEC dependency under the resumed Issue 28 allowance."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from vnext.continuous_sec_acquisition import live_sec_session
from vnext.normal_source_requirements import discover_saved_source_requirements
from vnext.canonical import canonical_json_bytes


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['plan','capture'])
    parser.add_argument('--company',required=True)
    parser.add_argument('--url',required=True)
    parser.add_argument('--refresh-metadata',action='store_true')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv);output=args.output.resolve()
    if output.exists() or output==ROOT or ROOT in output.parents:
        parser.error('Output must be a new file outside the code checkout')
    if args.command=='plan':
        discovered=discover_saved_source_requirements(repo_root=ROOT,company_id=args.company)
        matches=[r for r in discovered['requirements'] if r['source_url']==args.url]
        if len(matches)!=1:parser.error('URL is not a declared dependency of this company')
        result={'status':'OFFLINE_SOURCE_PLAN','dependency':matches[0],
            'refresh_metadata_requested':args.refresh_metadata,'calls':[0,0,0],'production_authorized':False}
    else:
        result=live_sec_session().capture(company_id=args.company,url=args.url,refresh_metadata=args.refresh_metadata)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as file:file.write(canonical_json_bytes(value=result))
    print(json.dumps({'status':result['status'],'calls':result['calls'],'output':str(output)}))
    return 0 if result['status'] in {'OFFLINE_SOURCE_PLAN','SUCCEEDED','EXISTING_VERIFIED_SOURCE_REUSED'} else 2


if __name__=='__main__':raise SystemExit(main())
