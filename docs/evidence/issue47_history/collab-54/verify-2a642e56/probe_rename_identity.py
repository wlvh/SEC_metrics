"""Probe only: copy #54's historical runtime and rename its Requirement identity.

Usage: python3 probe_rename_identity.py <installed runtime> <probe copy> <new id>

This is how the probe runtime of this check was made, so the result can be
reproduced; it is not #54's implementation and not a proposal for one. The
installed runtime names its Requirement ``issue_54_history_v1``; records.py
(validate_record) accepts only ids matching ``issue_[0-9]+_v[1-9][0-9]*``, so
run_store.create_run refuses every manifest. The copy renames the snapshot
directory and every literal use in the seven installed files that carry it,
rewrites the snapshot's own id and the authority bindings of those files (and
the validator binding), and commits the copy. Nothing else changes.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

OLD = "issue_54_history_v1"
FILES = ("scripts/vnext/run_store.py", "scripts/vnext/records.py", "scripts/vnext/historical_run.py",
         "scripts/vnext/company_compute.py", "scripts/vnext/company_requirement.py",
         "scripts/vnext/company_result_export.py", "scripts/vnext/company_runtime_install.py")


def main(installed, probe, new):
    installed, probe = Path(installed), Path(probe)
    if probe.exists():
        raise SystemExit("PROBE_TARGET_EXISTS")
    shutil.copytree(installed, probe, symlinks=True)
    subprocess.run(["git", "mv", "requirements/" + OLD, "requirements/" + new], cwd=probe, check=True)
    for relative in FILES:
        path = probe / relative
        path.write_text(path.read_text(encoding="utf-8").replace(OLD, new), encoding="utf-8")
    sys.path[:0] = [str(probe / "scripts")]
    from vnext.canonical import canonical_json_bytes
    manifest_path = probe / "requirements" / new / "baseline_manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    if manifest["requirement_id"] != OLD:
        raise SystemExit("UNEXPECTED_IDENTITY")
    manifest["requirement_id"] = new
    for relative in FILES:
        data = (probe / relative).read_bytes()
        manifest["execution_authority"]["files"][relative] = {
            "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    data = (probe / "scripts/vnext/company_requirement.py").read_bytes()
    manifest["validator"]["sha256"] = hashlib.sha256(data).hexdigest()
    manifest["validator"]["size"] = len(data)
    manifest_path.write_bytes(canonical_json_bytes(value=manifest))
    left = subprocess.run(["grep", "-rl", OLD, "scripts", "tools", "requirements"], cwd=probe,
                          capture_output=True, text=True).stdout.split()
    if left:
        raise SystemExit("OLD_IDENTITY_LEFT:" + ",".join(left))
    subprocess.run(["git", "add", "-A"], cwd=probe, check=True)
    subprocess.run(["git", "-c", "user.name=probe", "-c", "user.email=probe@local", "commit", "-qm",
                    "Probe: history runtime identity renamed to a pattern-conforming id"],
                   cwd=probe, check=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
