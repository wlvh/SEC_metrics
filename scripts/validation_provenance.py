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
SOURCE_POLICY_SCHEMA = 1
PROVENANCE_RELATIVE_PATH = Path("outputs/validation_snapshot_provenance.json")
SOURCE_POLICY_RELATIVE_PATH = Path("config/validation_source_policy.json")
MANIFEST = Path("outputs/validation_run_manifest.json")
REPORT = Path("REPORT_十公司财务指标.md")
README = Path("README_RUN.md")
SOP = Path("SOP.md")
LIGHT_MARKER = Path("LIGHT_REVIEW_PACKAGE.marker")
SOURCE_POLICY_KEYS = {
    "schema_version", "runtime_source_directories",
    "acceptance_source_files", "generated_artifacts",
    "publication_governance_files", "repository_hygiene_files",
    "explanatory_non_authoritative",
}
SOP_REFERENCE_PATTERN = re.compile(
    r"(?<![\w./-])((?:\.?[\w-]+/)*[\w.-]+\."
    r"(?:md|json|csv|yaml|yml|py)|(?:\.?[\w-]+/)+)"
)
FULL_CORE = (
    MANIFEST.as_posix(), REPORT.as_posix(), README.as_posix(),
    "outputs/golden_results.csv", "outputs/metrics_matrix.csv",
    "outputs/metric_evidence.csv", "outputs/coverage_matrix.csv",
    "outputs/events.csv", "evidence/requests_log.csv",
    "evidence/requests_log_manifest.json",
)
LIGHT_CORE = FULL_CORE[:-2]
REQUIRED = {
    "schema_version", "run_id", "manifest_mode", "manifest_result",
    "manifest_source_commit", "source_checkout_status", "source_commit",
    "source_input_tree_sha256", "source_file_count", "source_dirty_paths",
    "artifact_digests", "generated_at_utc",
}
README_START = "<!-- validation-reading-routes:start -->"
README_END = "<!-- validation-reading-routes:end -->"
README_BLOCK = """<!-- validation-reading-routes:start -->
## 只读取现有结果

1. 先读 `outputs/validation_run_manifest.json`；`result` 不是 `PASSED` / `PASSED_WITH_CAVEATS` 时停止验收。
2. 运行 `python3 tools/check_validation_snapshot.py`；缺少 provenance、源输入树不一致、关键 artifact hash 失配或 source input 有未提交改动时停止验收。
3. 再读 `REPORT_十公司财务指标.md`，随后按需查看 `outputs/metrics_matrix.csv` 与 `outputs/metric_evidence.csv`。
4. `source_commit` 与当前 HEAD 不同不自动等于失败；只有独立 checker 证明 source-input tree 等价时，merge commit 等 SHA 变化才可接受。

## 执行新批次

1. 使用干净 checkout，并配置有效 SEC organization/contact email。
2. 按顺序运行阶段 `00`–`11`；stage 11 exit 0 只表示报告构建完成。
3. 单独运行 `python3 scripts/12_validate_repair.py`。
4. 只有 stage 12 exit 0、terminal manifest 成功，且 `python3 tools/check_validation_snapshot.py` 通过，才构成完整批次成功。

## Validation snapshot provenance

- stage 11 在修改报告前删除可安全识别的旧 regular `outputs/validation_snapshot_provenance.json`；alias/非 regular 目标提前失败。
- `config/validation_source_policy.json` 分类 runtime source、acceptance source、generated artifact、发布治理和解释性文档；SOP 权威引用必须有明确角色，解释性非权威文档不能作为运行权威。
- stage 12 只在 policy-defined source closure 无未提交改动时继续；成功后绑定当前 Git commit、完整 source-input tree SHA-256，以及 manifest、报告、README、metrics/evidence/coverage/Golden、request ledger 与 refreshed validation artifact 的 SHA-256/size。
- 提交或 merge 导致 commit SHA 改变时，checker 只有在完整 source-input tree 仍等价时才给 warning 并允许继续；任一 source byte 或 artifact byte 漂移都失败。
- light package 可以生成显式 `LIGHT_PACKAGE_NO_GIT` 的受限 provenance，但不能升级为 full validation。
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
    """Report an invalid or unverifiable validation snapshot state."""

    pass


@dataclass(frozen=True)
class SourcePolicy:
    """Classify files that can affect runtime, acceptance, or documentation."""

    runtime_source_directories: Tuple[str, ...]
    acceptance_source_files: Tuple[str, ...]
    generated_artifacts: Tuple[str, ...]
    publication_governance_files: Tuple[str, ...]
    repository_hygiene_files: Tuple[str, ...]
    explanatory_non_authoritative: Tuple[str, ...]

    @property
    def source_paths(self) -> Tuple[str, ...]:
        """Return the policy-bound Git pathspecs, including the policy itself."""
        paths = (
            *self.runtime_source_directories,
            *self.acceptance_source_files,
            SOURCE_POLICY_RELATIVE_PATH.as_posix(),
        )
        return tuple(sorted(set(paths)))


@dataclass(frozen=True)
class SourceSnapshot:
    """Describe one deterministic and clean source-input tree."""

    checkout_status: str
    source_commit: Optional[str]
    tree_sha256: str
    file_count: int
    dirty_paths: Tuple[str, ...]


@dataclass(frozen=True)
class VerificationResult:
    """Return all snapshot verification errors and non-fatal warnings."""

    errors: Tuple[str, ...]
    warnings: Tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Return whether verification found no errors."""
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
        raise ValidationProvenanceError("Snapshot path escapes repository: {}".format(relative))
    candidate, current = workdir / path, workdir
    for part in path.parts:
        current /= part
        if os.path.lexists(current) and current.is_symlink():
            raise ValidationProvenanceError("Snapshot path contains a symlink component: {}".format(current))
    try:
        candidate.resolve(strict=False).relative_to(workdir.resolve())
    except ValueError as error:
        raise ValidationProvenanceError("Snapshot path resolves outside repository: {}".format(relative)) from error
    return candidate


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValidationProvenanceError("Snapshot input must be a non-symlink regular file: {}".format(path))
    return path.read_bytes()


