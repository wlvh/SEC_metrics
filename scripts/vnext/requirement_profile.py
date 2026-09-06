"""Version registry for immutable Requirement engines, not policy authority.

New engines are registered here without changing an already published engine
or its snapshot closure. Artifact generation is an explicit record contract;
it is never selected by the presence of Requirement identity fields.
"""

from pathlib import Path
from contextvars import ContextVar
from typing import Callable, Mapping

from . import requirement_profile_v1 as v1
from . import requirement_profile_v2 as v2
from . import requirement_profile_v3 as v3
from . import requirement_profile_v4 as v4
from .requirement_profile_v1 import CONTENT_HASH_PATTERN
from .requirement_profile_v1 import EXPLICIT_ARTIFACT_GENERATION
from .requirement_profile_v1 import LEGACY_ARTIFACT_GENERATION
from .requirement_profile_v1 import RequirementProfileError
from .requirement_profile_v1 import decision_record_hash
from .requirement_profile_v1 import read_requirement_object
from .requirement_profile_v1 import resolve_decision_chains
from .requirement_profile_v1 import validate_artifact_requirement_identity
from .requirement_profile_v1 import validate_execution_authority
from .requirement_profile_v1 import validate_transition_activation_receipt


PROFILE_REQUIREMENT_GENERATION = v1.PROFILE_REQUIREMENT_GENERATION
PROFILE_ENGINES = {
    v1.PROFILE_REQUIREMENT_GENERATION: v1,
    v2.PROFILE_REQUIREMENT_GENERATION: v2,
    v3.PROFILE_REQUIREMENT_GENERATION: v3,
    v4.PROFILE_REQUIREMENT_GENERATION: v4,
}
_LOADING_PATHS = ContextVar("requirement_loading_paths", default=())


def load_profile_requirement_snapshot(
    *, snapshot_dir: Path, parent_loader: Callable[..., Mapping[str, object]],
) -> dict:
    """Dispatch only a registered historical engine generation."""
    baseline = read_requirement_object(path=snapshot_dir / "baseline_manifest.json")
    engine = PROFILE_ENGINES.get(baseline.get("requirement_generation"))
    if engine is None:
        raise RequirementProfileError("Unknown Requirement engine generation")
    path = str(snapshot_dir.resolve())
    if path in _LOADING_PATHS.get():
        raise RequirementProfileError("Requirement ancestry contains a cycle")
    token = _LOADING_PATHS.set((*_LOADING_PATHS.get(), path))
    try:
        return engine.load_profile_requirement_snapshot(
            snapshot_dir=snapshot_dir, parent_loader=parent_loader,
        )
    finally:
        _LOADING_PATHS.reset(token)


def requirement_authority_paths(
    *, repo_root: Path, requirement: Mapping[str, object]
) -> list[str]:
    """Collect immutable snapshot/engine bytes for a portable publication."""
    paths = set()
    visited = set()

    def collect(requirement_id: str) -> None:
        if requirement_id in visited:
            return
        visited.add(requirement_id)
        directory = repo_root / "requirements" / requirement_id
        if directory.is_symlink() or not directory.is_dir():
            raise RequirementProfileError("Portable Requirement directory is unsafe")
        for path in directory.iterdir():
            if path.is_symlink() or not path.is_file():
                raise RequirementProfileError("Portable Requirement file is unsafe")
            paths.add(path.relative_to(repo_root).as_posix())
        baseline = read_requirement_object(path=directory / "baseline_manifest.json")
        if "parent" in baseline:
            collect(str(baseline["parent"]["requirement_id"]))
        elif "parent_requirement_id" in baseline:
            collect(str(baseline["parent_requirement_id"]))
        if baseline.get("supersedes_requirement"):
            collect(str(baseline["supersedes_requirement"]["requirement_id"]))
        if "validator" in baseline:
            paths.add(str(baseline["validator"]["path"]))
            paths.update(baseline["validator"]["dependencies"])

    collect(str(requirement["requirement_id"]))
    paths.update(requirement["execution_authority"]["files"])
    return sorted(paths)
