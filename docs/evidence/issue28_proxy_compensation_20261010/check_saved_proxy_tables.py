"""Three original proxy tables, no ledger/HTTP/model or company-state writes."""
import hashlib,json,socket,sys,time
from pathlib import Path
from sec_urls import submissions_url
from vnext.normal_governance_input import _Sources
from vnext.proxy_compensation_source import resolve_proxy_compensation_table,SPEC_PATH
from vnext.canonical import strict_json_loads
from vnext.observations import scope_key
from vnext.specs import compile_spec_file
socket.socket.connect=lambda *a,**kw: (_ for _ in ()).throw(AssertionError('NETWORK_FORBIDDEN'))
root=Path(__file__).resolve().parents[3];source=Path(sys.argv[1]).resolve();out=Path(sys.argv[2])
rows=[('macys','794367','0001558370-22-005031','tmb-20220520xdef14a.htm','2022-04-01','2021-01-31','2022-01-29',2021,'12290931'),
      ('marriott_international','1048286','0001193125-22-081138','d235712ddef14a.htm','2022-03-22','2021-01-01','2021-12-31',2021,None),
      ('jpmorgan_chase','19617','0000019617-22-000303','a2022proxystatement.htm','2022-04-04','2021-01-01','2021-12-31',2021,'84428145')]
answers=[];protected={};spec=compile_spec_file(path=root/SPEC_PATH,dependency_specs={})
for company,cik,acc,doc,filed,start,end,year,expected in rows:
 t=time.perf_counter();reader=_Sources(source,company,cik)
 filing={'form':'DEF 14A','accessionNumber':acc,'primaryDocument':doc,'filingDate':filed,'reportDate':''}
 proxy=reader.primary(filing)
 inv=reader.read(submissions_url(cik=int(cik)),role='sec_submissions_inventory',media_type='application/json')
 scope={'entity_scope':'registrant'}
 target={'company_id':company,'period_start':start,'period_end':end,'scope':scope,'scope_key':scope_key(scope=scope)}
 answer=resolve_proxy_compensation_table(**proxy,filing=filing,inventory=strict_json_loads(text=inv['raw_bytes'].decode()),
   company_id=company,cik=cik,target=target,fiscal_year=year,compiled_spec=spec)
 assert answer['result']['value']==expected,(company,answer['selection']['reason_code'],answer['result']['value'])
 if expected is None:assert answer['selection']['reason_code']=='C03_PROXY_SCT_MORE_THAN_ONE_CHIEF_EXECUTIVE'
 for item in reader.proofs.values():
  proof=item['proof'];p=source/proof['request_repo_relative_path'];protected[str(p)]=proof['request_body_sha256']
 elapsed=time.perf_counter()-t
 row={'company_id':company,'cik':cik,'filing':filing,'target':target,'source_reference':proxy['source_reference'],
      'source_proofs':[p['proof'] for p in reader.proofs.values()],
      'seconds':elapsed,'result':answer['result'],'selection':answer['selection'],
      'derived_table_count':len(answer['derived_assets'][0]['tables']),'new_calls':[0,0,0]}
 answers.append(row);print(company,answer['selection']['reason_code'],answer['result']['value'],round(elapsed,3),flush=True)
for p,sha in protected.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha
out.write_text(json.dumps({'base':'98e5312e2b1e5170724055a171942f9c10f337a6','source_root':str(source),
 'program_root':str(root),'original_reader_sha':'bcc0c0bc0293ba6b6ffc58b1f4e9034dbb52a786',
 'name_helper_sha':'4bcf6fbf9b92337940c6321eb84e1f1d10b9330c','working_tree_tests':True,
 'code_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['scripts/vnext/proxy_source_identity.py','scripts/vnext/proxy_compensation_source.py','scripts/vnext/organization_name_core.py']},
 'protected_original_files':len(protected),'new_calls':[0,0,0],'cases':answers},ensure_ascii=False,indent=2)+'\n')
