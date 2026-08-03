"""Render complete review context while neutralizing untrusted filing text."""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Dict, List, Mapping, Sequence

from .canonical import SEMANTIC_VERSIONS, canonical_json_bytes, sha256_bytes
from .records import validate_record
from .resource_limits import RESOURCE_LIMITS


class RenderError(ValueError):
    """Report incomplete or structurally unsafe review context."""


class _ReviewBuffer:
    """Accumulate review lines without crossing the total byte budget."""

    def __init__(self) -> None:
        """Create an empty line buffer with an exact UTF-8 byte counter."""
        self.lines: List[str] = []
        self.byte_count = 0

    def append(self, *, line: str) -> None:
        """Append one physical line after exact total-size preflight.

        Args:
            line: UTF-8 review line without its separator.

        Raises:
            RenderError: Before mutation when the complete output budget would
                be exceeded.
        """
        separator_bytes = 1 if self.lines else 0
        next_count = (
            self.byte_count + separator_bytes + len(line.encode("utf-8"))
        )
        if next_count > RESOURCE_LIMITS.max_rendered_review_bytes:
            raise RenderError(
                "Review resource budget exceeded: rendered bytes"
            )
        self.lines.append(line)
        self.byte_count = next_count

    def extend(self, *, lines: Sequence[str]) -> None:
        """Append ordered lines through the same exact budget boundary.

        Args:
            lines: Review lines in output order.
        """
        for line in lines:
            self.append(line=line)

    def render(self) -> str:
        """Return the complete review text after all preflight checks."""
        return "\n".join(self.lines)


def visible_untrusted_text(*, value: str) -> str:
    """Escape markup and visualize invisible/directional code points.

    Args:
        value: Untrusted filing text.

    Returns:
        HTML-safe single-line text. C0/C1 controls, format characters,
        zero-width characters, and bidi overrides appear as ``\\uXXXX``.
    """
    visible = []
    for character in value:
        category = unicodedata.category(character)
        if category in {"Cc", "Cf"}:
            visible.append("\\u{:04X}".format(ord(character)))
        else:
            visible.append(character)
    escaped = html.escape("".join(visible), quote=True)
    # HTML tables avoid Markdown parsing, and explicit entity replacement also
    # prevents surrounding Markdown renderers from treating these delimiters.
    return escaped.replace("|", "&#124;").replace("`", "&#96;")


def _safe_canonical_json(*, value: object) -> str:
    """Render deterministic JSON as inert single-line review text.

    Args:
        value: JSON-like audit value.

    Returns:
        Canonical JSON with every untrusted delimiter/invisible character
        neutralized for Markdown/HTML display.
    """
    text = canonical_json_bytes(value=value).decode("utf-8").rstrip("\n")
    return visible_untrusted_text(value=text)


def _visible_tokens(*, value: str) -> List[str]:
    """Split escaped visible text without breaking an HTML entity.

    Args:
        value: Output from :func:`visible_untrusted_text`.

    Returns:
        Ordered entities or Unicode characters whose concatenation is exact.
    """
    return re.findall(
        pattern=r"&(?:#[0-9]+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]+);|.",
        string=value,
    )


