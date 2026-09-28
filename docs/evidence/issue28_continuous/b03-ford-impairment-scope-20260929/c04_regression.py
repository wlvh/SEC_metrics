"""Run the already defined two-source recorded proof on current B03 bytes."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
prior = ROOT/'docs/evidence/issue28_continuous/b03-c04-recorded-resume-20260929/probe.py'
spec = importlib.util.spec_from_file_location('issue28_b03_c04_recorded', prior)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.EVIDENCE = Path(__file__).resolve().parent
module.main()
