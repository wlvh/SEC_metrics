"""Read-only repeat of the existing run-package checker in the execution image."""
import hashlib
import importlib.util
import json
from pathlib import Path

root=Path('/workspace/work/issue47-model-run-verified')
checker=Path('/workspace/SEC_metrics/docs/evidence/issue47_history/model-egress/build_run_package.py')
spec=importlib.util.spec_from_file_location('package_checker',checker)
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
receipt=json.loads((root/package.RECEIPT).read_text())
for relative,expected in receipt['bound_files'].items():
    actual=hashlib.sha256((root/relative).read_bytes()).hexdigest()
    wanted=expected['sha256'] if isinstance(expected,dict) else expected
    assert actual==wanted.removeprefix('sha256:'),(relative,actual,wanted)
body=json.loads((root/package.APPROVAL_BODY).read_text())
held=package.reproduce_requests(root,body)
print(json.dumps({'bound_files_same':len(receipt['bound_files']), 'requests':held,
    'approval_sha256':hashlib.sha256((root/package.APPROVAL_BODY).read_bytes()).hexdigest(),
    'budget_root':body['budget_root'], 'calls':[0,0,0]},indent=1))
