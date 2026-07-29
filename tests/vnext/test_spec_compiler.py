"""Bounded MetricSpec compiler, traits, and semantic hash tests."""

from __future__ import annotations

import ast
import json
import unittest

from tests.vnext.common import REPO_ROOT, compiled_specs
from vnext.specs import SpecError, compile_spec, parse_spec_document
from vnext.traits import derive_company_traits, repository_company_ciks


class SpecCompilerTest(unittest.TestCase):
    """Prove defaults, ordering, closure, traits, and AST limits."""

    def test_catalog_compiles_and_b03_closes_over_b01(self) -> None:
        """Compile every Phase 1 Spec and bind the B01 dependency closure."""
        specs = compiled_specs()
        source = (
            REPO_ROOT / "catalog/metrics/B03_ebitda_margin.md"
        ).read_text(encoding="utf-8")
        changed_dependency = dict(specs["B01"])
        changed_dependency["spec_closure_hash"] = "sha256:" + ("0" * 64)
        changed = compile_spec(
            text=source, dependency_specs={"B01": changed_dependency},
        )
        self.assertNotEqual(
            specs["B03"]["spec_closure_hash"], changed["spec_closure_hash"],
        )
        self.assertEqual(
            28,
            specs["B03"]["compiled"]["numeric_policy"]["decimal_precision"],
        )

    def test_dependency_compiled_semantics_must_match_its_hash(self) -> None:
        """Reject altered dependency behavior hidden behind an old closure."""
        specs = compiled_specs()
        source = (
            REPO_ROOT / "catalog/metrics/B03_ebitda_margin.md"
        ).read_text(encoding="utf-8")
        changed_dependency = json.loads(json.dumps(specs["B01"]))
        changed_dependency["compiled"]["numeric_policy"][
            "decimal_precision"
        ] = 9
        with self.assertRaisesRegex(SpecError, "semantic hash"):
            compile_spec(
                text=source,
                dependency_specs={"B01": changed_dependency},
            )

    def test_human_body_does_not_change_semantic_hash(self) -> None:
        """Keep explanation-only edits out of executable semantic identity."""
        source = (REPO_ROOT / "catalog/metrics/B01_revenue.md").read_text(
            encoding="utf-8"
        )
        original = compile_spec(text=source, dependency_specs={})
        changed = compile_spec(
            text=source + "\nExplanation only.\n", dependency_specs={},
        )
        self.assertEqual(
            original["spec_semantic_hash"], changed["spec_semantic_hash"],
        )

    def test_order_and_unknown_guard_change_or_fail(self) -> None:
        """Bind choose-first order and reject undeclared executable guards."""
        source = (
            REPO_ROOT / "catalog/metrics/B03_ebitda_margin.md"
        ).read_text(encoding="utf-8")
        specs = compiled_specs()
        original = compile_spec(
            text=source, dependency_specs={"B01": specs["B01"]},
        )
        front_end = source.index("---", 4)
        front = json.loads(source[4:front_end])
        front["inputs"]["operating_income"]["choose_first"].reverse()
        mutated = "---\n" + json.dumps(front) + "\n---\nbody"
        reordered = compile_spec(
            text=mutated, dependency_specs={"B01": specs["B01"]},
        )
        self.assertNotEqual(
            original["spec_semantic_hash"], reordered["spec_semantic_hash"],
        )
        front["top_level_guards"].append("business_magic")
        invalid = "---\n" + json.dumps(front) + "\n---\nbody"
        with self.assertRaises(SpecError):
            compile_spec(
                text=invalid, dependency_specs={"B01": specs["B01"]},
            )

    def test_depth_node_cycle_and_cardinality_limits_fail_closed(self) -> None:
        """Reject each bounded-DSL limit instead of guessing a fallback."""
        source = (REPO_ROOT / "catalog/metrics/B01_revenue.md").read_text(
            encoding="utf-8"
        )
        front, _body = parse_spec_document(text=source)

        # A deeply nested expression is valid in shape but exceeds the frozen
        # runtime resource bound, so compilation must stop before execution.
        deep = dict(front)
        expression: object = "revenue"
        for _index in range(40):
            expression = {"op": "add", "args": [expression, "1"]}
        deep["formula"] = expression
        with self.assertRaisesRegex(SpecError, "depth 32"):
            compile_spec(
                text="---\n" + json.dumps(deep) + "\n---\n",
                dependency_specs={},
            )

        # Unique strings avoid the duplicate guard and exercise the independent
        # 256-node cap over the compiled semantic object.
        wide = dict(front)
        wide["forbidden_confusions"] = [
            "confusion_{}".format(index) for index in range(260)
        ]
        with self.assertRaisesRegex(SpecError, "256 nodes"):
            compile_spec(
                text="---\n" + json.dumps(wide) + "\n---\n",
                dependency_specs={},
            )

        cyclic = dict(front)
        with self.assertRaisesRegex(SpecError, "dependency cycle"):
            compile_spec(
                text="---\n" + json.dumps(cyclic) + "\n---\n",
                dependency_specs={},
                stack=("B01",),
            )

        invalid_cardinality = dict(front)
        invalid_cardinality["inputs"] = json.loads(json.dumps(front["inputs"]))
        invalid_cardinality["inputs"]["revenue"]["structured_role"][
            "cardinality"
        ] = "many"
        with self.assertRaisesRegex(SpecError, "cardinality"):
            compile_spec(
                text=("---\n" + json.dumps(invalid_cardinality) + "\n---\n"),
                dependency_specs={},
            )

    def test_company_traits_are_registry_projection(self) -> None:
        """Derive traits from the canonical registry without company copies."""
        traits = derive_company_traits(
            registry_path=REPO_ROOT / "config/company_registry.csv",
            applicability_path=REPO_ROOT / "config/metric_applicability.yaml",
            trait_catalog_path=REPO_ROOT / "catalog/company_traits.yaml",
        )
        self.assertIn("lodging", traits["marriott_international"])
        self.assertEqual(["financial"], traits["jpmorgan_chase"])
        self.assertEqual(
            ["2041610", "813828"],
            repository_company_ciks(
                repo_root=REPO_ROOT,
                company_id="paramount_skydance_paramount_global",
            ),
        )

    def test_python_39_forbidden_api_surface_is_absent(self) -> None:
        """Keep executable source within the declared Python 3.9 floor."""
        forbidden = (
            "datetime.UTC",
            "hashlib.file_digest",
            "tomllib",
            "dataclass(slots=True)",
        )
        for path in sorted((REPO_ROOT / "scripts/vnext").glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                with self.subTest(path=path, token=token):
                    self.assertNotIn(token, text)
            with self.subTest(path=path, syntax="match"):
                tree = ast.parse(text, filename=str(path))
                self.assertFalse(
                    any(
                        type(node).__name__ == "Match"
                        for node in ast.walk(tree)
                    )
                )


if __name__ == "__main__":
    unittest.main()
