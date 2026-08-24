#!/usr/bin/env python3
"""Prove every model-provider opener is behind WB-3 reservation ownership.

The gate scans production Python under ``scripts`` and ``tools``. It fixes the
sole direct opener site, its provider-specific callers, the repository
transport call site, and the only approved remote-adapter constructor. It also
requires qualification capture and the legacy context-free factory to fail
closed before provider construction.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


ALLOWED_OPENER_CALLS = {
    (
        "scripts/vnext/ai_adapter.py",
        "_open_provider_request",
        "opener.open",
    ),
}
ALLOWED_BOUNDARY_CALLERS = {
    (
        "scripts/vnext/ai_adapter.py",
        "_OpenAIResponsesTransport.complete",
    ),
    (
        "scripts/vnext/ai_adapter.py",
        "_DeepSeekChatCompletionsTransport.complete",
    ),
}
ALLOWED_REPOSITORY_TRANSPORT_CALLERS = {
    (
        "scripts/vnext/ai_adapter.py",
        "_InvocationControllerTransport.send",
    ),
    (
        "scripts/vnext/ai_adapter.py",
        "_TableContextMeasurementTransport.send",
    ),
}
ALLOWED_REMOTE_ADAPTER_CONSTRUCTORS = {
    (
        "scripts/vnext/ai_adapter.py",
        "build_invocation_controlled_transport_adapter",
    ),
    (
        "scripts/vnext/ai_adapter.py",
        "build_table_context_measurement_transport",
    ),
}
ALLOWED_EGRESS_CAPABILITY_REFERENCES = {
    ("scripts/vnext/ai_adapter.py", "_open_provider_request"),
    (
        "scripts/vnext/ai_adapter.py",
        "_ApprovedTransportAdapter._complete_repository_transport",
    ),
    (
        "scripts/vnext/ai_adapter.py",
        "_InvocationControllerTransport.send",
    ),
    (
        "scripts/vnext/ai_adapter.py",
        "_TableContextMeasurementTransport.send",
    ),
}
FAIL_CLOSED_CONSTANTS = {
    (
        "scripts/vnext/ai_adapter.py",
        "build_approved_transport_adapter",
    ): "WB3_EXECUTION_CONTEXT_REQUIRED",
    (
        "scripts/vnext/ai_adapter.py",
        "capture_deepseek_reader_response",
    ): (
        "AI_QUALIFICATION_EGRESS_NOT_ENABLED"
    ),
    (
        "tools/vnext_capture_qualification_fixture.py",
        "capture",
    ): "AI_QUALIFICATION_EGRESS_NOT_ENABLED",
}
PROVIDER_HOST_LITERALS = {"api.deepseek.com", "api.openai.com"}


class ProviderEgressGateError(ValueError):
    """Report malformed source or a provider-egress bypass."""


def _attribute_name(*, node: ast.AST) -> str:
    """Return one dotted call target name without executing source."""
    parts = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


class _CallVisitor(ast.NodeVisitor):
    """Collect security-relevant call sites with qualified symbols."""

    def __init__(self, *, relative_path: str) -> None:
        """Initialize one file-scoped visitor."""
        self.relative_path = relative_path
        self.scope: List[str] = []
        self.opener_calls: List[Tuple[str, str, str]] = []
        self.boundary_callers: List[Tuple[str, str]] = []
        self.repository_transport_callers: List[Tuple[str, str]] = []
        self.remote_adapter_constructors: List[Tuple[str, str]] = []
        self.capability_references: List[Tuple[str, str]] = []
        self.function_constants: Dict[str, set[str]] = {}
        self.provider_host_literals: List[Tuple[str, str]] = []

    def _symbol(self) -> str:
        """Return the current class/function symbol."""
        return ".".join(self.scope)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Track class ownership while visiting methods."""
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track function ownership and all stable string constants."""
        self.scope.append(node.name)
        symbol = self._symbol()
        self.function_constants[symbol] = {
            value.value
            for value in ast.walk(node)
            if isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        }
        self.generic_visit(node)
        self.scope.pop()

    def visit_Call(self, node: ast.Call) -> None:
        """Record opener, boundary, transport, and constructor calls."""
        target = _attribute_name(node=node.func)
        symbol = self._symbol()
        if target in {
            "opener.open",
            "_DEEPSEEK_OPENER.open",
            "_OPENAI_OPENER.open",
        } or (
            self.relative_path == "scripts/vnext/ai_adapter.py"
            and target in {
                "socket.socket",
                "urllib.request.urlopen",
                "urlopen",
            }
        ):
            self.opener_calls.append((self.relative_path, symbol, target))
        if target.split(".")[-1] == "_open_provider_request":
            self.boundary_callers.append((self.relative_path, symbol))
        if target.split(".")[-1] == "_complete_repository_transport":
            self.repository_transport_callers.append(
                (self.relative_path, symbol)
            )
        if target.split(".")[-1] == "_ApprovedTransportAdapter":
            self.remote_adapter_constructors.append(
                (self.relative_path, symbol)
            )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """Record every load of the private egress capability token."""
        if (
            node.id == "_RESERVATION_OWNER_EGRESS_CAPABILITY"
            and isinstance(node.ctx, ast.Load)
        ):
            self.capability_references.append(
                (self.relative_path, self._symbol())
            )

    def visit_Constant(self, node: ast.Constant) -> None:
        """Record provider host literals outside the approved module."""
        if isinstance(node.value, str) and any(
            host in node.value for host in PROVIDER_HOST_LITERALS
        ):
            self.provider_host_literals.append(
                (self.relative_path, self._symbol())
            )


def _production_python_files(*, repo_root: Path) -> List[Path]:
    """Return the exact production Python scan set."""
    files = []
    for directory_name in ("scripts", "tools"):
        directory = repo_root / directory_name
        for path in sorted(directory.rglob("*.py")):
            if path.is_symlink() or not path.is_file():
                raise ProviderEgressGateError(
                    "Production Python path is unsafe: {}".format(path)
                )
            files.append(path)
    return files


def scan_provider_opener_calls(
    *, source_text: str, relative_path: str,
) -> List[Tuple[str, str, str]]:
    """Return provider opener calls from one UTF-8 Python source string."""
    try:
        tree = ast.parse(source_text)
    except SyntaxError as error:
        raise ProviderEgressGateError(
            "Python source cannot be parsed"
        ) from error
    visitor = _CallVisitor(relative_path=relative_path)
    visitor.visit(tree)
    return visitor.opener_calls


def check_provider_egress(*, repo_root: Path) -> Dict[str, object]:
    """Scan production calls and return a content-addressed PASS result."""
    opener_calls = []
    boundary_callers = []
    repository_callers = []
    constructors = []
    capability_references = []
    function_constants: Dict[str, set[str]] = {}
    host_literals = []
    scanned_files = []
    source_bindings = []
    for path in _production_python_files(repo_root=repo_root):
        relative = path.relative_to(repo_root).as_posix()
        try:
            source_text = path.read_text(encoding="utf-8")
            tree = ast.parse(source_text)
        except (OSError, SyntaxError, UnicodeDecodeError) as error:
            raise ProviderEgressGateError(
                "Production Python cannot be parsed: {}".format(relative)
            ) from error
        visitor = _CallVisitor(relative_path=relative)
        visitor.visit(tree)
        opener_calls.extend(visitor.opener_calls)
        boundary_callers.extend(visitor.boundary_callers)
        repository_callers.extend(visitor.repository_transport_callers)
        constructors.extend(visitor.remote_adapter_constructors)
        capability_references.extend(visitor.capability_references)
        for symbol in visitor.function_constants:
            function_constants[
                "{}::{}".format(relative, symbol)
            ] = visitor.function_constants[symbol]
        host_literals.extend(visitor.provider_host_literals)
        scanned_files.append(relative)
        source_bindings.append({
            "path": relative,
            "sha256": hashlib.sha256(
                source_text.encode("utf-8")
            ).hexdigest(),
        })
    errors = []
    if set(opener_calls) != ALLOWED_OPENER_CALLS:
        errors.append("provider opener call-site exact set differs")
    if set(boundary_callers) != ALLOWED_BOUNDARY_CALLERS:
        errors.append("provider boundary caller exact set differs")
    if set(repository_callers) != ALLOWED_REPOSITORY_TRANSPORT_CALLERS:
        errors.append("repository transport caller exact set differs")
    if set(constructors) != ALLOWED_REMOTE_ADAPTER_CONSTRUCTORS:
        errors.append("remote adapter constructor exact set differs")
    if set(capability_references) != ALLOWED_EGRESS_CAPABILITY_REFERENCES:
        errors.append("egress capability reference exact set differs")
    unexpected_hosts = sorted({
        value for value in host_literals
        if value[0] not in {
            "scripts/vnext/ai_adapter.py",
            "tools/check_provider_egress.py",
            "tools/check_vnext_semantics.py",
        }
    })
    if unexpected_hosts:
        errors.append("provider host literal escaped ai_adapter.py")
    for fail_closed_key in FAIL_CLOSED_CONSTANTS:
        path, function_name = fail_closed_key
        key = "{}::{}".format(path, function_name)
        expected = FAIL_CLOSED_CONSTANTS[fail_closed_key]
        if (
            key not in function_constants
            or expected not in function_constants[key]
        ):
            errors.append("{} is not fail closed".format(function_name))
    if errors:
        raise ProviderEgressGateError("; ".join(errors))
    body = {
        "schema_version": 1,
        "record_type": "PROVIDER_EGRESS_CALL_GRAPH_GATE",
        "status": "PASS",
        "scanned_file_count": len(scanned_files),
        "scanned_source_set_hash": "sha256:" + hashlib.sha256(
            json.dumps(
                source_bindings,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "provider_opener_allowed_call_sites": [
            "{}::{}".format(path, symbol)
            for path, symbol, _target in sorted(opener_calls)
        ],
        "provider_boundary_callers": [
            "{}::{}".format(path, symbol)
            for path, symbol in sorted(boundary_callers)
        ],
        "repository_transport_callers": [
            "{}::{}".format(path, symbol)
            for path, symbol in sorted(repository_callers)
        ],
        "remote_adapter_constructors": [
            "{}::{}".format(path, symbol)
            for path, symbol in sorted(constructors)
        ],
        "egress_capability_references": [
            "{}::{}".format(path, symbol)
            for path, symbol in sorted(capability_references)
        ],
    }
    encoded = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return {
        **body,
        "gate_receipt_id": "sha256:" + hashlib.sha256(encoded).hexdigest(),
    }


def main(*, argv: Sequence[str]) -> int:
    """Run the gate and optionally write canonical JSON output."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    arguments = parser.parse_args(list(argv))
    repo_root = Path(__file__).resolve().parents[1]
    try:
        result = check_provider_egress(repo_root=repo_root)
    except ProviderEgressGateError as error:
        print(str(error))
        return 1
    rendered = json.dumps(
        result, ensure_ascii=False, sort_keys=True, indent=2,
    ) + "\n"
    if arguments.output is not None:
        output = Path(arguments.output)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