def _write(workdir: Path, path: Path, content: bytes) -> None:
    relative = path.relative_to(workdir).as_posix()
    path = _repo(workdir, relative)
    if path.exists() and not path.is_file():
        raise ValidationProvenanceError("Snapshot output is not a regular file: {}".format(path))
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
        raise ValidationProvenanceError("Snapshot atomic-write postcondition failed: {}".format(path))


def _write_json(workdir: Path, path: Path, payload: Mapping[str, object]) -> None:
    _write(workdir, path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _git(workdir: Path, args: Sequence[str]) -> bytes:
    result = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(workdir), *args],
        check=False, capture_output=True, env=sanitized_git_environment(),
    )
    if result.returncode:
        raise ValidationProvenanceError(
            "Git command failed ({}): {}".format(
                " ".join(args), result.stderr.decode("utf-8", errors="replace").strip()
            )
        )
    return result.stdout


def _nul(content: bytes) -> List[str]:
    return [item.decode("utf-8") for item in content.split(b"\0") if item]


def _json(path: Path) -> Dict[str, object]:
    """Read one UTF-8 JSON object or fail at the current boundary."""
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


def _policy_values(
    *, payload: Mapping[str, object], key: str
) -> Tuple[str, ...]:
    """Return one required, unique array of non-empty policy paths."""
    values = payload[key]
    if not isinstance(values, list):
        raise ValidationProvenanceError(
            "Source policy {} must be a non-empty string array".format(key)
        )
    if not values or any(
        not isinstance(value, str) or not value for value in values
    ):
        raise ValidationProvenanceError(
            "Source policy {} must be a non-empty string array".format(key)
        )
    if len(values) != len(set(values)):
        raise ValidationProvenanceError(
            "Source policy {} contains duplicate paths".format(key)
        )
    return tuple(values)


