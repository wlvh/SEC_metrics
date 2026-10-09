"""Use the previously configured local credential for one authorized group.

The business request and claim checks remain in the V14-bound operator.
No credential bytes enter the repository or execution logs.
"""
import os
import sys
from pathlib import Path

from tools.vnext_batch33 import main


def run():
    key_path = Path('/Users/lyuhongwang/.local/state/sec_metrics/private-credentials/deepseek-20260914.key')
    if not key_path.is_file():
        raise RuntimeError('PREVIOUSLY_CONFIGURED_KEY_FILE_MISSING')
    key = key_path.read_text().strip()
    if not key:
        raise RuntimeError('PREVIOUSLY_CONFIGURED_KEY_FILE_EMPTY')
    try:
        os.environ['DEEPSEEK_API_KEY'] = key
        return main(sys.argv[1:])
    finally:
        os.environ.pop('DEEPSEEK_API_KEY', None)


if __name__ == '__main__':
    raise SystemExit(run())
