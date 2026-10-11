"""Read four existing proxy bodies; no acquisition, company state or model call."""
import hashlib,json,socket,subprocess,sys,time,types
from pathlib import Path
from vnext.canonical import content_hash
from vnext.governance_signals import resolve_c03,C03_SPEC_PATH
from vnext.normal_governance_input import _Sources
from vnext.specs import compile_spec_file

socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError('NETWORK_FORBIDDEN'))
program=Path(__file__).resolve().parents[3]
source_root=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve()
base='f51d8c3d27f3169b9cdb3a246295830882240c1f'
old=types.ModuleType('vnext._c03_main_baseline');old.__package__='vnext'
exec(compile(subprocess.check_output(['git','show',base+':scripts/vnext/governance_signals.py']),'<actual-main-governance>','exec'),old.__dict__)
rows=[
 ('marriott_international','1048286','2022-01-01','2022-12-31','0001140361-23-014123','ny20006599x500_def14a.htm','559da695a997c02bbfc5a3def4ed96c432acc82385153c241f118819a5a3ec3c','PASS','18686271'),
 ('marriott_international','1048286','2022-01-01','2022-12-31','0001140361-24-015465','ny20015439x1_def14a.htm','a25ce3426110e7f6ec546419607bff5d718b01825d5fa4faf970929acf294954','PASS','18715093'),
 ('lumen_technologies','18926','2022-01-01','2022-12-31','0000018926-23-000038','lumn-20230405.htm','a2ab506f740fa63eff2b7b6af22787b686d5720c6932077fec2f20495c474edb','C03_MULTIPLE_REPORTED_AMOUNTS',None),
 ('macys','794367','2022-01-30','2023-01-28','0001558370-23-005400','m-20230519xdef14a.htm','da7d47d8c8efbf7983a2fdeedebe637dccfb23e90fa912d6a132c08d4017dc43','C03_TARGET_PERIOD_NOT_FOUND',None),
]
proofs={};answers=[];spec=compile_spec_file(path=program/C03_SPEC_PATH,dependency_specs={})
for company,cik,start,end,acc,doc,sha,expected_reason,expected_value in rows:
 reader=_Sources(source_root,company,cik)
 src=reader.primary({'form':'DEF 14A','accessionNumber':acc,'primaryDocument':doc})
 assert hashlib.sha256(src['raw_bytes']).hexdigest()==sha
 for proof in reader.proofs.values():
  q=proof['proof'];path=source_root/q['request_repo_relative_path'];proofs[str(path)]=sha
 scope={'entity_scope':'registrant'}
 args={**src,'target':{'company_id':company,'period_start':start,'period_end':end,'scope':scope,'scope_key':content_hash(value=scope)},'expected_cik':cik,'compiled_spec':spec}
 def default(fn):
  try:return fn(**args),None
  except ValueError as error:return None,str(error)
 before,before_error=default(old.resolve_c03);same,same_error=default(resolve_c03)
 assert before==same and before_error==same_error,'Default result changed'
 t=time.perf_counter();new=resolve_c03(**args,sec_namespace_release='YEAR_QUARTER_OR_DATE');seconds=time.perf_counter()-t
 assert (new['selection']['reason_code'],new['result']['value'])==(expected_reason,expected_value)
 answers.append({'company':company,'target_period':[start,end],'accession':acc,'source_sha256':sha,'source_reference':src['source_reference'],'source_proofs':list(reader.proofs.values()),'default_matches_actual_main':True,'default_error':before_error,'explicit_reason':new['selection']['reason_code'],'explicit_value':new['result']['value'],'unit':new['result']['unit'],'result_id':new['result']['result_id'],'seconds':seconds,'candidate_locators':[r['locator'] for r in new['selection']['candidates']],'excluded_periods':sorted(set((x.get('period_start'),x.get('period_end')) for x in new['selection']['excluded']))})
 print(company,acc,before_error or before['selection']['reason_code'],'->',new['selection']['reason_code'],new['result']['value'],round(seconds,3),flush=True)
for path,sha in proofs.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha
result={'actual_main':base,'program_root':str(program),'source_root':str(source_root),'source_commit':'bcc0c0bc0293ba6b6ffc58b1f4e9034dbb52a786','tests_run_on_uncommitted_tree':True,'processing_sha256':{p:hashlib.sha256((program/p).read_bytes()).hexdigest() for p in ['scripts/vnext/governance_signals.py','scripts/vnext/xbrl_namespace_policy.py']},'new_calls':[0,0,0],'source_bytes_unchanged':True,'cases':answers,'not_granted':['first-filing-selection','whole-company-acceptance','production-adoption'],'first_reported_convention':'owner-decisions-2026-09-30/c03-convention.json; first value18686271 retained, later18715093 shown only as a distinct original disclosure'}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