def _validate_policy_path(*, relative: str, directory: bool) -> None:
    """Require a normalized repository-relative file or directory path."""
    path = Path(relative)
    invalid = any((
        path.is_absolute(),
        ".." in path.parts,
        path.as_posix() != relative,
        relative in {"", "."},
    ))
    if invalid:
        raise ValidationProvenanceError(
            "Source policy path is not normalized repository-relative: "
            "{}".format(relative)
        )
    if directory and len(path.parts) != 1:
        raise ValidationProvenanceError(
            "Runtime source directory must be a top-level path: {}".format(
                relative
            )
        )


def _sop_authority_references(*, workdir: Path) -> Tuple[str, ...]:
    """Extract repository paths only from SOP table authority columns."""
    try:
        text = _read(_repo(workdir, SOP.as_posix())).decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationProvenanceError("SOP.md must be UTF-8") from error
    authority_index: Optional[int] = None
    found_header = False
    references = set()
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            authority_index = None
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if "权威引用" in cells:
            authority_index = cells.index("权威引用")
            found_header = True
            continue
        if authority_index is None or len(cells) <= authority_index:
            continue
        if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        for match in SOP_REFERENCE_PATTERN.finditer(cells[authority_index]):
            relative = match.group(1)
            if relative.startswith("./"):
                relative = relative[2:]
            references.add(relative)
    if not found_header or not references:
        raise ValidationProvenanceError(
            "SOP.md must contain non-empty authority-reference table columns"
        )
    return tuple(sorted(references))


def _validate_sop_authority_references(
    *, workdir: Path, policy: SourcePolicy
) -> None:
    """Reject unclassified or falsely authoritative SOP file references."""
    source_files = set(policy.acceptance_source_files)
    generated = set(policy.generated_artifacts)
    governance = set(policy.publication_governance_files)
    governance.update(policy.repository_hygiene_files)
    artifacts = set(FULL_CORE)
    classified = source_files | generated | governance | artifacts
    unclassified = []
    explanatory = []
    for relative in _sop_authority_references(workdir=workdir):
        normalized = relative.rstrip("/")
        runtime = any(
            normalized == directory or normalized.startswith(directory + "/")
            for directory in policy.runtime_source_directories
        )
        if relative in policy.explanatory_non_authoritative:
            explanatory.append(relative)
        elif not runtime and relative not in classified:
            unclassified.append(relative)
    if explanatory:
        raise ValidationProvenanceError(
            "SOP authority references explanatory non-authoritative files: "
            "{}".format(",".join(explanatory))
        )
    if unclassified:
        raise ValidationProvenanceError(
            "SOP authority references are not classified by source policy: "
            "{}".format(",".join(unclassified))
        )


