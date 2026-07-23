"""Validate local Git checkout identity for audit-sensitive commands.

Purpose:
    Prevent a repository directory or extracted archive from borrowing another
    checkout's Git environment, directory, or gitfile metadata.

Call relationships:
    sec_pipeline request-history validation and the capability-contract checker
    call these helpers before reading HEAD objects.
"""

from __future__ import annotations

import os
from pathlib import Path


GIT_ENVIRONMENT_OVERRIDES = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_DIR",
    "GIT_INDEX_FILE",
    "GIT_NAMESPACE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_SHALLOW_FILE",
    "GIT_WORK_TREE",
}


def sanitized_git_environment() -> dict[str, str]:
    """Return process environment without Git repository selectors."""
    environment = os.environ.copy()
    # Git must discover metadata from the reviewed path itself; inherited
    # selectors can otherwise make an archive borrow an unrelated HEAD.
    for variable in list(environment):
        if (
            variable in GIT_ENVIRONMENT_OVERRIDES
            or variable.startswith("GIT_CONFIG_")
        ):
            environment.pop(variable)
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    return environment


def first_symlink_in_tree(*, root: Path) -> Path | None:
    """Return the first symlink below a metadata tree.

    Args:
        root: Git metadata directory whose descendants must remain local.

    Returns:
        A symlink path, or None when the complete tree is self-contained.
    """
    if root.is_symlink():
        return root
    if not root.is_dir():
        return None
    # Object and ref lookups must not depend on a mutable external namespace.
    for directory, directory_names, file_names in os.walk(
        root,
        followlinks=False,
    ):
        for name in directory_names + file_names:
            candidate = Path(directory) / name
            if candidate.is_symlink():
                return candidate
    return None


def first_symlink_in_path(*, path: Path) -> Path | None:
    """Return the first symlink in one unresolved lexical path.

    Args:
        path: Absolute or relative locator whose components must not redirect.

    Returns:
        The first symlink component, or None when every component is direct.
    """
    current = Path(path.anchor) if path.is_absolute() else Path()
    parts = path.parts[1:] if path.is_absolute() else path.parts
    # The locator must be inspected before resolve() erases path identity.
    for part in parts:
        current /= part
        if current.is_symlink():
            return current
    return None


def git_common_directory(*, git_dir: Path) -> tuple[Path | None, str]:
    """Resolve a Git common directory without accepting indirect metadata.

    Args:
        git_dir: Normal `.git` directory or linked-worktree registration.

    Returns:
        Common directory and an empty diagnostic, or None and an error.
    """
    commondir = git_dir / "commondir"
    if not commondir.exists() and not commondir.is_symlink():
        return git_dir, ""
    if commondir.is_symlink() or not commondir.is_file():
        return None, "Git commondir must be a regular local file"
    try:
        text = commondir.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as error:
        return None, f"Git commondir is unreadable: {error}"
    if not text or "\n" in text:
        return None, "Git commondir has invalid syntax"
    common_path = Path(text)
    if not common_path.is_absolute():
        common_path = git_dir / common_path
    common_link = first_symlink_in_path(path=common_path)
    if common_link is not None:
        return None, f"Git commondir locator contains symlink: {common_link}"
    common_dir = common_path.resolve(strict=False)
    if not common_dir.is_dir():
        return None, "Git commondir does not resolve to a local directory"
    return common_dir, ""


def git_storage_metadata_error(*, git_dir: Path) -> str:
    """Return an error when HEAD storage depends on external indirection.

    Args:
        git_dir: Validated normal or linked-worktree Git directory.

    Returns:
        Empty text only when object/ref metadata is local and self-contained.
    """
    common_dir, common_error = git_common_directory(git_dir=git_dir)
    if common_error:
        return common_error
    if common_dir is None:
        return "Git commondir unavailable"
    object_dir = common_dir / "objects"
    if object_dir.is_symlink() or not object_dir.is_dir():
        return "Git object store must be a local directory"
    for alternate_name in ["alternates", "http-alternates"]:
        alternate = object_dir / "info" / alternate_name
        if alternate.exists() or alternate.is_symlink():
            return f"Git object store {alternate_name} are not allowed"
    object_link = first_symlink_in_tree(root=object_dir)
    if object_link is not None:
        return f"Git object store contains symlink: {object_link}"
    for ref_root in [git_dir / "refs", common_dir / "refs"]:
        ref_link = first_symlink_in_tree(root=ref_root)
        if ref_link is not None:
            return f"Git refs contain symlink: {ref_link}"
    for metadata_path in [
        git_dir / "HEAD",
        git_dir / "index",
        common_dir / "config",
        common_dir / "packed-refs",
    ]:
        if metadata_path.is_symlink():
            return f"Git metadata must not be a symlink: {metadata_path}"
    return ""


def git_checkout_metadata_error(*, repo_root: Path) -> str:
    """Return an error unless `.git` belongs to this checkout.

    Args:
        repo_root: Candidate Git worktree root.

    Returns:
        Empty text for a normal clone or valid linked worktree; otherwise a
        diagnostic explaining why local Git metadata cannot be trusted.
    """
    dot_git = repo_root / ".git"
    if dot_git.is_symlink():
        return ".git must not be a symlink"
    if dot_git.is_dir():
        return git_storage_metadata_error(git_dir=dot_git)
    if not dot_git.is_file():
        return ".git must be a local directory or linked-worktree gitfile"
    try:
        gitfile_text = dot_git.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as error:
        return f".git file is unreadable: {error}"
    prefix = "gitdir: "
    if not gitfile_text.startswith(prefix) or "\n" in gitfile_text:
        return ".git file has invalid gitdir syntax"
    gitdir_locator = Path(gitfile_text[len(prefix):])
    if not gitdir_locator.is_absolute():
        gitdir_locator = dot_git.parent / gitdir_locator
    gitdir_link = first_symlink_in_path(path=gitdir_locator)
    if gitdir_link is not None:
        return f"Git gitdir locator contains symlink: {gitdir_link}"
    gitdir = gitdir_locator.resolve(strict=False)
    back_reference = gitdir / "gitdir"
    if (
        not gitdir.is_dir()
        or back_reference.is_symlink()
        or not back_reference.is_file()
    ):
        return ".git file is not a valid linked-worktree registration"
    try:
        back_text = back_reference.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as error:
        return f"linked-worktree back-reference is unreadable: {error}"
    back_path = Path(back_text)
    if not back_path.is_absolute():
        back_path = gitdir / back_path
    back_link = first_symlink_in_path(path=back_path)
    if back_link is not None:
        return f"linked-worktree back-reference contains symlink: {back_link}"
    if back_path.resolve(strict=False) != dot_git.resolve(strict=False):
        return ".git file does not point back to this worktree"
    return git_storage_metadata_error(git_dir=gitdir)
