"""Confirm Marriott under the final D01 execution-byte binding."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = HERE / 'native-marriott-final.log'
EXIT = HERE / 'native-marriott-final.exit'
with LOG.open('w') as handle:
    for script in ('private_update.py', 'cold_read.py'):
        print('marriott ' + script + ' final', file=handle, flush=True)
        result = subprocess.run([sys.executable, str(HERE / script), 'marriott', 'final'],
                                stdin=subprocess.DEVNULL, stdout=handle,
                                stderr=subprocess.STDOUT, check=False)
        if result.returncode:
            EXIT.write_text(str(result.returncode) + '\n')
            sys.exit(result.returncode)
EXIT.write_text('0\n')