def load_source_policy(*, workdir: Path) -> SourcePolicy:
    """Load and validate the machine-readable source and document policy."""
    payload = _json(_repo(workdir, SOURCE_POLICY_RELATIVE_PATH.as_posix()))
    if set(payload) != SOURCE_POLICY_KEYS:
        raise ValidationProvenanceError(
            "Source policy keys do not match the required schema"
        )
    schema_version = payload["schema_version"]
    valid_schema = all((
        type(schema_version) is int,
        schema_version == SOURCE_POLICY_SCHEMA,
    ))
    if not valid_schema:
        raise ValidationProvenanceError(
            "Unsupported source policy schema_version"
        )
    runtime = _policy_values(
        payload=payload,
        key="runtime_source_directories",
    )
    acceptance = _policy_values(
        payload=payload,
        key="acceptance_source_files",
    )
    generated = _policy_values(payload=payload, key="generated_artifacts")
    publication = _policy_values(
        payload=payload,
        key="publication_governance_files",
    )
    hygiene = _policy_values(
        payload=payload,
        key="repository_hygiene_files",
    )
    explanatory = _policy_values(
        payload=payload,
        key="explanatory_non_authoritative",
    )
    for relative in runtime:
        _validate_policy_path(relative=relative, directory=True)
    role_files = acceptance + generated + publication + hygiene + explanatory
    for relative in role_files:
        _validate_policy_path(relative=relative, directory=False)
    duplicates = sorted(
        relative for relative in set(role_files)
        if role_files.count(relative) > 1
    )
    if duplicates:
        raise ValidationProvenanceError(
            "Source policy assigns multiple roles to: {}".format(
                ",".join(duplicates)
            )
        )
    if SOP.as_posix() not in acceptance:
        raise ValidationProvenanceError(
            "SOP.md must be an acceptance source file"
        )
    if set(generated) != {README.as_posix(), REPORT.as_posix()}:
        raise ValidationProvenanceError(
            "Source policy generated_artifacts must match README and report"
        )
    policy = SourcePolicy(
        runtime_source_directories=runtime,
        acceptance_source_files=acceptance,
        generated_artifacts=generated,
        publication_governance_files=publication,
        repository_hygiene_files=hygiene,
        explanatory_non_authoritative=explanatory,
    )
    _validate_sop_authority_references(workdir=workdir, policy=policy)
    return policy


def _git_paths(*, workdir: Path, policy: SourcePolicy) -> List[str]:
    """Return the exact tracked source closure declared by the policy."""
    paths = sorted(set(_nul(_git(
        workdir,
        ["ls-files", "-z", "--", *policy.source_paths],
    ))))
    required = set(policy.acceptance_source_files)
    required.add(SOURCE_POLICY_RELATIVE_PATH.as_posix())
    missing = sorted(required - set(paths))
    if missing:
        raise ValidationProvenanceError(
            "Required source inputs are not tracked: {}".format(
                ",".join(missing)
            )
        )
    empty_directories = sorted(
        directory for directory in policy.runtime_source_directories
        if not any(
            path == directory or path.startswith(directory + "/")
            for path in paths
        )
    )
    if empty_directories:
        raise ValidationProvenanceError(
            "Runtime source directories have no tracked files: {}".format(
                ",".join(empty_directories)
            )
        )
    return paths


def _dirty(*, workdir: Path, policy: SourcePolicy) -> List[str]:
    """Return tracked, staged, ignored, or untracked source-policy changes."""
    commands = (
        ["diff", "--name-only", "-z", "--", *policy.source_paths],
        ["diff", "--cached", "--name-only", "-z", "--", *policy.source_paths],
        ["ls-files", "--others", "-z", "--", *policy.source_paths],
    )
    paths = set()
    for command in commands:
        paths.update(_nul(_git(workdir, command)))
    return sorted(
        path for path in paths
        if all((
            "__pycache__" not in Path(path).parts,
            Path(path).suffix not in {".pyc", ".pyo"},
        ))
    )


def _filesystem_paths(*, workdir: Path, policy: SourcePolicy) -> List[str]:
    """Enumerate a complete no-Git light-package source closure."""
    paths: List[str] = []
    for directory_name in policy.runtime_source_directories:
        directory = _repo(workdir, directory_name)
        if directory.is_symlink() or not directory.is_dir():
            raise ValidationProvenanceError(
                "Source directory is not a real directory: {}".format(
                    directory
                )
            )
        for path in directory.rglob("*"):
            if path.is_symlink():
                raise ValidationProvenanceError(
                    "Source input is a symlink: {}".format(path)
                )
            if path.is_dir():
                continue
            relative = path.relative_to(workdir)
            ignored = any((
                "__pycache__" in relative.parts,
                path.suffix in {".pyc", ".pyo"},
            ))
            if ignored:
                continue
            if not path.is_file():
                raise ValidationProvenanceError(
                    "Source input is not a regular file: {}".format(path)
                )
            paths.append(relative.as_posix())
    # Explicit files prevent light packages from deleting a singleton to shrink
    # the closure. The policy stays explicit even if config/ is reclassified.
    explicit = policy.acceptance_source_files + (
        SOURCE_POLICY_RELATIVE_PATH.as_posix(),
    )
    for relative in explicit:
        _read(_repo(workdir, relative))
        paths.append(relative)
    paths = sorted(set(paths))
    if not paths:
        raise ValidationProvenanceError(
            "Filesystem source-input closure is empty"
        )
    return paths


