"""Persist final bound source/Run check after documentation-only rule-byte change."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = HERE / 'native-final.log'
EXIT = HERE / 'native-final.exit'
with LOG.open('w') as handle:
    for script in ('private_update.py', 'cold_read.py'):
        print('paramount ' + script + ' final', file=handle, flush=True)
        process = subprocess.run([sys.executable, str(HERE / script), 'paramount', 'final'],
                                 stdin=subprocess.DEVNULL, stdout=handle,
                                 stderr=subprocess.STDOUT, check=False)
        if process.returncode:
            EXIT.write_text(str(process.returncode) + '\n')
            sys.exit(process.returncode)
EXIT.write_text('0\n')
