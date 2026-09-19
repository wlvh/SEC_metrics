"""Test-only frozen authority data; execute the current checkout's validators.

These copies deliberately do not represent the current publication mirrors.
They never become a production grant or a second imported implementation.
"""
import atexit
from functools import lru_cache
import json
from pathlib import Path
import shutil
import tempfile
import time

from tests.vnext.common import REPO_ROOT
from vnext.annual_continuity_sources import frozen_foundation_receipts
from vnext.requirements import load_requirement_snapshot


def copy_foundation_receipts(root):
    for relative,proof in frozen_foundation_receipts().items():
        target=root/relative;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(proof['bytes'])
    # These tests replay the already recorded model, not the current selection.
    # Recover its exact bytes from the existing complete publication.
    relative='config/provider_model_runtime.json'
    expected=json.loads((REPO_ROOT/'requirements/issue_15_v1/baseline_manifest.json').read_text())['runtime_authority_files'][relative]
    pointer=json.loads((REPO_ROOT/'outputs/active_publication.json').read_text())
    bundle=REPO_ROOT/'outputs/publications'/pointer['publication_id']
    manifest=json.loads((bundle/'publication_manifest.json').read_text())
    matches=[entry for entry in manifest['files'] if entry['path'].endswith('/'+relative)
             and entry['sha256']==expected['sha256'] and entry['size']==expected['size']]
    assert matches, 'Recorded model configuration is missing'
    raw=(bundle/matches[0]['path']).read_bytes()
    import hashlib
    assert hashlib.sha256(raw).hexdigest()==expected['sha256']
    (root/relative).write_bytes(raw)


PREFIX='historical-authority-test-'
# docs/evidence is 1.1 GB of archived material; the Requirement authority names
# five files inside it and the annual policies live in its top level. Copying
# the directory whole made each of these roots 1.2 GB, and a case killed by the
# 30 second timeout never runs atexit, so twenty-four leaked roots filled the
# disk and failed twelve unrelated fast cases with ENOSPC. Copying what is
# actually read makes a root 54 MB, and the suite went from FAILED in 171.9s
# with twelve failures to PASSED in 114.4s with none.
_EVIDENCE=('docs/evidence/issue28_continuous/frozen-parent-v10-index.json',
           'docs/evidence/r5_b06_followup/amendment_assessments.json',
           'docs/evidence/r5_b06_followup/measurement_relationships.json',
           'docs/evidence/r5_b06_scope/composition_assessments.json',
           'docs/evidence/r5_b06_scope/debt_scope_relationships.json')


def _sweep_leaked_roots(*,older_than_seconds=7200):
    """Remove roots a killed process left behind, never a running sibling's.

    The age bound is far above every registered per-case timeout, so a root
    this old belongs to no live case even when the suite runs with --jobs.
    """
    cutoff=time.time()-older_than_seconds
    for path in Path(tempfile.gettempdir()).glob(PREFIX+'*'):
        try:
            if path.is_dir() and not path.is_symlink() and path.stat().st_mtime < cutoff:
                shutil.rmtree(path,ignore_errors=True)
        except OSError:
            continue


@lru_cache(maxsize=1)
def historical_test_root():
    _sweep_leaked_roots()
    temporary=tempfile.TemporaryDirectory(prefix=PREFIX)
    atexit.register(temporary.cleanup)
    root=Path(temporary.name).resolve()
    for name in ('requirements','config','catalog','scripts','tools','tests/fixtures',
                 'artifacts/vnext/table_stage_c_evidence','artifacts/vnext/table_qualification_freeze'):
        shutil.copytree(REPO_ROOT/name,root/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(REPO_ROOT/'docs',root/'docs',
                    ignore=shutil.ignore_patterns('__pycache__','*.pyc','evidence'))
    for relative in _EVIDENCE+tuple('docs/evidence/'+path.name
                                    for path in (REPO_ROOT/'docs/evidence').glob('*.json')):
        target=root/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(REPO_ROOT/relative,target)
    matrix=json.loads((REPO_ROOT/'config/table_qualification_matrix.json').read_text())
    def sources(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key=='source_repo_relative_path':yield item
                else:yield from sources(item)
        elif isinstance(value,list):
            for item in value:yield from sources(item)
    from vnext.table_qualification_freeze import LAYOUT_FIXTURE_ROOT
    fixture_values=[]
    for family in matrix['families']:
        for value in family.values():
            if isinstance(value,dict) and 'fixture_id' in value:
                relative=LAYOUT_FIXTURE_ROOT/value['fixture_id']/'fixture_manifest.json'
                shutil.copytree((REPO_ROOT/relative).parent,(root/relative).parent)
                fixture_values.append(json.loads((REPO_ROOT/relative).read_text()))
    for relative in sources([matrix,*fixture_values]):
        source=REPO_ROOT/relative;target=root/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        for headers in source.parent.glob(source.name+'*.headers.json'):
            shutil.copy2(headers,target.parent/headers.name)
    for name in ('requests_log.csv','requests_log_manifest.json'):
        target=root/'evidence'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(REPO_ROOT/'evidence'/name,target)
    copy_foundation_receipts(root)
    load_requirement_snapshot(snapshot_dir=root/'requirements/issue_15_v1')
    return root