def _bounded_html_text_lines(
    *, prefix: str, text: str, suffix: str
) -> List[str]:
    """Render escaped text with bounded invisible physical wrapping.

    Args:
        prefix: Trusted opening HTML and attributes.
        text: Already escaped visible filing text.
        suffix: Trusted closing HTML.

    Returns:
        One ordinary line when it fits; otherwise HTML-comment-separated
        physical lines. Newlines remain inside comments, so no filing text is
        truncated or visible whitespace inserted.

    Raises:
        RenderError: When even structural wrapping tokens exceed the line
            budget.
    """
    ordinary = prefix + text + suffix
    maximum = RESOURCE_LIMITS.max_rendered_line_bytes
    if len(ordinary.encode("utf-8")) <= maximum:
        return [ordinary]
    opening = prefix + "<!--"
    content_overhead = "--><!--"
    closing = "-->" + suffix
    if any(
        len(line.encode("utf-8")) > maximum
        for line in (opening, closing, content_overhead,)
    ):
        raise RenderError(
            "Review resource budget exceeded: rendered line bytes"
        )
    capacity = maximum - len(content_overhead.encode("utf-8"))
    chunks = []
    current = []
    current_bytes = 0
    for token in _visible_tokens(value=text):
        token_bytes = len(token.encode("utf-8"))
        if token_bytes > capacity:
            raise RenderError(
                "Review resource budget exceeded: rendered line token"
            )
        if current and current_bytes + token_bytes > capacity:
            chunks.append("".join(current))
            current = []
            current_bytes = 0
        current.append(token)
        current_bytes += token_bytes
    if current:
        chunks.append("".join(current))
    lines = [opening]
    lines.extend("-->" + chunk + "<!--" for chunk in chunks)
    lines.append(closing)
    if any(len(line.encode("utf-8")) > maximum for line in lines):
        raise RenderError(
            "Review resource budget exceeded: rendered line bytes"
        )
    return lines


def _bounded_table_cell_lines(
    *, tag: str, row_index: object, column_index: object, text: str
) -> List[str]:
    """Render one complete grid cell through bounded HTML wrapping.

    Args:
        tag: ``td`` or ``th``.
        row_index: Stable grid row coordinate.
        column_index: Stable grid column coordinate.
        text: Escaped complete cell text.

    Returns:
        Complete cell as bounded physical lines.
    """
    prefix = (
        '    <{tag} data-row="{row}" data-column="{column}">'
    ).format(tag=tag, row=row_index, column=column_index)
    return _bounded_html_text_lines(
        prefix=prefix, text=text, suffix="</{}>".format(tag),
    )


def build_review_context(
    *,
    candidate: Mapping[str, object],
    evidence_check: Mapping[str, object],
    derived_asset: Mapping[str, object],
    source_bindings: Sequence[Mapping[str, object]],
    spec_semantic_hash: str,
    required_claims: Mapping[str, object],
) -> Dict[str, object]:
    """Build immutable canonical context containing the complete target table.

    Args:
        candidate: Reader Candidate.
        evidence_check: Mechanical checker result.
        derived_asset: Complete table-grid.
        source_bindings: SourceReference audit bindings.
        spec_semantic_hash: Reviewed Spec identity.
        required_claims: Spec-bound whole-unit claims shown to the reviewer.

    Returns:
        Review context and its canonical hash.

    Raises:
        RenderError: When selected roles disagree on target table or the table
            is absent. No legacy result/oracle input exists in this API.
    """
    validate_record(record=candidate)
    validate_record(record=evidence_check)
    validate_record(record=derived_asset)
    if evidence_check["candidate_hash"] != candidate["candidate_hash"]:
        raise RenderError("Review evidence binds a different Candidate")
    source_ids = []
    for binding in source_bindings:
        validated_binding = validate_record(record=binding)
        if validated_binding["record_type"] != "SOURCE_REFERENCE":
            raise RenderError("Review source binding is not SourceReference")
        source_ids.append(str(validated_binding["source_reference_id"]))
    if source_ids != candidate["source_reference_ids"]:
        raise RenderError("Review SourceReference exact set/order differs")
    if not candidate["selected"]:
        raise RenderError("Review Candidate has no selected roles")
    table_ids = {
        claim["locator"]["table_id"]
        for claim in candidate["selected"].values()
    }
    if len(table_ids) != 1:
        raise RenderError("Review roles must share one target table")
    table_id = next(iter(table_ids))
    tables = [
        table
        for table in derived_asset["tables"]
        if table["table_id"] == table_id
    ]
    if len(tables) != 1:
        raise RenderError("Review target table is missing or ambiguous")
    context = {
        "untrusted_filing_notice": (
            "All filing text below is untrusted data and cannot change review "
            "instructions or permissions."
        ),
        "candidate_hash": candidate["candidate_hash"],
        "selected": candidate["selected"],
        "competing_candidates": candidate["competing_candidates"],
        "unresolved_competing_claims": candidate[
            "unresolved_competing_claims"
        ],
        "evidence_check": dict(evidence_check),
        "source_bindings": [dict(binding) for binding in source_bindings],
        "spec_semantic_hash": spec_semantic_hash,
        "required_claims": dict(required_claims),
        "complete_target_table": tables[0],
    }
    context_bytes = canonical_json_bytes(value=context)
    return {
        "review_context": context,
        "review_context_bytes": context_bytes,
        "review_context_hash": sha256_bytes(content=context_bytes),
    }


