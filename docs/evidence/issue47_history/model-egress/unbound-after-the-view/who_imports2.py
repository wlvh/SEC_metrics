"""Full stack of the first load of each named module during the D04 imports (importlib included)."""
import sys, traceback, importlib
from pathlib import Path
repo = Path(sys.argv[1]).resolve()
targets = {"vnext." + n for n in sys.argv[2].split(",")}
sys.path.insert(0, str(repo / "scripts"))
seen = {}
class Finder:
    def find_spec(self, name, path=None, target=None):
        if name in targets and name not in seen:
            seen[name] = [f"{Path(f.filename).name}:{f.lineno} {f.name}" for f in traceback.extract_stack()[:-1]
                          if "importlib" not in f.filename and "<frozen" not in f.filename][-8:]
        return None
sys.meta_path.insert(0, Finder())
import vnext.historical_semantic_results  # noqa: F401
for n in sorted(targets):
    print(n, "LOADED" if n in sys.modules else "not loaded")
    for line in seen.get(n, []): print("    ", line)
