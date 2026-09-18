"""Compare a Requirement's execution authority against the code it imports.

An execution authority is meant to name the code a Run of that generation
executes, so that a Run records what produced it and a delivery can be built
from the list. This walks the actual import graph outward from the Python
modules the authority names and reports the difference.

Two answers, kept apart, because they mean different things:

* modules imported at module scope by authority-named code. Without these the
  authority's own modules cannot be imported at all, so anything assembled from
  the authority alone does not start. A non-empty list here is a defect.
* modules imported inside a function by authority-named code. Those sit on
  routes a given Run need not take, so their absence is information rather than
  a defect - but the authority itself does not draw the distinction, so this
  tool does.

No business call, no Run, no network: it reads the manifest and parses source.
"""
import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "scripts/vnext/"


def _module_path(name):
    return PACKAGE + name + ".py"


def _imports(*, repo_root, relative, module_scope_only):
    tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
    if module_scope_only:
        nodes = [inner for statement in tree.body
                 if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef,
                                               ast.ClassDef))
                 for inner in ast.walk(statement)]
    else:
        nodes = list(ast.walk(tree))
    names = set()
    for node in nodes:
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            names.add(node.module.split(".")[0]) if node.module else names.update(
                alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module == "vnext":
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module \
                and node.module.startswith("vnext."):
            names.add(node.module.split(".")[1])
        elif isinstance(node, ast.Import):
            names.update(alias.name.split(".")[1] for alias in node.names
                         if alias.name.startswith("vnext."))
    return {name for name in names if (repo_root / _module_path(name)).is_file()}


def _closure(*, repo_root, seeds, module_scope_only):
    seen, queue = set(seeds), list(seeds)
    while queue:
        for name in _imports(repo_root=repo_root, relative=queue.pop(),
                             module_scope_only=module_scope_only):
            path = _module_path(name)
            if path not in seen:
                seen.add(path)
                queue.append(path)
    return seen


def measure(*, repo_root, requirement_id):
    manifest = json.loads(
        (repo_root / "requirements" / requirement_id / "baseline_manifest.json").read_text())
    authority = set(manifest["execution_authority"]["files"])
    authority.update(manifest.get("new_rule_files", {}))
    authority.add(manifest["validator"]["path"])
    authority.update(manifest["validator"].get("dependencies", []))
    seeds = sorted(path for path in authority
                   if path.startswith(PACKAGE) and path.endswith(".py"))
    module_scope = _closure(repo_root=repo_root, seeds=seeds, module_scope_only=True)
    reachable = _closure(repo_root=repo_root, seeds=seeds, module_scope_only=False)
    required = sorted(module_scope - authority)
    return {"record_type": "EXECUTION_AUTHORITY_IMPORT_CLOSURE", "schema_version": 1,
            "requirement_id": manifest["requirement_id"],
            "authority_files": len(manifest["execution_authority"]["files"]),
            "authority_python_modules": len(seeds),
            "module_scope_closure": len(module_scope),
            "reachable_closure": len(reachable),
            "required_to_import_but_not_named": required,
            "reachable_on_some_path_but_not_named": sorted(
                reachable - authority - set(required)),
            "authority_is_import_complete": not required,
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_created": False, "production_authorized": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirement-id", default="issue_47_v1")
    parser.add_argument("--output")
    parser.add_argument("--require-complete", action="store_true",
                        help="Exit non-zero when a module-scope import is unnamed.")
    arguments = parser.parse_args(argv)
    report = measure(repo_root=ROOT, requirement_id=arguments.requirement_id)
    text = json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if arguments.output:
        Path(arguments.output).write_text(text, encoding="utf-8")
    print(text)
    if arguments.require_complete and not report["authority_is_import_complete"]:
        raise SystemExit("execution authority does not name: "
                         + ", ".join(report["required_to_import_but_not_named"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