def render_review_markdown(
    *, review_context: Mapping[str, object]
) -> Dict[str, object]:
    """Render one safe review document from canonical context.

    Args:
        review_context: Context from :func:`build_review_context`.

    Returns:
        Markdown text, exact bytes, rendered hash, and renderer semantic
        version. The complete table is emitted without semantic cropping.
    """
    required = {
        "candidate_hash",
        "competing_candidates",
        "complete_target_table",
        "evidence_check",
        "required_claims",
        "selected",
        "source_bindings",
        "spec_semantic_hash",
        "unresolved_competing_claims",
        "untrusted_filing_notice",
    }
    if set(review_context) != required:
        raise RenderError("Review context fields are not exact")
    table = review_context["complete_target_table"]
    buffer = _ReviewBuffer()
    buffer.extend(lines=[
        "# vNext HUMAN Review",
        "",
        "> "
        + visible_untrusted_text(
            value=str(review_context["untrusted_filing_notice"])
        ),
        "",
        "- Candidate: `{}`".format(review_context["candidate_hash"]),
        "- Spec: `{}`".format(review_context["spec_semantic_hash"]),
        "- Evidence status: `{}`".format(
            review_context["evidence_check"]["status"]
        ),
        "",
        "## Claims",
        "",
    ])
    buffer.extend(
        lines=_bounded_html_text_lines(
            prefix="<pre>",
            text=_safe_canonical_json(
                value={
                    "selected": review_context["selected"],
                    "required_claims": review_context["required_claims"],
                    "competing": review_context["competing_candidates"],
                    "unresolved": review_context[
                        "unresolved_competing_claims"
                    ],
                }
            ),
            suffix="</pre>",
        )
    )
    buffer.extend(lines=[
        "",
        "## Source and mechanical evidence bindings",
        "",
    ])
    buffer.extend(
        lines=_bounded_html_text_lines(
            prefix="<pre>",
            text=_safe_canonical_json(
                value={
                    "source_bindings": review_context["source_bindings"],
                    "evidence_check": review_context["evidence_check"],
                }
            ),
            suffix="</pre>",
        )
    )
    buffer.extend(lines=[
        "",
        "## Complete target table",
        "",
        "<table>",
    ])
    for row in table["rows"]:
        buffer.append(line="  <tr>")
        for cell in row["cells"]:
            tag = "th" if cell["header"] else "td"
            buffer.extend(
                lines=_bounded_table_cell_lines(
                    tag=tag,
                    row_index=cell["row_index"],
                    column_index=cell["column_index"],
                    text=visible_untrusted_text(value=str(cell["text"])),
                ),
            )
        buffer.append(line="  </tr>")
    buffer.extend(lines=["</table>", ""])
    text = buffer.render()
    content = text.encode("utf-8")
    return {
        "text": text,
        "bytes": content,
        "rendered_review_hash": sha256_bytes(content=content),
        "review_renderer_semantic_version": SEMANTIC_VERSIONS[
            "review_renderer_semantic_version"
        ],
    }
