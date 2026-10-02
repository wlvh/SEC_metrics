"""Persist one affected final-bound native path and a separate cold read."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
with (HERE / 'native.log').open('w') as output:
    for script in ('private_update.py', 'cold_read.py'):
        print(script, file=output, flush=True)
        result = subprocess.run([sys.executable, str(HERE / script)],
                                stdin=subprocess.DEVNULL, stdout=output,
                                stderr=subprocess.STDOUT, check=False)
        if result.returncode:
            (HERE / 'native.exit').write_text(str(result.returncode) + '\n')
            sys.exit(result.returncode)
(HERE / 'native.exit').write_text('0\n')
