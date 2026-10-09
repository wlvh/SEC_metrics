"""Install the retained main local runtime for the unchanged online interface.

The lightweight saved-source producer stays in the candidate. New native
online tasks retain main's fixed program until that path is replaced explicitly;
old tasks retain their already saved program. No SEC or model action occurs here.
"""
from pathlib import Path
import json,os,subprocess,sys,tempfile

RETAINED_MAIN = '8588ccbbb1c91d81e0fb1a89dff3575214282549'


def install_retained_local(*, repo_root, output_root):
    repo,output=Path(repo_root),Path(output_root)
    def git(*args):
        result=subprocess.run(['git','-C',str(repo),*args],capture_output=True,text=True)
        if result.returncode:raise ValueError('RETAINED_LOCAL_SOURCE_UNAVAILABLE:'+result.stderr.strip())
        return result.stdout
    git('cat-file','-e',RETAINED_MAIN+'^{commit}')
    with tempfile.TemporaryDirectory(prefix='sec-metrics-retained-local-') as folder:
        source=Path(folder).resolve()/'program-source'
        subprocess.run(['git','clone','--shared','--no-checkout','--quiet',str(repo),str(source)],check=True,capture_output=True)
        subprocess.run(['git','-C',str(source),'update-ref','HEAD',RETAINED_MAIN],check=True,capture_output=True)
        subprocess.run(['git','-C',str(source),'read-tree',RETAINED_MAIN],check=True,capture_output=True)
        names=set(git('ls-tree','-r','--name-only',RETAINED_MAIN).splitlines())
        paths={p for p in names if p.startswith(('scripts/','tools/','catalog/','config/','requirements/')) or '/' not in p}
        for path in sorted(names):
            if path.startswith('requirements/') and path.endswith('/baseline_manifest.json'):
                manifest=json.loads(git('show',RETAINED_MAIN+':'+path))
                paths.update(manifest.get('execution_authority',{}).get('files',{}))
                paths.update(manifest.get('new_rule_files',{}))
        paths.update(p for p in names if p.startswith('docs/evidence/issue28_continuous/frozen-parent-v10'))
        subprocess.run(['git','-C',str(source),'checkout-index','--stdin'],
                       input='\n'.join(sorted(paths & names))+'\n',text=True,check=True,capture_output=True)
        # Keep the retained business implementation, but allow the host's
        # ordinary system /tmp alias. The real installer below binds this
        # changed platform helper into the new private runtime; old tasks
        # keep their previously saved program.
        rate = source/'scripts/vnext/company_local_acquisition.py'
        original = rate.read_text()
        old = "root = Path('/tmp')/('sec-metrics-sec-rate-'+str(os.getuid()))"
        if original.count(old) != 1:
            raise ValueError('RETAINED_LOCAL_RATE_SEAM_CHANGED')
        rate.write_text(original.replace(old,
            "root = Path('/tmp').resolve()/('sec-metrics-sec-rate-'+str(os.getuid()))"))
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
        # Avoid loading caller modules through PYTHONPATH before the retained
        # CLI establishes its own source root. This installation has no HTTP.
        env.pop('PYTHONPATH',None)
        process=subprocess.run([sys.executable,'-B',str(source/'tools/vnext_company.py'),
            'install-runtime','--kind','local','--output-root',str(output)],
            env=env,capture_output=True,text=True)
        if process.returncode:
            raise ValueError('RETAINED_LOCAL_INSTALL_FAILED:'+process.stderr.strip())
        report=json.loads(process.stdout)
        if report.get('status')!='RUNTIME_INSTALLED' or report.get('sec_originals_installed') is not False:
            raise ValueError('RETAINED_LOCAL_INSTALL_INCOMPLETE')
        return {**report,'retained_main_commit':RETAINED_MAIN}