def _tree(*, workdir: Path, paths: Iterable[str]) -> Tuple[str, int]:
    """Hash repository-relative path, byte length, and content identity."""
    digest, count = hashlib.sha256(), 0
    for relative in sorted(paths):
        content = _read(_repo(workdir, relative))
        record = "{}\0{}\0{}\n".format(
            relative,
            len(content),
            hashlib.sha256(content).hexdigest(),
        )
        digest.update(record.encode("utf-8"))
        count += 1
    return digest.hexdigest(), count


def capture_source_snapshot(*, workdir: Path) -> SourceSnapshot:
    """Capture one clean policy-defined Git or explicit light source tree."""
    policy = load_source_policy(workdir=workdir)
    metadata_error = git_checkout_metadata_error(repo_root=workdir)
    if metadata_error:
        if not _repo(workdir, LIGHT_MARKER.as_posix()).is_file():
            raise ValidationProvenanceError(
                "Git source provenance unavailable outside an explicit light "
                "package: {}".format(metadata_error)
            )
        tree, count = _tree(
            workdir=workdir,
            paths=_filesystem_paths(workdir=workdir, policy=policy),
        )
        return SourceSnapshot(
            checkout_status="LIGHT_PACKAGE_NO_GIT",
            source_commit=None,
            tree_sha256=tree,
            file_count=count,
            dirty_paths=(),
        )
    commit = _git(workdir, ["rev-parse", "HEAD"]).decode("utf-8").strip()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValidationProvenanceError(
            "Git HEAD is not a full commit SHA: {}".format(commit)
        )
    dirty = _dirty(workdir=workdir, policy=policy)
    if dirty:
        raise ValidationProvenanceError(
            "Source-input files are dirty: {}".format(",".join(dirty))
        )
    tree, count = _tree(
        workdir=workdir,
        paths=_git_paths(workdir=workdir, policy=policy),
    )
    return SourceSnapshot(
        checkout_status="GIT_CLEAN",
        source_commit=commit,
        tree_sha256=tree,
        file_count=count,
        dirty_paths=(),
    )


def _manifest(workdir: Path) -> Dict[str, object]:
    manifest = _json(_repo(workdir, MANIFEST.as_posix()))
    required = {"run_id", "source_commit", "started_at_utc", "mode", "refreshed_artifacts", "not_refreshed_artifacts", "result"}
    if set(manifest) != required:
        raise ValidationProvenanceError("Validation manifest keys do not match the required schema")
    for key in ("run_id", "source_commit", "started_at_utc"):
        if not isinstance(manifest[key], str) or not manifest[key].strip():
            raise ValidationProvenanceError("Validation manifest {} must be a non-empty string".format(key))
    if not _is_utc(str(manifest["started_at_utc"])):
        raise ValidationProvenanceError("Validation manifest started_at_utc must be UTC ISO-8601")
    if manifest["mode"] not in {"FULL_VALIDATION", "LIGHT_REVIEW_MODE", "WORKSPACE_INCOMPLETE"}:
        raise ValidationProvenanceError("Validation manifest mode is invalid: {}".format(manifest["mode"]))
    if manifest["result"] not in {"IN_PROGRESS", "PASSED", "PASSED_WITH_CAVEATS", "FAILED"}:
        raise ValidationProvenanceError("Validation manifest result is invalid: {}".format(manifest["result"]))
    refreshed, stale = manifest["refreshed_artifacts"], manifest["not_refreshed_artifacts"]
    if not isinstance(refreshed, list) or not isinstance(stale, list) or any(not isinstance(x, str) for x in refreshed + stale):
        raise ValidationProvenanceError("Validation manifest artifact lists must be string arrays")
    if len(refreshed) != len(set(refreshed)) or len(stale) != len(set(stale)) or set(refreshed) & set(stale):
        raise ValidationProvenanceError("Validation manifest artifact lists are not unique/disjoint")
    return manifest


