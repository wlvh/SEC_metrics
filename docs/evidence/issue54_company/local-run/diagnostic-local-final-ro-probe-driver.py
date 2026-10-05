import json,pathlib,subprocess,sys,os
cfg=json.load(open('/workspace/work/local-final-source-scope/local-company.json'));program=pathlib.Path(cfg['program_root'])
assert not any(p.stat().st_mode&0o222 for p in [program,*program.rglob('*')])
start={str(p):p.stat().st_mtime_ns for p in program.rglob('*') if p.is_file()}
p=subprocess.run([sys.executable,'-B','/workspace/work/local-cold-adapter-probe-v2.py',str(program),'/workspace/work/local-final-authority-ro-probe'],capture_output=True,text=True)
assert p.returncode==0,p.stderr
assert start=={str(p):p.stat().st_mtime_ns for p in program.rglob('*') if p.is_file()}
print(json.dumps({'uid':os.getuid(),'capabilities':[l.strip() for l in open('/proc/self/status') if l.startswith('CapEff:')],'read_only_program':True,'program_writes':False,'probe':json.loads(p.stdout)},indent=2))
