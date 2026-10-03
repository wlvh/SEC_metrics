"""Run the live egress cases once and record every checkout module the bound-code check finds unbound.

Run from the seal tree's root with the same environment verify.py gives a suite process.
The check itself is unchanged: a wrapper computes the full list the check would truncate,
records it, then calls the original.
"""
import json, os, sys, unittest
from pathlib import Path
sys.path.insert(0, os.getcwd())
import tests.vnext.test_historical_model_egress as T   # loads the runner first, as the suite does
import vnext.historical_model_calls as calls
import vnext.historical_model_egress as egress
from vnext.canonical import strict_json_loads
seen = {}
original = calls.loaded_code_holds
def wrapped(authority):
    root = Path(authority.root)
    bound = set(strict_json_loads(text=authority._files.decode("utf-8")))
    for module in list(sys.modules.values()):
        where = getattr(module, "__file__", None)
        if not where:
            continue
        real = Path(os.path.realpath(where))
        if root not in real.parents:
            continue
        relative = real.relative_to(root).as_posix()
        if relative.startswith("tests/") or relative in bound:
            continue
        seen.setdefault(relative, module.__name__)
    return original(authority)
calls.loaded_code_holds = wrapped
egress.loaded_code_holds = wrapped
names = sys.argv[1].split(",")
loader = unittest.TestLoader()
suite = unittest.TestSuite()
for cls_name in dir(T):
    cls = getattr(T, cls_name)
    if isinstance(cls, type) and issubclass(cls, unittest.TestCase):
        for name in loader.getTestCaseNames(cls):
            if name in names:
                suite.addTest(cls(name))
result = unittest.TextTestRunner(verbosity=1).run(suite)
print(json.dumps({"ran": result.testsRun, "errors": len(result.errors), "failures": len(result.failures),
                  "unbound": sorted(seen)}, indent=1))