def _commit_base(value: str) -> Optional[str]:
    if re.fullmatch(r"[0-9a-f]{40}", value):
        return value
    for suffix in ("+dirty", "+status-unknown"):
        if value.endswith(suffix) and re.fullmatch(r"[0-9a-f]{40}", value[:-len(suffix)]):
            return value[:-len(suffix)]
    return None


def _manifest_matches(value: str, snapshot: SourceSnapshot) -> bool:
    return (
        value == "UNAVAILABLE_NON_GIT_WORKSPACE"
        if snapshot.source_commit is None
        else _commit_base(value) == snapshot.source_commit
    )


def _artifact_paths(manifest: Mapping[str, object]) -> List[str]:
    refreshed = manifest["refreshed_artifacts"]
    if not isinstance(refreshed, list) or any(not isinstance(x, str) for x in refreshed):
        raise ValidationProvenanceError("Validation manifest refreshed_artifacts must be a string array")
    invalid = [x for x in refreshed if not x or Path(x).name != x or "/" in x or "\\" in x]
    if invalid:
        raise ValidationProvenanceError("Validation manifest refreshed artifact names are not basenames: " + ",".join(invalid))
    core = FULL_CORE if manifest["mode"] == "FULL_VALIDATION" else LIGHT_CORE
    return sorted(set(core) | {"outputs/{}".format(x) for x in refreshed})


