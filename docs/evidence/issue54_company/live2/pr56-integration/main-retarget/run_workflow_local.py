"""Execute the run steps of a GitHub workflow locally, one fresh temp dir per job."""
import concurrent.futures as cf, itertools, json, os, re, subprocess, sys, tempfile, time, yaml
wf, jobs_sel, out = sys.argv[1], sys.argv[2].split(','), sys.argv[3]
os.makedirs(out, exist_ok=True)
d = yaml.safe_load(open(wf)); base_env = {**os.environ}
def expand(job_id, job):
    m = (job.get('strategy') or {}).get('matrix')
    if not m: return [(job_id, {})]
    keys = list(m); return [(job_id+'-'+'-'.join(str(v) for v in vals), dict(zip(keys, vals))) for vals in itertools.product(*[m[k] for k in keys])]
def sub(s, ctx):
    return re.sub(r'\$\{\{\s*([\w.]+)\s*\}\}', lambda x: str(ctx[x.group(1)]), str(s))
def run_job(name, job, matrix):
    tmp = tempfile.mkdtemp(prefix='wf-'+name+'-', dir='/home/user/work/wfruns')
    ctx = {'runner.temp': tmp, 'github.run_id': 'local', 'github.run_attempt': '1', **{'matrix.'+k: v for k, v in matrix.items()}}
    rec = {'job': name, 'timeout_minutes': job.get('timeout-minutes'), 'steps': []}; start = time.time()
    for st in job['steps']:
        if 'run' not in st or 'pip install' in st['run']: continue
        env = {**base_env, **{k: sub(v, ctx) for k, v in (st.get('env') or {}).items()}}
        if 'PYTHONPATH' in (st.get('env') or {}) and base_env.get('PYTHONPATH'): env['PYTHONPATH'] = env['PYTHONPATH'] + os.pathsep + base_env['PYTHONPATH']
        s = time.time(); p = subprocess.run(['bash', '-e', '-c', sub(st['run'], ctx)], cwd=os.getcwd(), env=env, capture_output=True, text=True)
        log = os.path.join(out, f"{name}--{len(rec['steps'])}.log"); open(log, 'w').write(p.stdout + '\n--- stderr ---\n' + p.stderr)
        summ = [json.loads(l) for l in p.stdout.splitlines() if l.startswith('{"allowed_skips"')]
        rec['steps'].append({'name': st.get('name'), 'rc': p.returncode, 'seconds': round(time.time()-s, 1), 'log': os.path.basename(log), 'unittest_summary': summ})
        if p.returncode: break
    rec['seconds'] = round(time.time()-start, 1); rec['ok'] = all(x['rc'] == 0 for x in rec['steps'])
    rec['within_timeout'] = rec['timeout_minutes'] is None or rec['seconds'] <= 60*rec['timeout_minutes']
    json.dump(rec, open(os.path.join(out, name+'.json'), 'w'), indent=1); return rec
os.makedirs('/home/user/work/wfruns', exist_ok=True)
todo = [(n, d['jobs'][j], m) for j in jobs_sel for n, m in expand(j, d['jobs'][j])]
with cf.ThreadPoolExecutor(int(os.environ.get('WF_PARALLEL', '3'))) as ex:
    for r in ex.map(lambda t: run_job(*t), todo):
        print(json.dumps({k: r[k] for k in ('job', 'ok', 'seconds', 'timeout_minutes', 'within_timeout')}), flush=True)
