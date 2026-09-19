"""List every Requirement-id dispatch point, and refuse an unreachable branch.

A Requirement is not registered in one place. Its id is tested in several
independent `if/elif` chains — the engine registry, the Run authority, the
structured replay, the fiscal-label coordinates, the text contexts, the text
handlers — and each chain decides which module handles that generation. Reading
one chain says nothing about the others, which is why this branch's estimate of
the registration cost was wrong more than once.

The answer is not that static reading is useless. It is that the reading has to
be exhaustive and mechanical rather than sampled by hand. This tool does both
halves of that:

* it prints the map — which chain, at which line, sends which Requirement id to
  which handler — so the entries can be checked against the tests that cover
  them;
* it fails when one chain tests the same id twice, because the second branch can
  never run.

The second check is not hypothetical. ``0a811d2`` shipped exactly that: a stray
``elif requirement_id == "issue_47_v1"`` sitting after the branch that already
matched it, inside a patch to a frozen-authority file. A full end-to-end Run
passed with it in place, because a dead branch changes no behaviour — it is the
kind of defect only reading finds.

No Run, no network, no business call: this parses source.
"""
import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED = ("scripts/vnext/run_store.py", "scripts/vnext/records.py",
           "scripts/vnext/requirement_profile.py")


def _requirement_ids(test):
    """Ids compared against in one condition, however the comparison is spelled."""
    ids = set()
    for node in ast.walk(test):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and (node.value.startswith("issue_") or node.value.startswith("ai_first")):
            ids.add(node.value)
    return ids


def _mentions_requirement_id(test):
    for node in ast.walk(test):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and node.value in {"requirement_id"}:
            return True
    return isinstance(test, ast.Compare) and bool(_requirement_ids(test))


def _handler(body):
    """What the branch routes to: the import it performs, or its first call."""
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.ImportFrom):
            names = ", ".join(a.name for a in node.names)
            return "." * (node.level or 0) + (node.module or "") + ":" + names
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return node.func.id + "()"
    return "<inline>"


def _chains(*, repo_root, relative):
    """Every if/elif chain whose conditions test a Requirement id."""
    tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or not _mentions_requirement_id(node.test):
            continue
        # Only the head of a chain; an elif is the orelse of the one above it.
        if any(isinstance(parent, ast.If) and node in parent.orelse
               for parent in ast.walk(tree)):
            continue
        branches, current = [], node
        while True:
            branches.append({"line": current.test.lineno,
                             "requirement_ids": sorted(_requirement_ids(current.test)),
                             "handler": _handler(current.body)})
            if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If) \
                    and _mentions_requirement_id(current.orelse[0].test):
                current = current.orelse[0]
                continue
            if current.orelse:
                branches.append({"line": current.orelse[0].lineno,
                                 "requirement_ids": [], "handler": _handler(current.orelse)})
            break
        found.append({"file": relative, "line": node.test.lineno, "branches": branches})
    return found


def measure(*, repo_root):
    chains, unreachable = [], []
    for relative in SCANNED:
        if not (repo_root / relative).is_file():
            continue
        for chain in _chains(repo_root=repo_root, relative=relative):
            seen = {}
            for branch in chain["branches"]:
                for identifier in branch["requirement_ids"]:
                    if identifier in seen:
                        unreachable.append(
                            {"file": chain["file"], "requirement_id": identifier,
                             "first_line": seen[identifier], "dead_line": branch["line"],
                             "dead_handler": branch["handler"]})
                    else:
                        seen[identifier] = branch["line"]
            chains.append(chain)
    routed = sorted({i for c in chains for b in c["branches"] for i in b["requirement_ids"]})
    return {"record_type": "REQUIREMENT_DISPATCH_MAP", "schema_version": 1,
            "scanned_files": [f for f in SCANNED if (repo_root / f).is_file()],
            "dispatch_chains": len(chains), "requirement_ids_routed": routed,
            "unreachable_branches": unreachable,
            "every_branch_reachable": not unreachable, "chains": chains,
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_created": False, "production_authorized": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--output")
    parser.add_argument("--require-reachable", action="store_true",
                        help="Exit non-zero when a chain tests one id twice.")
    arguments = parser.parse_args(argv)
    report = measure(repo_root=Path(arguments.repo_root).resolve())
    text = json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if arguments.output:
        Path(arguments.output).write_text(text, encoding="utf-8")
    print(text)
    if arguments.require_reachable and not report["every_branch_reachable"]:
        raise SystemExit("unreachable dispatch branches: "
                         + ", ".join("%s:%d %s" % (u["file"], u["dead_line"],
                                                   u["requirement_id"])
                                     for u in report["unreachable_branches"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