def _digests(workdir: Path, paths: Iterable[str]) -> Dict[str, Dict[str, object]]:
    result: Dict[str, Dict[str, object]] = {}
    for relative in sorted(set(paths)):
        content = _read(_repo(workdir, relative))
        result[relative] = {"sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
    return result


def invalidate_validation_snapshot(*, workdir: Path) -> None:
    path = _repo(workdir, PROVENANCE_RELATIVE_PATH.as_posix())
    if not path.exists():
        return
    if not path.is_file():
        raise ValidationProvenanceError("Existing validation provenance is not a regular file: {}".format(path))
    path.unlink()


def publish_validation_snapshot(*, workdir: Path, source_snapshot: SourceSnapshot) -> Dict[str, object]:
    manifest = _manifest(workdir)
    expected = {"FULL_VALIDATION": "PASSED", "LIGHT_REVIEW_MODE": "PASSED_WITH_CAVEATS"}
    mode, result = str(manifest["mode"]), str(manifest["result"])
    if mode not in expected or result != expected[mode]:
        raise ValidationProvenanceError("Only a successful full/light terminal manifest can be attested: mode={} result={}".format(mode, result))
    if not _manifest_matches(str(manifest["source_commit"]), source_snapshot):
        raise ValidationProvenanceError("Validation manifest source_commit does not identify the captured source commit")
    current = capture_source_snapshot(workdir=workdir)
    if current != source_snapshot:
        raise ValidationProvenanceError("Source input or Git HEAD changed during terminal validation")
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
    checked = verify_validation_snapshot(workdir=workdir, allow_equivalent_source_tree=False)
    if not checked.ok:
        raise ValidationProvenanceError("Published validation provenance failed verification: " + "; ".join(checked.errors))
    return payload


def _schema_errors(payload: Mapping[str, object]) -> List[str]:
    errors: List[str] = []
    if set(payload) != REQUIRED:
        missing, extra = sorted(REQUIRED - set(payload)), sorted(set(payload) - REQUIRED)
        if missing:
            errors.append("provenance missing keys: {}".format(",".join(missing)))
        if extra:
            errors.append("provenance unexpected keys: {}".format(",".join(extra)))
        return errors
    if payload["schema_version"] != SCHEMA:
        errors.append("unsupported provenance schema_version")
    expected = {"FULL_VALIDATION": "PASSED", "LIGHT_REVIEW_MODE": "PASSED_WITH_CAVEATS"}
    if payload["manifest_mode"] not in expected:
        errors.append("provenance manifest_mode is not attestable")
    elif payload["manifest_result"] != expected[payload["manifest_mode"]]:
        errors.append("provenance manifest_result is not a successful terminal state")
    if payload["source_checkout_status"] not in {"GIT_CLEAN", "LIGHT_PACKAGE_NO_GIT"}:
        errors.append("unsupported source_checkout_status")
    for key in ("run_id", "manifest_mode", "manifest_result", "manifest_source_commit", "source_checkout_status", "source_input_tree_sha256", "generated_at_utc"):
        if not isinstance(payload[key], str) or not payload[key].strip():
            errors.append("{} must be a non-empty string".format(key))
    manifest_commit = str(payload["manifest_source_commit"])
    if manifest_commit != "UNAVAILABLE_NON_GIT_WORKSPACE" and _commit_base(manifest_commit) is None:
        errors.append("manifest_source_commit has an unsupported format")
    source_commit = payload["source_commit"]
    if source_commit is not None and (not isinstance(source_commit, str) or re.fullmatch(r"[0-9a-f]{40}", source_commit) is None):
        errors.append("source_commit must be null or a full commit SHA")
    if not isinstance(payload["source_input_tree_sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", str(payload["source_input_tree_sha256"])) is None:
        errors.append("source_input_tree_sha256 must be lowercase SHA-256")
    if type(payload["source_file_count"]) is not int or payload["source_file_count"] < 1:
        errors.append("source_file_count must be a positive integer")
    dirty = payload["source_dirty_paths"]
    if not isinstance(dirty, list) or any(not isinstance(x, str) for x in dirty):
        errors.append("source_dirty_paths must be a string array")
    elif dirty:
        errors.append("successful provenance cannot contain dirty source paths")
    if payload["source_checkout_status"] == "GIT_CLEAN" and source_commit is None:
        errors.append("GIT_CLEAN provenance requires source_commit")
    if payload["source_checkout_status"] == "LIGHT_PACKAGE_NO_GIT" and source_commit is not None:
        errors.append("LIGHT_PACKAGE_NO_GIT provenance requires null source_commit")
    if not isinstance(payload["artifact_digests"], dict):
        errors.append("artifact_digests must be an object")
    if not _is_utc(str(payload["generated_at_utc"])):
        errors.append("generated_at_utc must be an ISO 8601 UTC timestamp")
    return errors


def verify_validation_snapshot(*, workdir: Path, allow_equivalent_source_tree: bool = True) -> VerificationResult:
    """Verify policy, source identity, manifest identity, and artifact bytes."""
    errors: List[str] = []
    warnings: List[str] = []
    try:
        load_source_policy(workdir=workdir)
    except ValidationProvenanceError as error:
        errors.append(str(error))
    try:
        path = _repo(workdir, PROVENANCE_RELATIVE_PATH.as_posix())
    except ValidationProvenanceError as error:
        errors.append(str(error))
        return VerificationResult(tuple(errors), ())
    if not path.exists():
        errors.append("validation snapshot provenance is missing")
        return VerificationResult(tuple(errors), ())
    if errors:
        return VerificationResult(tuple(errors), ())
    try:
        payload, manifest = _json(path), _manifest(workdir)
    except ValidationProvenanceError as error:
        return VerificationResult((str(error),), ())
    errors.extend(_schema_errors(payload))
    if errors:
        return VerificationResult(tuple(errors), tuple(warnings))
    for pkey, mkey in (("run_id", "run_id"), ("manifest_mode", "mode"), ("manifest_result", "result"), ("manifest_source_commit", "source_commit")):
        if payload[pkey] != manifest[mkey]:
            errors.append("{} does not match validation manifest".format(pkey))
    published = SourceSnapshot(
        checkout_status=str(payload["source_checkout_status"]),
        source_commit=(
            str(payload["source_commit"])
            if payload["source_commit"] is not None
            else None
        ),
        tree_sha256=str(payload["source_input_tree_sha256"]),
        file_count=int(payload["source_file_count"]),
        dirty_paths=tuple(str(x) for x in payload["source_dirty_paths"]),
    )
    if not _manifest_matches(str(manifest["source_commit"]), published):
        errors.append("validation manifest source_commit does not identify the published source commit")
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
            if allow_equivalent_source_tree and published.tree_sha256 == current.tree_sha256:
                warnings.append("Git commit differs but the complete source-input tree is equivalent")
            else:
                errors.append("source commit mismatch")
    try:
        expected_paths = _artifact_paths(manifest)
    except ValidationProvenanceError as error:
        errors.append(str(error))
        expected_paths = []
    digests = payload["artifact_digests"]
    if isinstance(digests, dict):
        actual, expected_keys = set(str(x) for x in digests), set(expected_paths)
        if actual != expected_keys:
            errors.append("artifact digest key set mismatch: missing={} unexpected={}".format(sorted(expected_keys - actual), sorted(actual - expected_keys)))
        for relative in sorted(actual & expected_keys):
            record = digests[relative]
            if not isinstance(record, dict) or set(record) != {"sha256", "size_bytes"}:
                errors.append("invalid artifact digest record: {}".format(relative))
                continue
            sha, size = record["sha256"], record["size_bytes"]
            if not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None or type(size) is not int or size < 0:
                errors.append("invalid artifact digest values: {}".format(relative))
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
                    output.extend(("- result: `FAILED`", "- snapshot_provenance: `FAILED` — {}".format(reason.replace("\n", " ")[:500])))
                    inserted = True
                else:
                    output.append(line)
            if not inserted:
                output.extend(("", "## Snapshot provenance failure", "", "- {}".format(reason.replace("\n", " ")[:500])))
            _write(workdir, path, ("\n".join(output) + "\n").encode("utf-8"))
    except (OSError, UnicodeDecodeError, ValidationProvenanceError) as error:
        cleanup.append("report_rewrite={}".format(error))
    if not manifest_failed:
        cleanup.append("terminal_manifest_not_downgraded")
    if cleanup:
        raise ValidationProvenanceError("Validation postflight failed closed with additional errors: " + "; ".join(cleanup))


def _inject(workdir: Path, relative: Path, title: str, start: str, end: str, block: str, label: str) -> None:
    path = _repo(workdir, relative.as_posix())
    text = _read(path).decode("utf-8")
    if start in text or end in text:
        pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), flags=re.DOTALL)
        if not pattern.search(text):
            raise ValidationProvenanceError("{} markers are malformed".format(label))
        text = pattern.sub(block, text, count=1)
    else:
        first, separator, remainder = text.partition("\n")
        if first.strip() != title or not separator:
            raise ValidationProvenanceError("{} has an unexpected title".format(relative))
        text = first + "\n\n" + block + "\n\n" + remainder.lstrip("\n")
    _write(workdir, path, text.encode("utf-8"))


def ensure_report_provenance_notice(*, workdir: Path) -> None:
    _inject(workdir, REPORT, "# REPORT_十公司财务指标", REPORT_START, REPORT_END, REPORT_BLOCK, "Report provenance notice")


def ensure_readme_routes(*, workdir: Path) -> None:
    _inject(workdir, README, "# README_RUN", README_START, README_END, README_BLOCK, "README route")
