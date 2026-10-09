"""Actual installed CLI under extra checkout/program-write refusal, no mocks."""
import os
from pathlib import Path
import runpy
import sys

program = Path(sys.argv[1])
sys.path[:0] = [str(program/'scripts/vnext'), str(program/'scripts'), str(program)]
from company_worker_guard import install_worker_guards
install_worker_guards(program)
sys.argv = [str(program/'tools/vnext_company.py'), *sys.argv[2:]]
runpy.run_path(sys.argv[0], run_name='__main__')
