"""Bounded persisted no-network D01 private updates and independent reads."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = HERE / 'native-run.log'
EXIT = HERE / 'native-run.exit'
with LOG.open('w') as handle:
    for company in ('paramount', 'marriott'):
        for script in ('private_update.py', 'cold_read.py'):
            print(f'{company} {script}', file=handle, flush=True)
            process = subprocess.run([sys.executable, str(HERE / script), company],
                                     stdin=subprocess.DEVNULL, stdout=handle,
                                     stderr=subprocess.STDOUT, check=False)
            if process.returncode:
                EXIT.write_text(str(process.returncode) + '\n')
                sys.exit(process.returncode)
EXIT.write_text('0\n')
