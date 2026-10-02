"""Persist one bounded current-tree fast-suite run without console flooding."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
with (HERE / 'fast-suite.json').open('w') as output, (HERE / 'fast-suite.stderr').open('w') as errors:
    result = subprocess.run([sys.executable, str(ROOT / 'tools/run_fast_tests_v2.py'),
                             '--jobs', '4'], cwd=ROOT, stdin=subprocess.DEVNULL,
                            stdout=output, stderr=errors, check=False)
(HERE / 'fast-suite.exit').write_text(str(result.returncode) + '\n')
