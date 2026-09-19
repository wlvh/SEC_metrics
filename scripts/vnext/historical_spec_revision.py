"""Compile a revised text MetricSpec without rewriting the compiler's bytes.

Purpose:
    Raising a ``TEXT_V1`` bound is a MetricSpec revision, and this repository
    already has a shape for that: a successor Spec file, the predecessor kept
    byte-identical. What does not fit is where the *ceiling* lives. A Spec may
    declare at most 64 items, and that number is in ``scripts/vnext/specs.py``,
    whose bytes fourteen frozen Requirement generations name in their execution
    authority. Raising it there fails all of them closed - measured, not
    inferred: opening a native request-construction scope bound to
    ``issue_28_v14`` against a tree carrying the raised ceiling raises
    ``NATIVE_REQUEST_CONSTRUCTION_RULE_CHANGED:scripts/vnext/specs.py`` and the
    whole continuous semantic-call route stops.

    So this generation carries the raised ceiling itself, the same way
    ``historical_text_results`` carries the section-boundary rule that
    ``text_coverage`` cannot. The frozen compiler still does every piece of
    parsing and validation. This module adds exactly two things: the successor
    ceiling, and a mechanical proof that the revision moved one number.

    That proof is the point. Substituting a value into a compiled artifact
    would hide any *other* defect in the successor file, because the frozen
    compiler rejects the whole file with one message and cannot say which check
    failed. So the successor's front matter is compiled through the frozen
    compiler twice over: once with its own declared bound replaced by the
    predecessor's, which must produce an artifact exactly equal to the
    predecessor's, and only then is the declared bound put back and the hashes
    recomputed with the frozen hashing functions. A successor that changed its
    method, its sections, its claims or a single word of its semantics fails
    the equality rather than compiling.

Call relationships:
    ``historical_results`` compiles the D02 route's Spec through this. The Run
    factory reaches the same path by Requirement, so a frozen Run replays the
    Spec it declared. Nothing here grants execution, opens a source or reads a
    filing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

from .canonical import content_hash, execution_semantics_hash
from .specs import (
    FRONT_MATTER_SEPARATOR,
    SEMANTIC_SET_PATHS,
    SpecError,
    compile_spec,
    parse_spec_document,
)

# The successor ceiling on what a TEXT_V1 Spec may declare, and the predecessor
# each revised Spec is read against. 192 is measured rather than chosen: across
# the nine annual filings this repository holds, one D02 excerpt carries 341 to
# 1,422 characters once the renderer's separators are counted the way
# max_text_chars counts them, so a filing spending the whole 64,000-character
# budget needs 45 to 187 items depending only on how its filer breaks
# paragraphs. 192 is the sparsest of those rounded up to three times the
# original bound. The character bound is untouched and stays the operative
# limit on how much text a result may carry.
SUCCESSOR_MAX_ITEMS = 192
REVISED_TEXT_SPECS = {
    "catalog/r6/D02_legal_disclosures_v2.md": "catalog/r6/D02_legal_disclosures_v1.md",
}
# The one front-matter value a revision handled here may move. Anything else is
# a different Spec, not a revision of this one.
REVISED_KEY = ("text_policy", "max_items")


class SpecRevisionError(SpecError):
    """A successor Spec is not a bound revision of its declared predecessor."""


def _read(*, path: Path) -> Tuple[Dict[str, object], str]:
    """Parse one Spec file without compiling it.

    Args:
        path: MetricSpec Markdown path.

    Returns:
        Front-matter mapping and human-readable body.

    Raises:
        SpecRevisionError: When the path is not a regular UTF-8 file.
    """
    if path.is_symlink() or not path.is_file():
        raise SpecRevisionError("MetricSpec must be a regular file: {}".format(path))
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise SpecRevisionError("MetricSpec must be UTF-8") from error
    return parse_spec_document(text=text)


def _declared_bound(*, front: Mapping[str, object], path: Path) -> int:
    """Return the item bound one Spec's front matter declares.

    Args:
        front: Parsed front matter.
        path: Source path, used only for diagnostics.

    Returns:
        The declared ``max_items``.

    Raises:
        SpecRevisionError: When no usable integer bound is declared.
    """
    policy = front.get(REVISED_KEY[0])
    if type(policy) is not dict or REVISED_KEY[1] not in policy:
        raise SpecRevisionError(
            "Revised Spec declares no {}: {}".format(".".join(REVISED_KEY), path)
        )
    bound = policy[REVISED_KEY[1]]
    if type(bound) is not int or not 1 <= bound <= SUCCESSOR_MAX_ITEMS:
        raise SpecRevisionError(
            "Revised Spec {} must be an integer in 1..{}: {}".format(
                ".".join(REVISED_KEY), SUCCESSOR_MAX_ITEMS, path
            )
        )
    return bound


def _document(*, front: Mapping[str, object], body: str) -> str:
    """Re-emit one parsed Spec as a document the frozen compiler can read.

    Args:
        front: Front-matter mapping to serialise.
        body: Human-readable body, carried through unchanged.

    Returns:
        A complete MetricSpec document.

    Why:
        The frozen compiler reads the parsed front matter, never its layout, so
        re-serialising is semantically neutral. It is done here rather than by
        editing the file's text because the comparison below is between
        compiled artifacts, where formatting cannot reach.
    """
    return "\n".join(
        (FRONT_MATTER_SEPARATOR, json.dumps(front, ensure_ascii=False, indent=1),
         FRONT_MATTER_SEPARATOR, body)
    )


def compile_revised_text_spec(
    *,
    successor_path: Path,
    predecessor_path: Path,
    dependency_specs: Optional[Mapping[str, Mapping[str, object]]] = None,
) -> Dict[str, object]:
    """Compile a successor Spec that raises one bound above the frozen ceiling.

    Args:
        successor_path: The revised Spec file.
        predecessor_path: The Spec it revises, whose bytes are unchanged.
        dependency_specs: Already compiled dependency mappings.

    Returns:
        The same shape :func:`specs.compile_spec` returns, with the successor's
        declared bound and hashes recomputed over it.

    Raises:
        SpecRevisionError: When the successor differs from its predecessor
            anywhere except the one permitted bound.
        SpecError: From the frozen compiler, for anything it already rejects.
    """
    successor_front, successor_body = _read(path=successor_path)
    predecessor_front, _ = _read(path=predecessor_path)
    declared = _declared_bound(front=successor_front, path=successor_path)
    inherited = _declared_bound(front=predecessor_front, path=predecessor_path)

    # The successor's own front matter, compiled through the frozen compiler
    # with the one permitted value held at the predecessor's. Everything the
    # frozen compiler checks is therefore checked against the successor's real
    # content, and the equality below states that nothing else moved.
    probe_front = dict(successor_front)
    probe_front[REVISED_KEY[0]] = {**successor_front[REVISED_KEY[0]],
                                   REVISED_KEY[1]: inherited}
    probe = compile_spec(
        text=_document(front=probe_front, body=successor_body),
        dependency_specs=dependency_specs,
    )
    predecessor = compile_spec(
        text=_document(front=dict(predecessor_front), body=successor_body),
        dependency_specs=dependency_specs,
    )
    if probe["compiled"] != predecessor["compiled"]:
        differing = sorted(
            key for key in set(probe["compiled"]) | set(predecessor["compiled"])
            if probe["compiled"].get(key) != predecessor["compiled"].get(key)
        )
        raise SpecRevisionError(
            "Revised Spec changes more than {}: {}".format(
                ".".join(REVISED_KEY), ",".join(differing)
            )
        )
    if probe["prompt_bundle"] != predecessor["prompt_bundle"]:
        raise SpecRevisionError(
            "Revised Spec changes its prompt bundle: {}".format(successor_path)
        )

    compiled = dict(probe["compiled"])
    compiled[REVISED_KEY[0]] = {**compiled[REVISED_KEY[0]], REVISED_KEY[1]: declared}
    semantic_hash = content_hash(value=compiled, set_paths=SEMANTIC_SET_PATHS)
    prompt_bundle = {**probe["prompt_bundle"], "spec_semantic_hash": semantic_hash}
    closure_hash = content_hash(
        value={
            "spec_semantic_hash": semantic_hash,
            "dependency_closure_hashes": [
                (dependency_specs or {})[dependency]["spec_closure_hash"]
                for dependency in compiled["dependencies"]
            ],
            "execution_semantics_hash": execution_semantics_hash(),
        }
    )
    return {
        "compiled": compiled,
        "spec_semantic_hash": semantic_hash,
        "prompt_bundle_hash": content_hash(value=prompt_bundle),
        "prompt_bundle": prompt_bundle,
        "spec_closure_hash": closure_hash,
        "body": successor_body,
    }


def compile_historical_spec_file(
    *,
    repo_root: Path,
    repo_relative_path: str,
    dependency_specs: Optional[Mapping[str, Mapping[str, object]]] = None,
) -> Dict[str, object]:
    """Compile one Spec this generation uses, revised or not.

    Args:
        repo_root: Repository root the relative path resolves against.
        repo_relative_path: Spec path as the Run manifest declares it.
        dependency_specs: Already compiled dependency mappings.

    Returns:
        Result from :func:`compile_revised_text_spec` for a registered
        revision, otherwise from the frozen :func:`specs.compile_spec_file`.
    """
    predecessor = REVISED_TEXT_SPECS.get(repo_relative_path)
    if predecessor is None:
        from .specs import compile_spec_file
        return compile_spec_file(path=repo_root / repo_relative_path,
                                 dependency_specs=dependency_specs)
    return compile_revised_text_spec(
        successor_path=repo_root / repo_relative_path,
        predecessor_path=repo_root / predecessor,
        dependency_specs=dependency_specs,
    )
