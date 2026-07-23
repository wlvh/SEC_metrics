"""Bind terminal validation to the source inputs and acceptance artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from git_workspace import git_checkout_metadata_error, sanitized_git_environment

SCHEMA = 1
PROVENANCE_RELATIVE_PATH = Path("outputs/validation_snapshot_provenance.json")
MANIFEST = Path("outputs/validation_run_manifest.json")
REPORT = Path("REPORT_十公司财务指标.md")
README = Path("README_RUN.md")
LIGHT_MARKER = Path("LIGHT_REVIEW_PACKAGE.marker")
SOURCE_DIRS = ("scripts", "tools", "config", "tests")
SOURCE_FILES = (
    "capability_contract.json",
    "02_指标定义_SEC_10公司单年指标.md",
    "AGENTS.md",
    "SOP.md",
    "TESTING.md",
    "architecture.md",
    "interact.md",
    "docs/business_user_guide.md",
    "docs/validation_snapshot_provenance.md",
)
SOURCE_PATHS = SOURCE_DIRS + SOURCE_FILES
FULL_CORE = (
    MANIFEST.as_posix(),
    REPORT.as_posix(),
    README.as_posix(),
    "outputs/golden_results.csv",
    "outputs/metrics_matrix.csv",
    "outputs/metric_evidence.csv",
    "outputs/coverage_matrix.csv",
    "outputs/events.csv",
    "evidence/requests_log.csv",
    "evidence/requests_log_manifest.json",
)
LIGHT_CORE = FULL_CORE[:-2]
REQUIRED = {
    "schema_version",
    "run_id",
    "manifest_mode",
    "manifest_result",
    "manifest_source_commit",
    "source_checkout_status",
    "source_commit",
    "source_input_tree_sha256",
    "source_file_count",
    "source_dirty_paths",
    "artifact_digests",
    "generated_at_utc",
}
README_START = "<!-- validation-reading-routes:start -->"
README_END = "<!-- validation-reading-routes:end -->"
README_BLOCK = """<!-- validation-reading-routes:start -->
## 只读取现有结果

1. 先读 `outputs/validation_run_manifest.json`；非 terminal success 时停止。
2. 运行 `python3 tools/check_validation_snapshot.py`；source tree 或 artifact digest 失配时停止。
3. checker 通过后再读报告、metrics 与 evidence。

## 执行新批次

1. 在 clean source checkout 中按顺序运行 `00`–`11`；stage 11 exit 0 只表示报告完成。
2. 单独运行 `python3 scripts/12_validate_repair.py`。
3. stage 12 exit 0、terminal manifest 成功且 snapshot checker 通过，才构成完整批次成功。

## Validation snapshot provenance

stage 12 绑定 source-input tree 及 manifest/report/README/metrics/evidence/coverage/Golden/request/validation artifacts 的 SHA-256 与 size。commit SHA 改变时，仅完整 source tree 等价可作为 warning 接受；light provenance 不能升级为 full validation。
<!-- validation-reading-routes:end -->"""
REPORT_START = "<!-- validation-snapshot-provenance:start -->"
REPORT_END = "<!-- validation-snapshot-provenance:end -->"
REPORT_BLOCK = """<!-- validation-snapshot-provenance:start -->
## Validation snapshot provenance

- 报告存在或显示 GO，不单独证明当前 checkout 可验收。
- 必须同时满足 terminal manifest 成功，且 `python3 tools/check_validation_snapshot.py` 通过。
- checker 验证 source-input tree 和关键 artifact SHA-256/size。
<!-- validation-snapshot-provenance:end -->"""


class ValidationProvenanceError(RuntimeError):
    """Raised when validation provenance cannot be trusted or published."""


@dataclass(frozen=True)
class SourceSnapshot:
    """Content identity of the source inputs used by terminal validation."""

    checkout_status: str
    source_commit: Optional[str]
    tree_sha256: str
    file_count: int
    dirty_paths: Tuple[str, ...]


@dataclass(frozen=True)
class VerificationResult:
    """Independent validation-snapshot verification result."""

    errors: Tuple[str, ...]
    warnings: Tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Return true only when no verification error was found."""
        return not self.errors


def _utc() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _is_utc(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0)


