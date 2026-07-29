"""Audit vNext executables for reintroduced business parsers and unsafe AI I/O.

The audit parses Python ASTs under ``scripts/vnext`` and emits one receipt row
per literal/import/call match. Business semantic literals are allowed only in
catalog, Requirement snapshots, and tests, so any executable match fails with
``SEMANTIC_PARSER_REINTRODUCED``. The AI adapter additionally forbids direct
SEC transport, shell, subprocess, filesystem, and broad network imports.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


BUSINESS_LITERAL_PATTERN = re.compile(
    r"\b(lodging|hotel|occupancy|revpar|adr|marriott|pfizer|"
    r"systemwide|worldwide|comparable|b01|b03|b10|b11)\b",
    flags=re.IGNORECASE,
)
FORBIDDEN_AI_IMPORTS = {
    "http",
    "requests",
    "sec_http",
    "socket",
    "subprocess",
    "urllib",
}
FORBIDDEN_AI_CALLS = {"eval", "exec", "open", "system"}


class SemanticAuditError(RuntimeError):
    """Report an unreadable source tree or failed semantic audit."""


def _sha256(*, content: bytes) -> str:
    """Return SHA-256 for exact receipt/source bytes.

    Args:
        content: Bytes to hash.

    Returns:
        Lowercase digest.
    """
    return hashlib.sha256(content).hexdigest()


def _attribute_name(*, node: ast.AST) -> str:
    """Return a dotted name for one AST name/attribute expression.

    Args:
        node: Name, Attribute, or another expression.

    Returns:
        Best-effort dotted name; unknown expressions return an empty string.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _attribute_name(node=node.value)
        return parent + "." + node.attr if parent else node.attr
    return ""


