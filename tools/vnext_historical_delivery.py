"""Assemble a delivery that carries its own runtime, and replay a Run from it.

The question is narrow, and this branch previously answered it wrongly: can a
frozen historical Run be replayed without the development checkout? The earlier
claim was that an existing invariant forbids it. It does not. ``_external``
refuses the data root *overlapping* the code root - the same tree, or the data
root inside the code root - and a delivery whose ``runtime/`` and ``data/`` are
siblings is neither. So the delivery is built and run rather than argued about.

The runtime is assembled from the Requirement's own execution authority plus
every ``requirements/`` snapshot, because loading one walks its parent chain.
Anything else the replay turns out to need is listed in the report under
``extra_beyond_authority`` rather than folded in silently: those are files a Run
executes against that its authority does not name, and that gap is a finding,
not a packaging detail.

The replay runs in a separate interpreter, in isolated mode, from a working
directory outside both the delivery and any checkout, with no network. It then
reports where every loaded ``vnext`` module came from, so "does not depend on
the development checkout" is checked rather than asserted.

This produces no business call and creates no Run: it replays one that exists.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Read by requirement_profile_v4 through v7 at a runtime-root-relative path
# while a Requirement is loaded, and not named by any execution authority.
POLICY_INPUTS_NOT_IN_ANY_AUTHORITY = (
    "docs/evidence/issue_28_r4_label_policy.json",
    "docs/evidence/issue_28_annual_candidate_policy.json",
    "docs/evidence/issue_28_annual_runtime_policy.json",
    "docs/evidence/issue_28_annual_repair_policy.json",
)

REPLAY = '''
import json, os, socket, sys
from pathlib import Path
from unittest.mock import patch

DELIVERY = Path(%r)
sys.path = [str(DELIVERY / "runtime" / "scripts")] + [
    entry for entry in sys.path
    if entry.startswith(sys.prefix) or "python3" in entry or entry.endswith(".zip")]
with patch.object(socket.socket, "connect", side_effect=AssertionError("no network")), \\
     patch.object(socket, "getaddrinfo", side_effect=AssertionError("no dns")):
    from vnext.run_store import load_frozen_run
    from vnext.historical_projection import render_historical_run
    manifest, records, _ = load_frozen_run(run_dir=DELIVERY / "run",
                                           repo_root=DELIVERY / "data")
    result = [r for r in records if r["record_type"] == "METRIC_RESULT"][0]
    rendered = render_historical_run(data_root=DELIVERY / "data",
                                     run_dir=DELIVERY / "run", frozen=True)

runtime = (DELIVERY / "runtime").resolve()
loaded = {name: getattr(module, "__file__", None) for name, module in sys.modules.items()
          if name.split(".")[0] == "vnext"}
print(json.dumps({
    "run_id": manifest["run_id"], "status": manifest["status"],
    "requirement_id": manifest["requirement_id"],
    "target_period": manifest["target_period"],
    "value": result["value"], "quality": result["quality"],
    "row_value": rendered["row"]["value"], "row_fiscal_year": rendered["row"]["fiscal_year"],
    "row_accession": rendered["row"]["accession"],
    "row_hash": rendered["receipt"]["row_hash"],
    "evidence_count": len(rendered["evidence"]),
    "vnext_modules_loaded": len(loaded),
    "vnext_modules_outside_the_delivery": sorted(
        name for name, path in loaded.items()
        if path and not Path(path).resolve().is_relative_to(runtime)),
    "sys_path_entries_outside_the_delivery": [
        entry for entry in sys.path
        if entry and not entry.startswith((str(DELIVERY), sys.prefix))
        and "python3" not in entry and not entry.endswith(".zip")],
    "working_directory": os.getcwd(),
    "calls": {"provider": 0, "paid": 0, "sec": 0},
}))
'''


def _authority_paths(*, runtime_root, requirement_id):
    manifest = json.loads((runtime_root / "requirements" / requirement_id
                           / "baseline_manifest.json").read_text(encoding="utf-8"))
    paths = set(manifest["execution_authority"]["files"])
    paths.update(manifest.get("new_rule_files", {}))
    paths.add(manifest["validator"]["path"])
    paths.update(manifest["validator"].get("dependencies", []))
    paths.update(str(path.relative_to(runtime_root))
                 for path in (runtime_root / "requirements").rglob("*") if path.is_file())
    return sorted(paths)


def assemble(*, runtime_root, data_root, run_dir, delivery, requirement_id):
    if delivery.exists():
        shutil.rmtree(delivery)
    delivery.mkdir(parents=True)
    authority = _authority_paths(runtime_root=runtime_root, requirement_id=requirement_id)
    copied = []
    for relative in list(authority) + list(POLICY_INPUTS_NOT_IN_ANY_AUTHORITY):
        source = runtime_root / relative
        if not source.is_file():
            continue
        target = delivery / "runtime" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(relative)
    shutil.copytree(data_root, delivery / "data")
    shutil.copytree(run_dir, delivery / "run")
    sizes = {}
    for part in ("runtime", "data", "run"):
        sizes[part] = sum(f.stat().st_size for f in (delivery / part).rglob("*") if f.is_file())
    return {"authority_paths": len(authority), "runtime_files": len(copied),
            "extra_beyond_authority": list(POLICY_INPUTS_NOT_IN_ANY_AUTHORITY),
            "byte_sizes": sizes, "total_bytes": sum(sizes.values())}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True,
                        help="Tree the runtime bytes come from; needs the registration patch.")
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--delivery", required=True)
    parser.add_argument("--requirement-id", default="issue_47_v1")
    parser.add_argument("--output")
    arguments = parser.parse_args(argv)

    started = time.time()
    delivery = Path(arguments.delivery).resolve()
    assembled = assemble(runtime_root=Path(arguments.runtime_root).resolve(),
                         data_root=Path(arguments.data_root).resolve(),
                         run_dir=Path(arguments.run_dir).resolve(),
                         delivery=delivery, requirement_id=arguments.requirement_id)
    completed = subprocess.run([sys.executable, "-I", "-c", REPLAY % str(delivery)],
                               capture_output=True, text=True, cwd="/",
                               env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})
    report = {"record_type": "HISTORICAL_PORTABLE_DELIVERY_REPLAY", "schema_version": 1,
              "requirement_id": arguments.requirement_id, **assembled,
              "interpreter_flags": ["-I"], "working_directory": "/",
              "environment_passed": ["PATH", "PYTHONDONTWRITEBYTECODE"],
              "returncode": completed.returncode,
              "duration_seconds": round(time.time() - started, 1),
              "calls": {"provider": 0, "paid": 0, "sec": 0},
              "native_run_created": False, "production_authorized": False}
    if completed.returncode == 0:
        report["replay"] = json.loads(completed.stdout.strip().splitlines()[-1])
        replay = report["replay"]
        report["depends_on_no_checkout"] = (
            not replay["vnext_modules_outside_the_delivery"]
            and not replay["sys_path_entries_outside_the_delivery"])
    else:
        report["stderr_tail"] = completed.stderr[-4000:]
        report["depends_on_no_checkout"] = False
    text = json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if arguments.output:
        Path(arguments.output).write_text(text, encoding="utf-8")
    print(text)
    return 0 if completed.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
