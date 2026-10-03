"""Every module-level value of the four modules, docstrings aside, as comparable text.

Usage: python3 fingerprint.py <repo> <out.json>
"""
import importlib, json, re, sys, types
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo / "scripts"))
MODULES = ["vnext.historical_board_composition", "vnext.historical_capacity_results",
           "vnext.historical_event_items", "vnext.historical_lodging_results"]


def shape(value, depth=0):
    if isinstance(value, re.Pattern):
        return {"re": value.pattern, "flags": value.flags}
    if isinstance(value, (frozenset, set)):
        return {"set": sorted(shape(v, depth + 1) if not isinstance(v, str) else v for v in value)}
    if isinstance(value, (tuple, list)):
        return [shape(v, depth + 1) for v in value]
    if isinstance(value, dict):
        return {str(k): shape(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (types.FunctionType, type)):
        code = getattr(value, "__code__", None)
        return {"callable": value.__qualname__,
                "code": (code.co_code.hex(), [c for c in code.co_consts if not isinstance(c, types.CodeType)
                                               and not (isinstance(c, str) and c == value.__doc__)])
                if code else None}
    return {"other": type(value).__name__}


out = {}
for name in MODULES:
    module = importlib.import_module(name)
    values = {}
    for key, value in sorted(vars(module).items()):
        if key.startswith("__") or isinstance(value, types.ModuleType):
            continue
        if getattr(value, "__module__", name) not in (name, None) and callable(value):
            continue
        try:
            values[key] = shape(value)
        except Exception as error:  # noqa: BLE001 - a fingerprint, not a check
            values[key] = {"unshaped": repr(error)}
    out[name] = values
Path(sys.argv[2]).write_text(json.dumps(out, indent=0, sort_keys=True, default=repr), encoding="utf-8")
print("written", sys.argv[2], {k: len(v) for k, v in out.items()})