def audit_python_file(
    *, path: Path, repo_root: Path
) -> List[Dict[str, object]]:
    """Return every classified semantic/security match in one Python file.

    Args:
        path: Executable Python file.
        repo_root: Root used for portable receipt paths.

    Returns:
        Ordered hit records.

    Raises:
        SemanticAuditError: On invalid UTF-8 or Python syntax.
    """
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
    except (UnicodeDecodeError, SyntaxError) as error:
        raise SemanticAuditError("Cannot parse {}".format(path)) from error
    relative = path.relative_to(repo_root).as_posix()
    hits: List[Dict[str, object]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            match = BUSINESS_LITERAL_PATTERN.search(node.value)
            if match is not None:
                hits.append(
                    {
                        "file": relative,
                        "line": node.lineno,
                        "literal": match.group(0),
                        "type": "BUSINESS_LITERAL",
                        "allowed": False,
                        "reason": (
                            "Business semantics belong in catalog/fixtures"
                        ),
                    }
                )
        if path.name != "ai_adapter.py":
            continue
        if isinstance(node, ast.Import):
            names = [alias.name.split(".", 1)[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            module = node.module if node.module is not None else ""
            names = [module.split(".", 1)[0]]
        else:
            names = []
        for name in names:
            if name in FORBIDDEN_AI_IMPORTS:
                hits.append(
                    {
                        "file": relative,
                        "line": node.lineno,
                        "literal": name,
                        "type": "AI_FORBIDDEN_IMPORT",
                        "allowed": False,
                        "reason": (
                            "AI adapter must not own SEC, shell, or broad "
                            "network I/O"
                        ),
                    }
                )
        if isinstance(node, ast.Call):
            call_name = _attribute_name(node=node.func).split(".")[-1]
            if call_name in FORBIDDEN_AI_CALLS:
                hits.append(
                    {
                        "file": relative,
                        "line": node.lineno,
                        "literal": call_name,
                        "type": "AI_FORBIDDEN_CALL",
                        "allowed": False,
                        "reason": (
                            "AI adapter has no shell or filesystem authority"
                        ),
                    }
                )
    return hits


def scan_secret_token(
    *, roots: Sequence[Path], secret_token: str
) -> List[Dict[str, object]]:
    """Find an exact test token in publishable/audit file bytes.

    Args:
        roots: Files or directories to scan recursively.
        secret_token: Non-empty key-like test token.

    Returns:
        Portable hit records. The token itself is never copied into output.
    """
    if not secret_token:
        raise SemanticAuditError("Secret scan token cannot be empty")
    needle = secret_token.encode("utf-8")
    hits = []
    for root in roots:
        paths: Iterable[Path]
        if root.is_symlink():
            hits.append(
                {
                    "file": str(root),
                    "line": 0,
                    "literal": "symlink",
                    "type": "SECRET_SCAN_SYMLINK",
                    "allowed": False,
                    "reason": "Secret scan root is a symbolic link",
                }
            )
            continue
        if root.is_file():
            paths = [root]
        elif root.is_dir():
            paths = sorted(root.rglob("*"))
        else:
            paths = []
        for path in paths:
            if path.is_symlink():
                hits.append(
                    {
                        "file": str(path),
                        "line": 0,
                        "literal": "symlink",
                        "type": "SECRET_SCAN_SYMLINK",
                        "allowed": False,
                        "reason": (
                            "Secret scan namespace contains a symbolic link"
                        ),
                    }
                )
                continue
            if not path.is_file():
                continue
            if needle in path.read_bytes():
                hits.append(
                    {
                        "file": str(path),
                        "line": 0,
                        "literal": "sha256:" + _sha256(content=needle),
                        "type": "SECRET_TOKEN",
                        "allowed": False,
                        "reason": "Secret-like test token reached an artifact",
                    }
                )
    return hits


def run_audit(
    *, repo_root: Path, secret_roots: Sequence[Path], secret_token: str
) -> Dict[str, object]:
    """Audit the complete vNext production Python boundary.

    Args:
        repo_root: Repository root.
        secret_roots: Optional artifact roots for token scanning.
        secret_token: Optional test token; empty disables only token scanning.

    Returns:
        Deterministic receipt mapping.
    """
    source_root = repo_root / "scripts" / "vnext"
    files = list(source_root.glob("*.py"))
    files.extend((repo_root / "tools").glob("vnext_*.py"))
    acceptance_runner = repo_root / "tools" / "run_acceptance.py"
    if acceptance_runner.is_file() and not acceptance_runner.is_symlink():
        files.append(acceptance_runner)
    files = sorted(files)
    if not files:
        raise SemanticAuditError("vNext executable source set is empty")
    hits = []
    source_hashes = {}
    for path in files:
        source_hashes[path.relative_to(repo_root).as_posix()] = _sha256(
            content=path.read_bytes()
        )
        hits.extend(audit_python_file(path=path, repo_root=repo_root))
    if secret_token:
        hits.extend(
            scan_secret_token(roots=secret_roots, secret_token=secret_token,)
        )
    # Distinguish artifact-namespace failures from source semantic regressions
    # so the receipt identifies which acceptance boundary rejected the run.
    secret_failure = any(
        str(hit["type"]).startswith("SECRET_") for hit in hits
    )
    failure_code = (
        "SECRET_ARTIFACT_SCAN_FAILED"
        if secret_failure
        else "SEMANTIC_PARSER_REINTRODUCED" if hits else ""
    )
    return {
        "schema_version": 1,
        "status": "FAIL" if hits else "PASS",
        "failure_code": failure_code,
        "source_hashes": source_hashes,
        "hits": hits,
    }


def main(*, argv: Sequence[str]) -> int:
    """Run the CLI and write one UTF-8 receipt.

    Args:
        argv: Command-line arguments excluding executable name.

    Returns:
        Zero only when every audit check passes.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root", default=str(Path(__file__).resolve().parents[1])
    )
    parser.add_argument(
        "--output", default="outputs/semantic_audit_receipt.json",
    )
    parser.add_argument("--secret-token", default="")
    parser.add_argument("--secret-token-env", default="")
    parser.add_argument("--secret-root", action="append", default=[])
    arguments = parser.parse_args(list(argv))
    repo_root = Path(arguments.repo_root).resolve()
    secret_roots = [repo_root / value for value in arguments.secret_root]
    if arguments.secret_token and arguments.secret_token_env:
        raise SemanticAuditError(
            "Use either --secret-token or --secret-token-env, not both"
        )
    secret_token = arguments.secret_token
    if arguments.secret_token_env:
        if arguments.secret_token_env not in os.environ:
            raise SemanticAuditError(
                "Secret scan environment variable is absent"
            )
        secret_token = os.environ[arguments.secret_token_env]
    receipt = run_audit(
        repo_root=repo_root,
        secret_roots=secret_roots,
        secret_token=secret_token,
    )
    output = repo_root / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": receipt["status"], "output": str(output)}))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