def _repo(workdir: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValidationProvenanceError(
            "Snapshot path escapes repository: {}".format(relative)
        )
    candidate, current = workdir / path, workdir
    for part in path.parts:
        current /= part
        if os.path.lexists(current) and current.is_symlink():
            raise ValidationProvenanceError(
                "Snapshot path contains a symlink component: {}".format(current)
            )
    try:
        candidate.resolve(strict=False).relative_to(workdir.resolve())
    except ValueError as error:
        raise ValidationProvenanceError(
            "Snapshot path resolves outside repository: {}".format(relative)
        ) from error
    return candidate


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValidationProvenanceError(
            "Snapshot input must be a non-symlink regular file: {}".format(path)
        )
    return path.read_bytes()


def _write(workdir: Path, path: Path, content: bytes) -> None:
    relative = path.relative_to(workdir).as_posix()
    path = _repo(workdir, relative)
    if path.exists() and not path.is_file():
        raise ValidationProvenanceError(
            "Snapshot output is not a regular file: {}".format(path)
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".{}.{}.tmp".format(path.name, uuid.uuid4().hex))
    try:
        with temporary.open("xb") as file_obj:
            file_obj.write(content)
            file_obj.flush()
            os.fsync(file_obj.fileno())
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
        raise ValidationProvenanceError(
            "Snapshot atomic-write postcondition failed: {}".format(path)
        )


def _write_json(
    workdir: Path,
    path: Path,
    payload: Mapping[str, object],
) -> None:
    content = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
    _write(workdir, path, content)


def _git(workdir: Path, args: Sequence[str]) -> bytes:
    result = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(workdir), *args],
        check=False,
        capture_output=True,
        env=sanitized_git_environment(),
    )
    if result.returncode:
        raise ValidationProvenanceError(
            "Git command failed ({}): {}".format(
                " ".join(args),
                result.stderr.decode("utf-8", errors="replace").strip(),
            )
        )
    return result.stdout


def _nul(content: bytes) -> List[str]:
    return [item.decode("utf-8") for item in content.split(b"\0") if item]


def _git_paths(workdir: Path) -> List[str]:
    paths = sorted(
        set(_nul(_git(workdir, ["ls-files", "-z", "--", *SOURCE_PATHS])))
    )
    if not paths:
        raise ValidationProvenanceError("Git source-input closure is empty")
    return paths


def _dirty(workdir: Path) -> List[str]:
    commands = (
        ["diff", "--name-only", "-z", "--", *SOURCE_PATHS],
        ["diff", "--cached", "--name-only", "-z", "--", *SOURCE_PATHS],
        ["ls-files", "--others", "-z", "--", *SOURCE_PATHS],
    )
    paths = set()
    for command in commands:
        paths.update(_nul(_git(workdir, command)))
    return sorted(
        path
        for path in paths
        if "__pycache__" not in Path(path).parts
        and Path(path).suffix not in {".pyc", ".pyo"}
    )


def _filesystem_paths(workdir: Path) -> List[str]:
    paths: List[str] = []
    for directory_name in SOURCE_DIRS:
        directory = workdir / directory_name
        if not directory.exists():
            continue
        if directory.is_symlink() or not directory.is_dir():
            raise ValidationProvenanceError(
                "Source directory is not a real directory: {}".format(directory)
            )
        for path in directory.rglob("*"):
            if path.is_symlink():
                raise ValidationProvenanceError(
                    "Source input is a symlink: {}".format(path)
                )
            if path.is_dir():
                continue
            relative = path.relative_to(workdir)
            if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            if not path.is_file():
                raise ValidationProvenanceError(
                    "Source input is not a regular file: {}".format(path)
                )
            paths.append(relative.as_posix())
    # A no-Git light package cannot redefine the source closure by omitting an
    # explicit governance or contract file. Every declared singleton is required.
    for relative in SOURCE_FILES:
        path = _repo(workdir, relative)
        _read(path)
        paths.append(relative)
    paths = sorted(set(paths))
    if not paths:
        raise ValidationProvenanceError(
            "Filesystem source-input closure is empty"
        )
    return paths


def _tree(workdir: Path, paths: Iterable[str]) -> Tuple[str, int]:
    digest, count = hashlib.sha256(), 0
    for relative in sorted(paths):
        content = _read(_repo(workdir, relative))
        digest.update(
            "{}\0{}\0{}\n".format(
                relative,
                len(content),
                hashlib.sha256(content).hexdigest(),
            ).encode("utf-8")
        )
        count += 1
    return digest.hexdigest(), count


