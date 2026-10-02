"""Compare actual old/default/new A05 binding bytes and refuse wrong scope."""
import ast
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]

from vnext.canonical import canonical_json_bytes, content_hash
from vnext.normal_annual_input_v2 import exact_json_value
from vnext.normal_run_v3 import (A05_FORMULA_POLICY, _binding,
                                 prepare_case)
from vnext.requirements import load_requirement_snapshot

old_source = subprocess.check_output(['git', 'show',
    'HEAD:scripts/vnext/normal_run_v3.py'], cwd=ROOT, text=True)
old_tree = ast.parse(old_source)
old_fn, = [node for node in old_tree.body if isinstance(node, ast.FunctionDef)
           and node.name == '_binding']
old_scope = {'exact_json_value': exact_json_value}
exec(compile(ast.Module(body=[old_fn], type_ignores=[]), 'old_binding', 'exec'),
     old_scope)
source = Path(json.loads((ROOT/'docs/evidence/issue28_continuous/'
    'ordinary-jpm-a05-current-20261002/result.json').read_text())['processing_root'])
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    default = prepare_case(data_root=source, company_id='jpmorgan_chase',
                           metric_id='A05')
    explicit = prepare_case(data_root=source, company_id='jpmorgan_chase',
                            metric_id='A05', a05_formula=True)
    try:
        prepare_case(data_root=source, company_id='jpmorgan_chase',
                     metric_id='B01', a05_formula=True)
    except ValueError as error:
        assert str(error) == 'ORDINARY_A05_FORMULA_SCOPE_WRONG_METRIC'
    else:
        raise AssertionError('A05_FORMULA_WRONG_METRIC_ACCEPTED')
requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v13')
old = old_scope['_binding'](default, requirement)
current_default = _binding(default, requirement)
new = _binding(explicit, requirement)
assert canonical_json_bytes(value=old) == canonical_json_bytes(value=current_default)
assert old == current_default and 'presentation_policy' not in old
assert new['presentation_policy'] == explicit['presentation_policy'] == A05_FORMULA_POLICY
assert default['input_binding'] == explicit['input_binding']
assert default['expected_records'] == explicit['expected_records']
assert default['results']['A05']['result_id'] == explicit['results']['A05']['result_id']
assert content_hash(value=old) != content_hash(value=new)
body = {'record_type': 'ISSUE28_A05_FORMULA_DEFAULT_COMPATIBILITY',
    'old_source_head': subprocess.check_output(['git','rev-parse','HEAD'],
        cwd=ROOT,text=True).strip(),
    'old_binding_bytes_equal_new_default': True,
    'old_default_binding_hash': content_hash(value=old),
    'explicit_binding_hash': content_hash(value=new),
    'source_input_binding_equal': True,
    'expected_records_equal': True,
    'numeric_result_id_equal': default['results']['A05']['result_id'],
    'wrong_metric_refused_before_source': True,
    'new_real_calls': [0, 0, 0]}
(HERE/'binding-compat.json').write_text(json.dumps(body,ensure_ascii=False,
    indent=2)+'\n')
print(json.dumps({'status':'PASS','old_default_bytes_equal':True,
    'explicit_has_separate_identity':True,'same_numeric_result':True}))
