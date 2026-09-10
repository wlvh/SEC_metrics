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

from tests.vnext.common import REPO_ROOT
from vnext.annual_continuity_sources import frozen_foundation_receipts
from vnext.requirements import load_requirement_snapshot


def copy_foundation_receipts(root):
    for relative,proof in frozen_foundation_receipts().items():
        target=root/relative;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(proof['bytes'])


@lru_cache(maxsize=1)
def historical_test_root():
    temporary=tempfile.TemporaryDirectory(prefix='historical-authority-test-')
    atexit.register(temporary.cleanup)
    root=Path(temporary.name).resolve()
    for name in ('requirements','config','catalog','scripts','tools','docs','tests/fixtures',
                 'artifacts/vnext/table_stage_c_evidence','artifacts/vnext/table_qualification_freeze'):
        shutil.copytree(REPO_ROOT/name,root/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
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