def capture_source_snapshot(*, workdir: Path) -> SourceSnapshot:
    metadata_error = git_checkout_metadata_error(repo_root=workdir)
    if metadata_error:
        if not _repo(workdir, LIGHT_MARKER.as_posix()).is_file():
            raise ValidationProvenanceError(
                "Git source provenance unavailable outside an explicit light "
                "package: " + metadata_error
            )
        tree, count = _tree(workdir, _filesystem_paths(workdir))
        return SourceSnapshot("LIGHT_PACKAGE_NO_GIT", None, tree, count, ())
    commit = _git(workdir, ["rev-parse", "HEAD"]).decode("utf-8").strip()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValidationProvenanceError(
            "Git HEAD is not a full commit SHA: {}".format(commit)
        )
    dirty = _dirty(workdir)
    if dirty:
        raise ValidationProvenanceError(
            "Source-input files are dirty: {}".format(",".join(dirty))
        )
    tree, count = _tree(workdir, _git_paths(workdir))
    return SourceSnapshot("GIT_CLEAN", commit, tree, count, ())


def _json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(_read(path).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationProvenanceError(
            "Invalid UTF-8 JSON object: {}".format(path)
        ) from error
    if not isinstance(payload, dict):
        raise ValidationProvenanceError(
            "JSON root must be an object: {}".format(path)
        )
    return payload


def _manifest(workdir: Path) -> Dict[str, object]:
    manifest = _json(_repo(workdir, MANIFEST.as_posix()))
    required = {
        "run_id",
        "source_commit",
        "started_at_utc",
        "mode",
        "refreshed_artifacts",
        "not_refreshed_artifacts",
        "result",
    }
    if set(manifest) != required:
        raise ValidationProvenanceError(
            "Validation manifest keys do not match the required schema"
        )
    for key in ("run_id", "source_commit", "started_at_utc"):
        if not isinstance(manifest[key], str) or not manifest[key].strip():
            raise ValidationProvenanceError(
                "Validation manifest {} must be a non-empty string".format(key)
            )
    if not _is_utc(str(manifest["started_at_utc"])):
        raise ValidationProvenanceError(
            "Validation manifest started_at_utc must be UTC ISO-8601"
        )
    if manifest["mode"] not in {
        "FULL_VALIDATION",
        "LIGHT_REVIEW_MODE",
        "WORKSPACE_INCOMPLETE",
    }:
        raise ValidationProvenanceError(
            "Validation manifest mode is invalid: {}".format(manifest["mode"])
        )
    if manifest["result"] not in {
        "IN_PROGRESS",
        "PASSED",
        "PASSED_WITH_CAVEATS",
        "FAILED",
    }:
        raise ValidationProvenanceError(
            "Validation manifest result is invalid: {}".format(
                manifest["result"]
            )
        )
    refreshed = manifest["refreshed_artifacts"]
    stale = manifest["not_refreshed_artifacts"]
    if (
        not isinstance(refreshed, list)
        or not isinstance(stale, list)
        or any(not isinstance(item, str) for item in refreshed + stale)
    ):
        raise ValidationProvenanceError(
            "Validation manifest artifact lists must be string arrays"
        )
    if (
        len(refreshed) != len(set(refreshed))
        or len(stale) != len(set(stale))
        or set(refreshed) & set(stale)
    ):
        raise ValidationProvenanceError(
            "Validation manifest artifact lists are not unique/disjoint"
        )
    return manifest


def _commit_base(value: str) -> Optional[str]:
    if re.fullmatch(r"[0-9a-f]{40}", value):
        return value
    for suffix in ("+dirty", "+status-unknown"):
        if value.endswith(suffix) and re.fullmatch(
            r"[0-9a-f]{40}", value[: -len(suffix)]
        ):
            return value[: -len(suffix)]
    return None


def _manifest_matches(value: str, snapshot: SourceSnapshot) -> bool:
    return (
        value == "UNAVAILABLE_NON_GIT_WORKSPACE"
        if snapshot.source_commit is None
        else _commit_base(value) == snapshot.source_commit
    )


def _artifact_paths(manifest: Mapping[str, object]) -> List[str]:
    refreshed = manifest["refreshed_artifacts"]
    if not isinstance(refreshed, list) or any(
        not isinstance(item, str) for item in refreshed
    ):
        raise ValidationProvenanceError(
            "Validation manifest refreshed_artifacts must be a string array"
        )
    invalid = [
        item
        for item in refreshed
        if not item
        or Path(item).name != item
        or "/" in item
        or "\\" in item
    ]
    if invalid:
        raise ValidationProvenanceError(
            "Validation manifest refreshed artifact names are not basenames: "
            + ",".join(invalid)
        )
    core = FULL_CORE if manifest["mode"] == "FULL_VALIDATION" else LIGHT_CORE
    return sorted(set(core) | {"outputs/{}".format(item) for item in refreshed})


def _digests(
    workdir: Path,
    paths: Iterable[str],
) -> Dict[str, Dict[str, object]]:
    result: Dict[str, Dict[str, object]] = {}
    for relative in sorted(set(paths)):
        content = _read(_repo(workdir, relative))
        result[relative] = {
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }
    return result


def invalidate_validation_snapshot(*, workdir: Path) -> None:
    path = _repo(workdir, PROVENANCE_RELATIVE_PATH.as_posix())
    if not path.exists():
        return
    if not path.is_file():
        raise ValidationProvenanceError(
            "Existing validation provenance is not a regular file: {}".format(
                path
            )
        )
    path.unlink()


def publish_validation_snapshot(
    *,
    workdir: Path,
    source_snapshot: SourceSnapshot,
) -> Dict[str, object]:
    manifest = _manifest(workdir)
    expected = {
        "FULL_VALIDATION": "PASSED",
        "LIGHT_REVIEW_MODE": "PASSED_WITH_CAVEATS",
    }
    mode, result = str(manifest["mode"]), str(manifest["result"])
    if mode not in expected or result != expected[mode]:
        raise ValidationProvenanceError(
            "Only a successful full/light terminal manifest can be attested: "
            "mode={} result={}".format(mode, result)
        )
    if not _manifest_matches(str(manifest["source_commit"]), source_snapshot):
        raise ValidationProvenanceError(
            "Validation manifest source_commit does not identify the captured "
            "source commit"
        )
    current = capture_source_snapshot(workdir=workdir)
    if current != source_snapshot:
        raise ValidationProvenanceError(
            "Source input or Git HEAD changed during terminal validation"
        )
    payload: Dict[str, object] = {
        "schema_version": SCHEMA,
        "run_id": str(manifest["run_id"]),
        "manifest_mode": mode,
        "manifest_result": result,
        "manifest_source_commit": str(manifest["source_commit"]),
        "source_checkout_status": source_snapshot.checkout_status,
        "source_commit": source_snapshot.source_commit,
        "source_input_tree_sha256": source_snapshot.tree_sha256,
        "source_file_count": source_snapshot.file_count,
        "source_dirty_paths": list(source_snapshot.dirty_paths),
        "artifact_digests": _digests(workdir, _artifact_paths(manifest)),
        "generated_at_utc": _utc(),
    }
    path = workdir / PROVENANCE_RELATIVE_PATH
    _write_json(workdir, path, payload)
    checked = verify_validation_snapshot(
        workdir=workdir,
        allow_equivalent_source_tree=False,
    )
    if not checked.ok:
        raise ValidationProvenanceError(
            "Published validation provenance failed verification: "
            + "; ".join(checked.errors)
        )
    return payload


def _schema_errors(payload: Mapping[str, object]) -> List[str]:
    errors: List[str] = []
    if set(payload) != REQUIRED:
        missing = sorted(REQUIRED - set(payload))
        extra = sorted(set(payload) - REQUIRED)
        if missing:
            errors.append("provenance missing keys: {}".format(",".join(missing)))
        if extra:
            errors.append(
                "provenance unexpected keys: {}".format(",".join(extra))
            )
        return errors
    if payload["schema_version"] != SCHEMA:
        errors.append("unsupported provenance schema_version")
    expected = {
        "FULL_VALIDATION": "PASSED",
        "LIGHT_REVIEW_MODE": "PASSED_WITH_CAVEATS",
    }
    if payload["manifest_mode"] not in expected:
        errors.append("provenance manifest_mode is not attestable")
    elif payload["manifest_result"] != expected[payload["manifest_mode"]]:
        errors.append(
            "provenance manifest_result is not a successful terminal state"
        )
    if payload["source_checkout_status"] not in {
        "GIT_CLEAN",
        "LIGHT_PACKAGE_NO_GIT",
    }:
        errors.append("unsupported source_checkout_status")
    for key in (
        "run_id",
        "manifest_mode",
        "manifest_result",
        "manifest_source_commit",
        "source_checkout_status",
        "source_input_tree_sha256",
        "generated_at_utc",
    ):
        if not isinstance(payload[key], str) or not payload[key].strip():
            errors.append("{} must be a non-empty string".format(key))
    manifest_commit = str(payload["manifest_source_commit"])
    if (
        manifest_commit != "UNAVAILABLE_NON_GIT_WORKSPACE"
        and _commit_base(manifest_commit) is None
    ):
        errors.append("manifest_source_commit has an unsupported format")
    source_commit = payload["source_commit"]
    if source_commit is not None and (
        not isinstance(source_commit, str)
        or re.fullmatch(r"[0-9a-f]{40}", source_commit) is None
    ):
        errors.append("source_commit must be null or a full commit SHA")
    if not isinstance(payload["source_input_tree_sha256"], str) or re.fullmatch(
        r"[0-9a-f]{64}", str(payload["source_input_tree_sha256"])
    ) is None:
        errors.append("source_input_tree_sha256 must be lowercase SHA-256")
    if (
        type(payload["source_file_count"]) is not int
        or payload["source_file_count"] < 1
    ):
        errors.append("source_file_count must be a positive integer")
    dirty = payload["source_dirty_paths"]
    if not isinstance(dirty, list) or any(
        not isinstance(item, str) for item in dirty
    ):
        errors.append("source_dirty_paths must be a string array")
    elif dirty:
        errors.append("successful provenance cannot contain dirty source paths")
    if payload["source_checkout_status"] == "GIT_CLEAN" and source_commit is None:
        errors.append("GIT_CLEAN provenance requires source_commit")
    if (
        payload["source_checkout_status"] == "LIGHT_PACKAGE_NO_GIT"
        and source_commit is not None
    ):
        errors.append("LIGHT_PACKAGE_NO_GIT provenance requires null source_commit")
    if not isinstance(payload["artifact_digests"], dict):
        errors.append("artifact_digests must be an object")
    if not _is_utc(str(payload["generated_at_utc"])):
        errors.append("generated_at_utc must be an ISO 8601 UTC timestamp")
    return errors


def verify_validation_snapshot(
    *,
    workdir: Path,
    allow_equivalent_source_tree: bool = True,
) -> VerificationResult:
    errors: List[str] = []
    warnings: List[str] = []
    try:
        path = _repo(workdir, PROVENANCE_RELATIVE_PATH.as_posix())
    except ValidationProvenanceError as error:
        return VerificationResult((str(error),), ())
    if not path.exists():
        return VerificationResult(
            ("validation snapshot provenance is missing",),
            (),
        )
    try:
        payload, manifest = _json(path), _manifest(workdir)
    except ValidationProvenanceError as error:
        return VerificationResult((str(error),), ())
    errors.extend(_schema_errors(payload))
    if errors:
        return VerificationResult(tuple(errors), tuple(warnings))
    for provenance_key, manifest_key in (
        ("run_id", "run_id"),
        ("manifest_mode", "mode"),
        ("manifest_result", "result"),
        ("manifest_source_commit", "source_commit"),
    ):
        if payload[provenance_key] != manifest[manifest_key]:
            errors.append(
                "{} does not match validation manifest".format(provenance_key)
            )
    published = SourceSnapshot(
        str(payload["source_checkout_status"]),
        (
            str(payload["source_commit"])
            if payload["source_commit"] is not None
            else None
        ),
        str(payload["source_input_tree_sha256"]),
        int(payload["source_file_count"]),
        tuple(str(item) for item in payload["source_dirty_paths"]),
    )
    if not _manifest_matches(str(manifest["source_commit"]), published):
        errors.append(
            "validation manifest source_commit does not identify the published "
            "source commit"
        )
    try:
        current = capture_source_snapshot(workdir=workdir)
    except ValidationProvenanceError as error:
        errors.append(str(error))
        current = None
    if current is not None:
        if published.checkout_status != current.checkout_status:
            errors.append("source checkout status changed")
        if published.tree_sha256 != current.tree_sha256:
            errors.append("source-input tree digest mismatch")
        if published.file_count != current.file_count:
            errors.append("source-input file count mismatch")
        if published.source_commit != current.source_commit:
            if (
                allow_equivalent_source_tree
                and published.tree_sha256 == current.tree_sha256
            ):
                warnings.append(
                    "Git commit differs but the complete source-input tree is "
                    "equivalent"
                )
            else:
                errors.append("source commit mismatch")
    try:
        expected_paths = _artifact_paths(manifest)
    except ValidationProvenanceError as error:
        errors.append(str(error))
        expected_paths = []
    digests = payload["artifact_digests"]
    if isinstance(digests, dict):
        actual = set(str(item) for item in digests)
        expected_keys = set(expected_paths)
        if actual != expected_keys:
            errors.append(
                "artifact digest key set mismatch: missing={} unexpected={}".format(
                    sorted(expected_keys - actual),
                    sorted(actual - expected_keys),
                )
            )
        for relative in sorted(actual & expected_keys):
            record = digests[relative]
            if not isinstance(record, dict) or set(record) != {
                "sha256",
                "size_bytes",
            }:
                errors.append(
                    "invalid artifact digest record: {}".format(relative)
                )
                continue
            sha = record["sha256"]
            size = record["size_bytes"]
            if (
                not isinstance(sha, str)
                or re.fullmatch(r"[0-9a-f]{64}", sha) is None
                or type(size) is not int
                or size < 0
            ):
                errors.append(
                    "invalid artifact digest values: {}".format(relative)
                )
                continue
            try:
                content = _read(_repo(workdir, relative))
            except ValidationProvenanceError as error:
                errors.append(str(error))
                continue
            if len(content) != size:
                errors.append("artifact size mismatch: {}".format(relative))
            if hashlib.sha256(content).hexdigest() != sha:
                errors.append("artifact SHA-256 mismatch: {}".format(relative))
    return VerificationResult(tuple(errors), tuple(warnings))


def fail_validation_snapshot(*, workdir: Path, reason: str) -> None:
    cleanup: List[str] = []
    try:
        invalidate_validation_snapshot(workdir=workdir)
    except (OSError, ValidationProvenanceError) as error:
        cleanup.append("sidecar_cleanup={}".format(error))
    manifest_failed = False
    try:
        path = _repo(workdir, MANIFEST.as_posix())
        if path.is_file() and not path.is_symlink():
            manifest = _json(path)
            if "result" in manifest:
                manifest["result"] = "FAILED"
                _write_json(workdir, path, manifest)
                manifest_failed = True
    except (OSError, ValidationProvenanceError) as error:
        cleanup.append("manifest_rewrite={}".format(error))
    try:
        path = _repo(workdir, REPORT.as_posix())
        if path.is_file() and not path.is_symlink():
            output: List[str] = []
            inserted = False
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("- Verdict: **"):
                    output.append("- Verdict: **NO-GO**。")
                elif line.startswith("- result: `"):
                    output.extend(
                        (
                            "- result: `FAILED`",
                            "- snapshot_provenance: `FAILED` — {}".format(
                                reason.replace("\n", " ")[:500]
                            ),
                        )
                    )
                    inserted = True
                else:
                    output.append(line)
            if not inserted:
                output.extend(
                    (
                        "",
                        "## Snapshot provenance failure",
                        "",
                        "- {}".format(reason.replace("\n", " ")[:500]),
                    )
                )
            _write(
                workdir,
                path,
                ("\n".join(output) + "\n").encode("utf-8"),
            )
    except (OSError, UnicodeDecodeError, ValidationProvenanceError) as error:
        cleanup.append("report_rewrite={}".format(error))
    if not manifest_failed:
        cleanup.append("terminal_manifest_not_downgraded")
    if cleanup:
        raise ValidationProvenanceError(
            "Validation postflight failed closed with additional errors: "
            + "; ".join(cleanup)
        )


def _inject(
    workdir: Path,
    relative: Path,
    title: str,
    start: str,
    end: str,
    block: str,
    label: str,
) -> None:
    path = _repo(workdir, relative.as_posix())
    text = _read(path).decode("utf-8")
    if start in text or end in text:
        pattern = re.compile(
            re.escape(start) + r".*?" + re.escape(end),
            flags=re.DOTALL,
        )
        if not pattern.search(text):
            raise ValidationProvenanceError(
                "{} markers are malformed".format(label)
            )
        text = pattern.sub(block, text, count=1)
    else:
        first, separator, remainder = text.partition("\n")
        if first.strip() != title or not separator:
            raise ValidationProvenanceError(
                "{} has an unexpected title".format(relative)
            )
        text = first + "\n\n" + block + "\n\n" + remainder.lstrip("\n")
    _write(workdir, path, text.encode("utf-8"))


def ensure_report_provenance_notice(*, workdir: Path) -> None:
    _inject(
        workdir,
        REPORT,
        "# REPORT_十公司财务指标",
        REPORT_START,
        REPORT_END,
        REPORT_BLOCK,
        "Report provenance notice",
    )


def ensure_readme_routes(*, workdir: Path) -> None:
    _inject(
        workdir,
        README,
        "# README_RUN",
        README_START,
        README_END,
        README_BLOCK,
        "README route",
    )
