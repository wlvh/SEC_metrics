"""Bind the historical offline packet reader allowance to pushed old code."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'scripts'))
from vnext.d03_recorded_response_store import _HISTORICAL_V1_MODULE_SHA256

base = 'c009ec97b9ac229c8202d1bd001bd1ea366d0c7d'
relative = 'scripts/vnext/d03_recorded_response_store.py'
old = subprocess.check_output(['git', 'show', base + ':' + relative], cwd=ROOT)
packet_path = Path('/private/tmp/issue28-d03-recorded-packet-20260927-02/packet.json')
packet = json.loads(packet_path.read_text())
old_digest = hashlib.sha256(old).hexdigest()
assert old_digest == packet['module_sha256'] == _HISTORICAL_V1_MODULE_SHA256
assert packet['provider_execution_credit'] == 'RECORDED_TEST_ONLY'
assert packet['native_result_created'] is False
print(json.dumps({'old_pushed_code_sha': base,
    'historical_store_module_sha256': old_digest,
    'packet_id': packet['packet_id'],
    'packet_module_matches_pushed_code': True,
    'provider_execution_credit': packet['provider_execution_credit'],
    'native_result_created': False}, sort_keys=True))
