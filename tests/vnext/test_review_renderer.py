"""Safe complete-table review rendering tests."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from tests.vnext.common import reader_response, reviewed_fixture
from vnext.render import build_review_context, render_review_markdown
from vnext.render import visible_untrusted_text


REQUIRED_CLAIMS = {
    "period_role": "current_fiscal_year",
    "property_population": "comparable",
    "operating_scope": "systemwide",
    "geography": "worldwide",
}


class ReviewRendererTest(unittest.TestCase):
    """Prove untrusted filing text stays visible but inert and hash-bound."""

    def test_markup_controls_zero_width_and_bidi_are_neutralized(self) -> None:
        """Escape active delimiters and visualize invisible code points."""
        untrusted = "<script>x</script>|`\n\u0001\u200b\u202e"
        visible = visible_untrusted_text(value=untrusted)
        self.assertNotIn("<script>", visible)
        self.assertIn("&lt;script&gt;", visible)
        self.assertIn("&#124;", visible)
        self.assertIn("&#96;", visible)
        self.assertIn("\\u000A", visible)
        self.assertIn("\\u0001", visible)
        self.assertIn("\\u200B", visible)
        self.assertIn("\\u202E", visible)

    def test_renderer_includes_every_target_table_cell(self) -> None:
        """Render the target grid with stable coordinate attributes."""
        fixture = reviewed_fixture()
        context = build_review_context(
            candidate=fixture["candidate"],
            evidence_check=fixture["evidence"],
            derived_asset=fixture["asset"],
            source_bindings=[fixture["source"]],
            spec_semantic_hash="sha256:" + "d" * 64,
            required_claims=REQUIRED_CLAIMS,
        )
        rendered = render_review_markdown(
            review_context=context["review_context"],
        )
        table = context["review_context"]["complete_target_table"]
        cell_count = sum(len(row["cells"]) for row in table["rows"])
        self.assertEqual(cell_count, rendered["text"].count("data-row="))
        self.assertIn("Comparable Systemwide Properties", rendered["text"])
        self.assertIn(
            "Untrusted data",
            rendered["text"].replace("untrusted data", "Untrusted data"),
        )

    def test_rendered_hash_changes_with_visible_context(self) -> None:
        """Bind visible unresolved claims into exact rendered bytes."""
        first = reviewed_fixture()
        second = reviewed_fixture(
            response_bytes=reader_response(
                asset=first["asset"],
                unresolved=[{"description": "period label is ambiguous"}],
            )
        )
        first_context = build_review_context(
            candidate=first["candidate"],
            evidence_check=first["evidence"],
            derived_asset=first["asset"],
            source_bindings=[first["source"]],
            spec_semantic_hash="sha256:" + "d" * 64,
            required_claims=REQUIRED_CLAIMS,
        )
        second_context = build_review_context(
            candidate=second["candidate"],
            evidence_check=second["evidence"],
            derived_asset=second["asset"],
            source_bindings=[second["source"]],
            spec_semantic_hash="sha256:" + "d" * 64,
            required_claims=REQUIRED_CLAIMS,
        )
        first_rendered = render_review_markdown(
            review_context=first_context["review_context"]
        )
        second_rendered = render_review_markdown(
            review_context=second_context["review_context"]
        )
        self.assertNotEqual(
            first_rendered["rendered_review_hash"],
            second_rendered["rendered_review_hash"],
        )

    def _assert_long_cell_is_losslessly_split_into_bounded_lines(self) -> None:
        """Keep every visible character without an unbounded physical line."""
        fixture = reviewed_fixture()
        context = build_review_context(
            candidate=fixture["candidate"],
            evidence_check=fixture["evidence"],
            derived_asset=fixture["asset"],
            source_bindings=[fixture["source"]],
            spec_semantic_hash="sha256:" + "d" * 64,
            required_claims=REQUIRED_CLAIMS,
        )["review_context"]
        baseline_z_count = render_review_markdown(
            review_context=context,
        )["text"].count("z")
        replaced_z_count = str(
            context["complete_target_table"]["rows"][0]["cells"][0][
                "text"
            ]
        ).count("z")
        context["complete_target_table"]["rows"][0]["cells"][0][
            "text"
        ] = "z" * 20000
        limits = SimpleNamespace(
            max_html_bytes=4096,
            max_tables=4,
            max_rows_per_table=8,
            max_columns_per_table=8,
            max_cells_per_table=64,
            max_total_cells=64,
            max_cell_text_chars=30000,
            max_table_text_chars=60000,
            max_total_table_text_chars=60000,
            max_expanded_text_chars=60000,
            max_rendered_review_bytes=65536,
            max_rendered_line_bytes=1024,
        )
        with mock.patch(
            "vnext.render.RESOURCE_LIMITS", limits, create=True,
        ):
            rendered = render_review_markdown(review_context=context)
        self.assertTrue(
            all(
                len(line.encode("utf-8")) <= limits.max_rendered_line_bytes
                for line in rendered["text"].splitlines()
            )
        )
        self.assertEqual(
            baseline_z_count - replaced_z_count + 20000,
            rendered["text"].count("z"),
        )

    def _assert_total_review_budget_fails_without_truncation(self) -> None:
        """Reject a review that cannot be represented within total budget."""
        fixture = reviewed_fixture()
        context = build_review_context(
            candidate=fixture["candidate"],
            evidence_check=fixture["evidence"],
            derived_asset=fixture["asset"],
            source_bindings=[fixture["source"]],
            spec_semantic_hash="sha256:" + "d" * 64,
            required_claims=REQUIRED_CLAIMS,
        )["review_context"]
        limits = SimpleNamespace(
            max_html_bytes=4096,
            max_tables=4,
            max_rows_per_table=8,
            max_columns_per_table=8,
            max_cells_per_table=64,
            max_total_cells=64,
            max_cell_text_chars=1024,
            max_table_text_chars=4096,
            max_total_table_text_chars=8192,
            max_expanded_text_chars=8192,
            max_rendered_review_bytes=32,
            max_rendered_line_bytes=8192,
        )
        with mock.patch(
            "vnext.render.RESOURCE_LIMITS", limits, create=True,
        ):
            with self.assertRaisesRegex(
                ValueError, "resource budget.*rendered bytes"
            ):
                render_review_markdown(review_context=context)

    def test_review_renderer_resource_budget_matrix(self) -> None:
        """Cover lossless physical wrapping and total-output rejection."""
        self._assert_long_cell_is_losslessly_split_into_bounded_lines()
        self._assert_total_review_budget_fails_without_truncation()


if __name__ == "__main__":
    unittest.main()
