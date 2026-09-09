"""External evidence harness. It never supplies an adoption or publication verdict."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent
REPO = Path('/Users/lyuhongwang/Developer/SEC_metrics')
sys.path[:0] = [str(REPO), str(REPO / 'scripts')]
from vnext import annual_publication as annual, publication as pub
from vnext.annual_adoption import read, git, _tree_files
from vnext.canonical import content_hash

def save(name, value):
    (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def proof(path):
    data = path.read_bytes()
    return {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}

def state():
    old = read(REPO, 'docs/evidence/annual_publication/protection-final.json')['protected_files']
    return {'official_files': {name: proof(REPO / name) for name in old},
        'official_publications': _tree_files(root=REPO / 'outputs/publications'),
        'candidate': _tree_files(root=CANDIDATE),
        'historical_runtime': _tree_files(root=Path(CONTEXT['origin']['data_directory']).parents[5]),
        'stash': git('stash', 'list', '--format=%H').decode().splitlines(),
        'historical_worktrees': [w for w in git('worktree', 'list', '--porcelain').decode().split('\n\n')
                                if w and not w.startswith('worktree ' + str(REPO) + '\n')]}

CONTEXT = read(BASE, 'source-context.json')
CANDIDATE = Path(CONTEXT['origin']['candidate_directory'])
ROOT = BASE / 'final-rehearsal'
mode = sys.argv[1]
assert not git('status', '--porcelain', '--untracked-files=all').strip()
assert _tree_files(root=CANDIDATE) == CONTEXT['candidate_files']
for key in list(os.environ):
    if key.endswith('_API_KEY') or key in {'SEC_CONTACT_EMAIL', 'DEEPSEEK_API_KEY', 'OPENAI_API_KEY'}:
        os.environ.pop(key)
head = git('rev-parse', 'HEAD').decode().strip()
tree_text = git('ls-tree', '-r', head, 'scripts', 'tools', 'config', 'catalog', 'requirements').decode()
identity = {'head': head, 'git_tree_oid': git('rev-parse', head + '^{tree}').decode().strip(),
    'implementation_tree': content_hash(value=tree_text),
    'implementation_tree_definition': 'canonical content_hash of UTF-8 git ls-tree -r HEAD scripts tools config catalog requirements output',
    'tests': {name: proof(REPO / name) for name in ['tools/run_fast_tests.py',
        'tests/vnext/test_annual_publication.py', 'tests/vnext/test_annual_publication_rehearsal.py']}}
before = state()
if mode == 'prepare':
    assert not ROOT.exists()
    save('protection-before.json', before)
else:
    assert before == read(BASE, 'protection-before.json')
started = datetime.now(timezone.utc).isoformat()
github = []
real_output = subprocess.check_output
def traced_output(argv, *args, **kwargs):
    if argv[0] == 'gh':
        assert mode == 'prepare' and argv[1:2] == ['api']
        result = real_output(argv, *args, **kwargs)
        github.append({'argv': argv, 'response_sha256': hashlib.sha256(result).hexdigest(), 'response_size': len(result)})
        return result
    return real_output(argv, *args, **kwargs)
subprocess.check_output = traced_output
def blocked(*args, **kwargs):
    raise AssertionError('BUSINESS_NETWORK_FORBIDDEN')
socket.socket.connect = blocked
log = BASE / (mode + '.log')
code = 1
try:
    with log.open('w') as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        if mode == 'prepare':
            result = annual.prepare(candidate_dir=CANDIDATE, publication_root=ROOT)
            assert result['status'] == 'PREPARED_ISOLATED_COMPLETE_PUBLICATION'
            save('prepare.json', result)
            print(json.dumps(result, indent=2), flush=True)
        elif mode == 'validate-switch-read':
            prepared = read(BASE, 'prepare.json')
            directory = ROOT / 'outputs/publications' / prepared['publication_id']
            manifest = pub.verify_publication_bundle(bundle_dir=directory)
            print('FULL_NATIVE_BUNDLE_VALIDATION_PASSED', flush=True)
            result = annual.switch(publication_root=ROOT, publication_id=manifest['publication_id'], operation='publish')
            assert result['public_row_count'] == 327 and len(result['source_locations']) == 2
            save('switch-read.json', result)
            print(json.dumps(result, indent=2), flush=True)
        elif mode == 'integration':
            prepared = read(BASE, 'prepare.json')
            os.environ.update({'ANNUAL_PUBLICATION_TEST_ROOT': str(ROOT),
                'ANNUAL_PUBLICATION_TEST_ID': prepared['publication_id'],
                'ANNUAL_PUBLICATION_TEST_REPORT': str(BASE / 'integration-checks.json')})
            import unittest
            names = ['tests.vnext.test_annual_publication_rehearsal.AnnualPublicationRehearsalTest.' + n for n in
                ['test_complete_flow_faults_and_cold_source_reads', 'test_repeated_prepare_does_not_publish_or_query_approval']]
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
            assert result.wasSuccessful() and result.testsRun == 2 and not result.skipped
        else:
            raise ValueError(mode)
    assert state() == before
    assert git('rev-parse', 'HEAD').decode().strip() == head
    assert not git('status', '--porcelain', '--untracked-files=all').strip()
    code = 0
finally:
    save(mode + '-execution.json', {'command': sys.argv, 'cwd': str(Path.cwd()), 'code': identity,
        'started_at_utc': started, 'finished_at_utc': datetime.now(timezone.utc).isoformat(),
        'exit_status': code, 'log': {'path': str(log), **proof(log)},
        'harness': {'path': str(Path(__file__)), **proof(Path(__file__))},
        'publication_root': str(ROOT), 'candidate_root': str(CANDIDATE), 'github_reads': github,
        'new_provider_paid_sec_calls': [0, 0, 0], 'protection_equal': state() == before})
print(json.dumps({'mode': mode, 'exit_status': code, 'head': head, 'github_reads': len(github)}))
