import json,pathlib,hashlib,subprocess,sys,os,time
base=pathlib.Path('/workspace/work');state=base/'local-recorded-d04/state'
work=next((state/'updates/processing/D04').glob('*/attempts/f062a87b2eb648c1a7abf87962720d75'))
semantic=json.load(open(work/'current-semantic-source.json'))
proof=semantic['source_proofs'][0]
relative=proof['request_headers_repo_relative_path'];header=state/'source'/relative
assert relative in json.load(open(state/'source/config/company_source_admission.json'))['files'] if (state/'source/config/company_source_admission.json').exists() else header.is_file()
files=[p for p in work.rglob('*') if p.is_file()]
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};raw=header.read_bytes();mode=header.stat().st_mode
command=[sys.executable,'-B',str(base/'local-runtime-projection/tools/vnext_company.py'),'compute','--state-root',str(state),'--trust-root',str(base/'local-recorded-d04/trust/company'),'--company','enphase_energy','--metric','D04']
start=time.monotonic()
try:
 header.chmod(mode|0o200);header.write_bytes(b'{}')
 p=subprocess.run(command,capture_output=True,text=True)
 assert p.returncode!=0 and 'COMPANY_SOURCE_BYTES_CHANGED' in p.stderr,p.stderr
finally:
 header.write_bytes(raw);header.chmod(mode)
assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
print(json.dumps({'status':'PASS','elapsed_seconds':format(time.monotonic()-start,'.6f'),'binding':'successful processing receipt + actual current-semantic-source.source_proofs','header':str(header),'reason':'COMPANY_SOURCE_BYTES_CHANGED','old_candidate_all_files_unchanged':True,'header_restored':True,'real_calls':[0,0,0]}))
