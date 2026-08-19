"""Verify the frozen Issue #15 WB-1 authority transfer.

The positive test loads both explicit Requirement schemas, compares all 13
historical Decision records by canonical hash, recomputes the matrix baseline,
and checks every frozen ``file::symbol`` producer locator.  Negative tests
prove Contract, receipt, parent-disposition, and producer-scope drift fail
closed without modifying the immutable parent fixture.
"""

from __future__ import annotations

import ast
import copy
import csv
import json
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from typing import Dict, Set

from tests.vnext.common import REPO_ROOT
from vnext.canonical import content_hash, sha256_file
from vnext.publication import PublicationView, ROOT_MIRROR_RELATIVE_PATHS
from vnext.publication import verify_publication_bundle
from vnext.requirements import (
    ISSUE_15_BASE_PIPELINE_SHA256,
    ISSUE_15_EXPECTED_PRODUCER_EXACT_SET_HASH,
    ISSUE_15_EXPECTED_PRODUCER_RECORD_SET_HASH,
    ISSUE_15_EXPECTED_SCOPE_EVIDENCE_HASH,
    ISSUE_15_EXPECTED_SEMANTIC_RECORD_SET_HASH,
    ISSUE_15_POST_FREEZE_DECISION_EVIDENCE,
    ISSUE_15_POST_FREEZE_EFFECTIVE_TIP_HASHES,
    RequirementError,
    load_requirement_snapshot,
)


PARENT_DIR = REPO_ROOT / "requirements" / "ai_first_v3_3_1"
ISSUE_15_DIR = REPO_ROOT / "requirements" / "issue_15_v1"
CONTRACT_SHA256 = "9a368d3cf7381d29adb0a1b041e882f74c1137b6e16d266300ef4ec21b9e19ec"
FOUNDATION_SOURCE_COMMIT = "f1cc44342e6814522ec2688cf3674f7ec442be8d"
FOUNDATION_MERGE_COMMIT = "4d02db6a474f93eec9e058d780e206b4504ab24d"


def frozen_issue15_artifact_path(*, relative: str) -> Path:
    """Resolve one WB-1 baseline artifact before or after formal activation.

    Args:
        relative: Repository-relative frozen artifact path.

    Returns:
        Root path without an active pointer, otherwise the same bytes inside
        the active successor's verified predecessor A.
    """
    pointer_path = REPO_ROOT / "outputs" / "active_publication.json"
    if not pointer_path.exists():
        return REPO_ROOT / relative
    active = PublicationView.open(publication_root=REPO_ROOT)
    predecessor_id = active.manifest["previous_publication_id"]
    predecessor_dir = None
    while predecessor_id is not None:
        candidate = (
            REPO_ROOT / "outputs" / "publications" / str(predecessor_id)
        )
        manifest = verify_publication_bundle(bundle_dir=candidate)
        if (candidate / "internal/legacy_baseline_import.json").is_file():
            predecessor_dir = candidate
            break
        predecessor_id = manifest["previous_publication_id"]
    if predecessor_dir is None:
        raise AssertionError("Active publication chain lacks legacy A")
    root_to_bundle = {
        root_relative: bundle_relative
        for bundle_relative, root_relative in ROOT_MIRROR_RELATIVE_PATHS.items()
    }
    if relative in root_to_bundle:
        return predecessor_dir / root_to_bundle[relative]
    return predecessor_dir / "internal" / "legacy_baseline_support" / relative


def read_json(*, path: Path) -> Dict[str, object]:
    """Read one trusted test JSON object with explicit UTF-8 decoding.

    Args:
        path: Existing Requirement JSON file.

    Returns:
        Parsed root object.
    """
    value = json.loads(s=path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("Test JSON root must be an object")
    return value


def module_symbols(*, path: Path) -> Set[str]:
    """Return top-level function, class, and assignment names in one module.

    Args:
        path: Existing UTF-8 Python source file.

    Returns:
        Top-level symbols addressable by the inventory's ``file::symbol``
        convention.
    """
    tree = ast.parse(source=path.read_text(encoding="utf-8"))
    symbols: Set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    symbols.add(target.id)
                    if target.id == "RETIRED_LEGACY_PRODUCER_NAMES":
                        symbols.update(
                            child.value
                            for child in ast.walk(node.value)
                            if isinstance(child, ast.Constant)
                            and isinstance(child.value, str)
                        )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            symbols.add(node.target.id)
    return symbols


def module_functions(*, path: Path) -> Dict[str, ast.FunctionDef]:
    """Return top-level function AST nodes keyed by exact symbol name.

    Args:
        path: Existing UTF-8 Python source file.

    Returns:
        Function definitions used by callsite and transitive-edge checks.
    """
    tree = ast.parse(source=path.read_text(encoding="utf-8"))
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def call_at_site(*, function: ast.FunctionDef, callee: str, call_site: str) -> ast.Call:
    """Return the unique direct call at one frozen line/column locator.

    Args:
        function: Caller function AST node.
        callee: Expected unqualified callee name.
        call_site: Decimal ``line:column`` source locator.

    Returns:
        Exact matching call node.
    """
    line_text, column_text = call_site.split(":", maxsplit=1)
    matches = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == callee
        and node.lineno == int(line_text)
        and node.col_offset == int(column_text)
    ]
    if len(matches) != 1:
        raise AssertionError(
            "Callsite must resolve exactly once: {}::{}@{}".format(
                function.name, callee, call_site
            )
        )
    return matches[0]


def call_keyword(*, call: ast.Call, keyword: str) -> ast.AST:
    """Return one required keyword expression from a frozen callsite.

    Args:
        call: Parsed function call.
        keyword: Required keyword argument name.

    Returns:
        AST expression bound to the keyword.
    """
    matches = [item.value for item in call.keywords if item.arg == keyword]
    if len(matches) != 1:
        raise AssertionError("Call keyword must exist exactly once: " + keyword)
    return matches[0]


def assignment_value(*, path: Path, symbol: str) -> ast.AST:
    """Return the unique top-level assignment value for one constant.

    Args:
        path: Existing UTF-8 Python source file.
        symbol: Required assignment target name.

    Returns:
        Assigned AST expression.
    """
    tree = ast.parse(source=path.read_text(encoding="utf-8"))
    matches = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == symbol
            for target in node.targets
        ):
            matches.append(node.value)
    if len(matches) != 1:
        raise AssertionError("Assignment must exist exactly once: " + symbol)
    return matches[0]


def copy_test_repository(*, temp_dir: str) -> Path:
    """Copy both Requirement snapshots and every bound foundation receipt.

    Args:
        temp_dir: Empty temporary directory used as a repository root.

    Returns:
        Copied ``requirements/issue_15_v1`` directory.
    """
    repository_root = Path(temp_dir)
    requirements_dir = repository_root / "requirements"
    parent_copy = requirements_dir / "ai_first_v3_3_1"
    issue_copy = requirements_dir / "issue_15_v1"
    shutil.copytree(src=PARENT_DIR, dst=parent_copy)
    shutil.copytree(src=ISSUE_15_DIR, dst=issue_copy)
    baseline = read_json(path=ISSUE_15_DIR / "baseline_manifest.json")
    for relative in baseline["runtime_authority_files"]:
        destination = repository_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src=REPO_ROOT / relative, dst=destination)
    company_registry = repository_root / "config" / "company_registry.csv"
    shutil.copy2(
        src=REPO_ROOT / "config" / "company_registry.csv",
        dst=company_registry,
    )
    foundation = read_json(path=ISSUE_15_DIR / "foundation_verification_receipt.json")
    for binding in foundation["receipt_bindings"]:
        relative = Path(binding["path"])
        destination = repository_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src=REPO_ROOT / relative, dst=destination)
    return issue_copy


def write_json(*, path: Path, value: Dict[str, object]) -> None:
    """Write one deterministic test JSON object as UTF-8.

    Args:
        path: Destination fixture path.
        value: Complete JSON object.

    Expected output:
        The test copy changes without mutating repository authority bytes.
    """
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )


def rebind_inventory(*, issue_copy: Path, inventory: Dict[str, object]) -> None:
    """Write a forged inventory and update only its snapshot byte binding.

    Args:
        issue_copy: Copied child Requirement directory.
        inventory: Mutated inventory object under negative test.

    Expected output:
        Baseline byte checks pass so the independent semantic closure must
        reject the forged content.
    """
    inventory_path = issue_copy / "legacy_semantic_producer_inventory.json"
    write_json(path=inventory_path, value=inventory)
    baseline_path = issue_copy / "baseline_manifest.json"
    baseline = read_json(path=baseline_path)
    binding = baseline["snapshot_files"]["legacy_semantic_producer_inventory.json"]
    binding["sha256"] = sha256_file(path=inventory_path)
    binding["size"] = inventory_path.stat().st_size
    write_json(path=baseline_path, value=baseline)


def rebind_decisions(*, issue_copy: Path, register: Dict[str, object]) -> None:
    """Write a forged register and update only its snapshot byte binding.

    Args:
        issue_copy: Copied child Requirement directory.
        register: Mutated Decision Register under negative test.

    Expected output:
        Byte-level closure remains self-consistent so effective-tip validation
        must reject the forged policy rather than the outer file hash.
    """
    register_path = issue_copy / "decision_register.json"
    write_json(path=register_path, value=register)
    baseline_path = issue_copy / "baseline_manifest.json"
    baseline = read_json(path=baseline_path)
    binding = baseline["snapshot_files"]["decision_register.json"]
    binding["sha256"] = sha256_file(path=register_path)
    binding["size"] = register_path.stat().st_size
    write_json(path=baseline_path, value=baseline)


def internally_rebind_inventory_records(
    *, inventory: Dict[str, object]
) -> Dict[str, object]:
    """Return a forged inventory with every internal record hash recomputed.

    Args:
        inventory: Complete copied child inventory before attacker mutation.

    Returns:
        Independent mutated object whose counts, coverage, exact-set hashes,
        and record-set hashes are internally self-consistent.
    """
    rebound = copy.deepcopy(inventory)
    producers = rebound["producers"]
    semantic = [row for row in producers if row["kind"] == "SEMANTIC_PRODUCER"]
    shared = [row for row in producers if row["kind"] == "SHARED_PLUMBING"]
    metric_ids = rebound["metric_id_set"]
    rebound["semantic_producer_count"] = len(semantic)
    rebound["shared_plumbing_count"] = len(shared)
    rebound["producer_exact_set_hash"] = content_hash(
        value=[row["producer_id"] for row in semantic]
    )
    rebound["shared_plumbing_exact_set_hash"] = content_hash(
        value=[row["producer_id"] for row in shared]
    )
    rebound["producer_record_set_hash"] = content_hash(value=producers)
    rebound["semantic_producer_record_set_hash"] = content_hash(value=semantic)
    rebound["coverage_by_metric"] = {
        metric_id: [
            row["producer_id"]
            for row in semantic
            if metric_id in row["covered_metric_ids"]
        ]
        for metric_id in metric_ids
    }
    rebound["covered_metric_ids"] = [
        metric_id
        for metric_id in metric_ids
        if rebound["coverage_by_metric"][metric_id]
    ]
    return rebound


class Issue15AuthorityTest(unittest.TestCase):
    """Prove WB-1 bytes, Decision history, and frozen inventories close."""

    def test_issue15_snapshot_loads_and_preserves_parent_history(self) -> None:
        """Load Issue #15 and recompute every WB-1 boundary from source bytes."""
        parent_snapshot = load_requirement_snapshot(snapshot_dir=PARENT_DIR)
        issue_snapshot = load_requirement_snapshot(snapshot_dir=ISSUE_15_DIR)
        parent_register = read_json(path=PARENT_DIR / "decision_register.json")
        parent_inventory = read_json(path=PARENT_DIR / "legacy_path_inventory.json")
        issue_register = read_json(path=ISSUE_15_DIR / "decision_register.json")
        baseline = read_json(path=ISSUE_15_DIR / "baseline_manifest.json")
        transfer = read_json(path=ISSUE_15_DIR / "transfer_manifest.json")
        source_receipt = read_json(
            path=ISSUE_15_DIR / "source_strategy_baseline_receipt.json"
        )
        inventory = read_json(
            path=ISSUE_15_DIR / "legacy_semantic_producer_inventory.json"
        )
        foundation = read_json(
            path=ISSUE_15_DIR / "foundation_verification_receipt.json"
        )

        self.assertEqual("issue_15_v1", issue_snapshot["requirement_id"])
        self.assertEqual(
            parent_snapshot["requirement_closure_hash"],
            issue_snapshot["parent_requirement_closure_hash"],
        )
        self.assertEqual(
            "SUPERSEDED_BY_NEW_DECISION",
            transfer["decision_transfer"]["parent_contract_risk_transitions"][0][
                "status"
            ],
        )
        self.assertEqual(
            CONTRACT_SHA256, sha256_file(path=ISSUE_15_DIR / "CONTRACT.md"),
        )
        contract = (ISSUE_15_DIR / "CONTRACT.md").read_text(encoding="utf-8")
        self.assertNotIn("/ PR #14 主正文", contract)
        self.assertNotIn("合并前 PR #14 停止新增 Reader 代码", contract)

        parent_decisions = parent_register["decisions"]
        parent_pending = parent_register["pending_decisions"]
        issue_decisions = issue_register["decisions"]
        issue_pending = issue_register["pending_decisions"]
        self.assertEqual(12, len(parent_decisions))
        self.assertEqual(1, len(parent_pending))
        historical_parent = list(parent_decisions) + list(parent_pending)
        historical_child = list(issue_decisions[: len(parent_decisions)]) + list(
            issue_pending
        )
        self.assertEqual(13, len(historical_child))
        self.assertEqual(
            [content_hash(value=record) for record in historical_parent],
            [content_hash(value=record) for record in historical_child],
        )
        self.assertEqual([], issue_snapshot["pending_decision_ids"])
        self.assertEqual(4, len(issue_snapshot["decision_chains"]["D-01"]))
        self.assertEqual(3, len(issue_snapshot["decision_chains"]["D-26"]))
        self.assertEqual(2, len(issue_snapshot["decision_chains"]["D-35"]))
        self.assertEqual(2, len(issue_snapshot["decision_chains"]["D-36"]))
        self.assertEqual(
            set(baseline["effective_decision_ids"]),
            set(issue_snapshot["effective_decisions"]),
        )
        self.assertEqual(
            0, issue_snapshot["effective_decisions"]["D-01"]["choice"]["retry_count"],
        )
        self.assertNotIn(
            "freeze_replay",
            issue_snapshot["effective_decisions"]["D-26"]["choice"][
                "prohibited_required_test_classes"
            ],
        )
        self.assertNotIn(
            "budget_preflight_provider_calls_zero",
            issue_snapshot["effective_decisions"]["D-26"]["choice"][
                "required_short_deterministic_invariants"
            ],
        )
        effective_tip_hashes = {
            decision_id: content_hash(
                value=issue_snapshot["effective_decisions"][decision_id]
            )
            for decision_id in ISSUE_15_POST_FREEZE_EFFECTIVE_TIP_HASHES
        }
        self.assertEqual(
            ISSUE_15_POST_FREEZE_EFFECTIVE_TIP_HASHES, effective_tip_hashes,
        )
        for decision_id in ISSUE_15_POST_FREEZE_EFFECTIVE_TIP_HASHES:
            self.assertEqual(
                ISSUE_15_POST_FREEZE_DECISION_EVIDENCE,
                issue_snapshot["effective_decisions"][decision_id]["evidence"],
            )
        d35_choice = issue_snapshot["effective_decisions"]["D-35"]["choice"]
        d36_choice = issue_snapshot["effective_decisions"]["D-36"]["choice"]
        self.assertNotIn("BUDGET_EXCEEDED", d35_choice["terminal_classes"])
        self.assertEqual(0, d35_choice["http_402_automatic_retries"])
        self.assertTrue(d35_choice["http_402_stops_execution"])
        self.assertTrue(d35_choice["http_402_stops_batch"])
        self.assertEqual(
            ["PAYLOAD_LIMIT", "CONTEXT_LIMIT", "RESOURCE_LIMIT"],
            d35_choice["non_monetary_safety_terminal_classes"],
        )
        self.assertEqual(
            "DISABLED", d36_choice["repository_monetary_budget_enforcement"],
        )
        self.assertEqual(
            "EXTERNAL_API_ACCOUNT_BALANCE", d36_choice["spending_authority"],
        )
        self.assertFalse(d36_choice["monetary_budget_preflight"])
        self.assertFalse(
            d36_choice["estimated_or_actual_cost_may_block_provider_call"]
        )
        for decision_id in [
            "D-30",
            "D-31",
            "D-32",
            "D-33",
            "D-34",
            "D-37",
            "D-38",
        ]:
            self.assertEqual(
                1, len(issue_snapshot["decision_chains"][decision_id]),
            )

        parent_files = transfer["parent_snapshot_files"]
        for filename, binding in parent_files.items():
            parent_path = PARENT_DIR / filename
            self.assertEqual(binding["sha256"], sha256_file(path=parent_path))
            self.assertEqual(binding["size"], parent_path.stat().st_size)

        for relative, binding in baseline["runtime_authority_files"].items():
            runtime_path = REPO_ROOT / relative
            self.assertEqual(binding["sha256"], sha256_file(path=runtime_path))
            self.assertEqual(binding["size"], runtime_path.stat().st_size)

        matrix_path = frozen_issue15_artifact_path(
            relative="outputs/metrics_matrix.csv"
        )
        with matrix_path.open(mode="r", encoding="utf-8", newline="") as file_obj:
            rows = list(csv.DictReader(f=file_obj))
        metric_ids = sorted({row["metric_id"] for row in rows})
        keys = sorted(
            [
                {"company": row["company"], "metric_id": row["metric_id"]}
                for row in rows
            ],
            key=lambda row: (row["company"], row["metric_id"]),
        )
        self.assertEqual(230, len(rows))
        self.assertEqual(39, len(metric_ids))
        self.assertEqual(source_receipt["matrix_sha256"], sha256_file(path=matrix_path))
        self.assertEqual(source_receipt["metric_id_set"], metric_ids)
        self.assertEqual(
            source_receipt["metric_id_set_hash"], content_hash(value=metric_ids),
        )
        self.assertEqual(
            source_receipt["rows_by_metric"],
            dict(sorted(Counter(row["metric_id"] for row in rows).items())),
        )
        self.assertEqual(
            source_receipt["rows_by_current_status"],
            dict(sorted(Counter(row["status"] for row in rows).items())),
        )
        self.assertEqual(
            source_receipt["frozen_legacy_keyset_hash"], content_hash(value=keys),
        )

        producers = inventory["producers"]
        semantic_producers = [
            producer
            for producer in producers
            if producer["kind"] == "SEMANTIC_PRODUCER"
        ]
        semantic_producer_ids = sorted(
            producer["producer_id"] for producer in semantic_producers
        )
        self.assertEqual(
            inventory["producer_exact_set_hash"],
            content_hash(value=semantic_producer_ids),
        )
        self.assertEqual(
            inventory["producer_record_set_hash"], content_hash(value=producers),
        )
        self.assertEqual(
            inventory["semantic_producer_record_set_hash"],
            content_hash(value=semantic_producers),
        )
        self.assertEqual(
            ISSUE_15_EXPECTED_PRODUCER_EXACT_SET_HASH,
            content_hash(value=semantic_producer_ids),
        )
        self.assertEqual(
            ISSUE_15_EXPECTED_PRODUCER_RECORD_SET_HASH, content_hash(value=producers),
        )
        self.assertEqual(
            ISSUE_15_EXPECTED_SEMANTIC_RECORD_SET_HASH,
            content_hash(value=semantic_producers),
        )
        scope_closure = {
            "scope_evidence_by_producer": inventory["scope_evidence_by_producer"],
            "scope_evidence_groups": inventory["scope_evidence_groups"],
            "scope_excluded_callers": inventory["scope_excluded_callers"],
            "scope_transitive_edges": inventory["scope_transitive_edges"],
        }
        self.assertEqual(
            ISSUE_15_EXPECTED_SCOPE_EVIDENCE_HASH, content_hash(value=scope_closure),
        )
        self.assertEqual(
            ISSUE_15_BASE_PIPELINE_SHA256,
            inventory["producer_source_files"]["scripts/sec_pipeline.py"]["sha256"],
        )
        expected_parent_groups = {
            group: parent_inventory[group]
            for group in sorted(parent_inventory["migration_rules"])
        }
        self.assertEqual(
            expected_parent_groups, inventory["parent_inventory_groups"],
        )
        self.assertEqual(
            set(expected_parent_groups), set(inventory["parent_symbol_dispositions"]),
        )
        for group, members in expected_parent_groups.items():
            self.assertEqual(
                set(members), set(inventory["parent_symbol_dispositions"][group]),
            )
        self.assertEqual(metric_ids, inventory["covered_metric_ids"])
        symbols_by_file: Dict[str, Set[str]] = {}
        for producer in producers:
            relative, symbol = producer["producer_id"].split("::", 1)
            if relative not in symbols_by_file:
                symbols_by_file[relative] = module_symbols(path=REPO_ROOT / relative)
            self.assertIn(symbol, symbols_by_file[relative])
        self.assertIs(False, inventory["mutable_legacy_retirement_config_ledger"])
        self.assertFalse(
            (REPO_ROOT / "config" / "legacy_retirement_ledger.json").exists()
        )

        self.assertEqual(
            FOUNDATION_SOURCE_COMMIT, foundation["foundation_source_commit"],
        )
        self.assertEqual(FOUNDATION_MERGE_COMMIT, foundation["foundation_merge_commit"])
        self.assertEqual("issue-15-foundation-v1", foundation["foundation_tag"])
        self.assertEqual("FAST_LOCAL_ONLY", foundation["highest_evidence_level"])
        self.assertEqual(0, foundation["real_external_provider_egress_count"])
        self.assertEqual(0, foundation["paid_provider_call_count"])
        self.assertEqual(
            [0, 0, 0, 0],
            [row["return_code"] for row in foundation["verification_commands"]],
        )
        bound_paths = {binding["path"] for binding in foundation["receipt_bindings"]}
        for binding in foundation["receipt_bindings"]:
            path = REPO_ROOT / binding["path"]
            self.assertTrue(path.is_file())
            self.assertFalse(path.is_symlink())
            self.assertEqual(binding["size"], path.stat().st_size)
            self.assertEqual(binding["sha256"], sha256_file(path=path))
        for command in foundation["verification_commands"]:
            self.assertTrue(set(command["receipt_paths"]).issubset(bound_paths))

        for relative, binding in baseline["root_business_artifacts"].items():
            path = frozen_issue15_artifact_path(relative=relative)
            self.assertEqual(binding["sha256"], sha256_file(path=path))
            self.assertEqual(binding["size"], path.stat().st_size)

    def test_reusable_producer_scopes_match_exact_base_call_graph(self) -> None:
        """Derive reusable helper scopes from every audited base callsite."""
        inventory = read_json(
            path=ISSUE_15_DIR / "legacy_semantic_producer_inventory.json"
        )
        pipeline_path = REPO_ROOT / "scripts" / "sec_pipeline.py"
        self.assertEqual(
            ISSUE_15_BASE_PIPELINE_SHA256, sha256_file(path=pipeline_path),
        )
        functions = module_functions(path=pipeline_path)
        groups = inventory["scope_evidence_groups"]
        group_by_id = {row["evidence_id"]: row for row in groups}
        selection_evidence = set()
        direct_metric_evidence = {
            "derived_metric": set(),
            "metric_from_fact": set(),
        }
        predicate_evidence = set()

        # Exact line/column locators make every evidence group falsifiable
        # against the source bytes rather than merely self-consistent JSON.
        for group in groups:
            evidence_type = group["evidence_type"]
            if evidence_type == "METRIC_SET_CONSTANT":
                symbol = group["caller_id"].split("::", 1)[1]
                value = assignment_value(path=pipeline_path, symbol=symbol)
                line_text, column_text = group["call_sites"][0].split(":", maxsplit=1)
                self.assertEqual(int(line_text), value.lineno)
                self.assertEqual(int(column_text), value.col_offset)
                self.assertEqual(
                    set(group["active_metric_ids"]), set(ast.literal_eval(value)),
                )
                self.assertEqual([], group["retired_metric_ids"])
                continue

            caller = group["caller_id"].split("::", 1)[1]
            callee = group["callee_id"].split("::", 1)[1]
            observed_metric_ids = set()
            for call_site in group["call_sites"]:
                call = call_at_site(
                    function=functions[caller], callee=callee, call_site=call_site,
                )
                identity = (caller, callee, call_site)
                if evidence_type == "SELECTION_CALLSITES":
                    period_kind = call_keyword(call=call, keyword="period_kind",)
                    self.assertIsInstance(period_kind, ast.Constant)
                    self.assertEqual(group["period_kind"], period_kind.value)
                    selection_evidence.add(identity)
                elif evidence_type == "DIRECT_METRIC_ARGUMENT":
                    metric_id = call_keyword(call=call, keyword="metric_id")
                    self.assertIsInstance(metric_id, ast.Constant)
                    observed_metric_ids.add(metric_id.value)
                    direct_metric_evidence[callee].add(identity)
                elif evidence_type == "DIRECT_PREDICATE_CALLSITES":
                    predicate_evidence.add(identity)
                else:
                    self.fail("Unknown scope evidence type: " + evidence_type)
            if evidence_type == "DIRECT_METRIC_ARGUMENT":
                self.assertEqual(
                    set(group["active_metric_ids"]), observed_metric_ids,
                )
                self.assertEqual([], group["retired_metric_ids"])

        # Every production selector call is either evidence-bearing or an
        # explicitly classified wrapper/validation-only caller.
        excluded = inventory["scope_excluded_callers"]
        actual_selection = set()
        actual_excluded_callers = set()
        for caller, function in functions.items():
            caller_id = "scripts/sec_pipeline.py::" + caller
            for node in ast.walk(function):
                if (
                    not isinstance(node, ast.Call)
                    or not isinstance(node.func, ast.Name)
                    or node.func.id
                    not in {"select_component", "select_target_component"}
                ):
                    continue
                identity = (
                    caller,
                    node.func.id,
                    "{}:{}".format(node.lineno, node.col_offset),
                )
                if caller_id in excluded:
                    actual_excluded_callers.add(caller_id)
                else:
                    actual_selection.add(identity)
        self.assertEqual(selection_evidence, actual_selection)
        self.assertEqual(set(excluded), actual_excluded_callers)

        # Direct metric projection and duration-predicate helpers have no
        # unaccounted callsite outside their evidence groups.
        for callee in sorted(direct_metric_evidence):
            actual = set()
            for caller, function in functions.items():
                for node in ast.walk(function):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == callee
                    ):
                        actual.add(
                            (
                                caller,
                                callee,
                                "{}:{}".format(node.lineno, node.col_offset),
                            )
                        )
            self.assertEqual(direct_metric_evidence[callee], actual)
        actual_predicates = set()
        for caller, function in functions.items():
            for node in ast.walk(function):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "annual_duration_ok"
                ):
                    actual_predicates.add(
                        (
                            caller,
                            node.func.id,
                            "{}:{}".format(node.lineno, node.col_offset),
                        )
                    )
        self.assertEqual(predicate_evidence, actual_predicates)

        # Verify the reusable selector chain and its duration/instant guards.
        edge_identities = set()
        for edge in inventory["scope_transitive_edges"]:
            caller = edge["caller_id"].split("::", 1)[1]
            callee = edge["callee_id"].split("::", 1)[1]
            call = call_at_site(
                function=functions[caller], callee=callee, call_site=edge["call_site"],
            )
            edge_identities.add((caller, callee, edge["call_site"]))
            flow = edge["period_kind_flow"]
            if flow == "PASSTHROUGH":
                period_kind = call_keyword(call=call, keyword="period_kind")
                self.assertIsInstance(period_kind, ast.Name)
                self.assertEqual("period_kind", period_kind.id)
                continue
            expected_kind = flow.split("::", 1)[1]
            parents = {
                child: parent
                for parent in ast.walk(functions[caller])
                for child in ast.iter_child_nodes(parent)
            }
            ancestor = parents[call]
            while not isinstance(ancestor, ast.If):
                ancestor = parents[ancestor]
            self.assertIsInstance(ancestor.test, ast.Compare)
            self.assertIsInstance(ancestor.test.left, ast.Name)
            self.assertEqual("period_kind", ancestor.test.left.id)
            self.assertIsInstance(ancestor.test.ops[0], ast.Eq)
            comparator = ancestor.test.comparators[0]
            self.assertIsInstance(comparator, ast.Constant)
            self.assertEqual(expected_kind, comparator.value)
        expected_edge_callers = {
            edge["caller_id"].split("::", 1)[1]
            for edge in inventory["scope_transitive_edges"]
        }
        actual_edges = set()
        edge_callees = {
            edge["callee_id"].split("::", 1)[1]
            for edge in inventory["scope_transitive_edges"]
        }
        for caller in expected_edge_callers:
            for node in ast.walk(functions[caller]):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in edge_callees
                ):
                    actual_edges.add(
                        (
                            caller,
                            node.func.id,
                            "{}:{}".format(node.lineno, node.col_offset),
                        )
                    )
        self.assertEqual(edge_identities, actual_edges)

        # The same generic union rule drives every evidence-marked producer;
        # no function-specific assertion is needed to enforce future changes.
        producer_by_id = {row["producer_id"]: row for row in inventory["producers"]}
        referenced_groups = set()
        for producer_id, evidence in inventory["scope_evidence_by_producer"].items():
            selected = [
                group_by_id[group_id] for group_id in evidence["evidence_group_ids"]
            ]
            derived_active = sorted(
                {
                    metric_id
                    for group in selected
                    for metric_id in group["active_metric_ids"]
                }
            )
            derived_retired = sorted(
                {
                    metric_id
                    for group in selected
                    for metric_id in group["retired_metric_ids"]
                }
            )
            self.assertEqual(derived_active, evidence["active_metric_ids"])
            self.assertEqual(derived_retired, evidence["retired_metric_ids"])
            self.assertEqual(
                derived_active, producer_by_id[producer_id]["active_metric_ids"],
            )
            self.assertEqual(
                derived_retired, producer_by_id[producer_id]["retired_metric_ids"],
            )
            referenced_groups.update(evidence["evidence_group_ids"])
        self.assertEqual(set(group_by_id), referenced_groups)

        fact_is_instant = producer_by_id["scripts/sec_pipeline.py::fact_is_instant"]
        self.assertEqual(
            ["A04", "A05", "A06", "A10", "B06", "B08", "B09"],
            fact_is_instant["active_metric_ids"],
        )
        self.assertEqual([], fact_is_instant["retired_metric_ids"])
        self.assertTrue(
            {"A04", "A05", "A06", "B09"}.issubset(fact_is_instant["active_metric_ids"])
        )

    def test_issue15_contract_byte_change_invalidates_snapshot(self) -> None:
        """Reject one Contract byte while leaving the copied parent untouched."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            with (issue_copy / "CONTRACT.md").open(mode="ab") as file_obj:
                file_obj.write(b"\n")
            with self.assertRaises(RequirementError):
                load_requirement_snapshot(snapshot_dir=issue_copy)

    def test_monetary_observability_cannot_become_a_budget_gate(self) -> None:
        """Reject a self-rebound tip that makes estimated cost blocking."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            register = read_json(path=issue_copy / "decision_register.json")
            d36 = next(
                row
                for row in reversed(register["decisions"])
                if row["decision_id"] == "D-36"
            )
            d36["choice"]["estimated_or_actual_cost_may_block_provider_call"] = True
            rebind_decisions(issue_copy=issue_copy, register=register)
            with self.assertRaisesRegex(
                RequirementError, "superseding Decision content differs",
            ):
                load_requirement_snapshot(snapshot_dir=issue_copy)

    def test_budget_exceeded_cannot_return_as_monetary_terminal(self) -> None:
        """Reject a self-rebound D-35 tip that restores BUDGET_EXCEEDED."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            register = read_json(path=issue_copy / "decision_register.json")
            d35 = next(
                row
                for row in reversed(register["decisions"])
                if row["decision_id"] == "D-35"
            )
            d35["choice"]["terminal_classes"].append("BUDGET_EXCEEDED")
            rebind_decisions(issue_copy=issue_copy, register=register)
            with self.assertRaisesRegex(
                RequirementError, "superseding Decision content differs",
            ):
                load_requirement_snapshot(snapshot_dir=issue_copy)

    def test_resource_limit_cannot_be_recast_as_monetary_budget(self) -> None:
        """Reject a tip that disguises a hard resource limit as spending."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            register = read_json(path=issue_copy / "decision_register.json")
            d35 = next(
                row
                for row in reversed(register["decisions"])
                if row["decision_id"] == "D-35"
            )
            d35["choice"]["resource_limit_is_monetary_budget_gate"] = True
            rebind_decisions(issue_copy=issue_copy, register=register)
            with self.assertRaisesRegex(
                RequirementError, "superseding Decision content differs",
            ):
                load_requirement_snapshot(snapshot_dir=issue_copy)

    def test_budget_preflight_invariant_cannot_return(self) -> None:
        """Reject a self-rebound D-26 tip that restores the removed test."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            register = read_json(path=issue_copy / "decision_register.json")
            d26 = next(
                row
                for row in reversed(register["decisions"])
                if row["decision_id"] == "D-26"
            )
            d26["choice"]["required_short_deterministic_invariants"].append(
                "budget_preflight_provider_calls_zero"
            )
            rebind_decisions(issue_copy=issue_copy, register=register)
            with self.assertRaisesRegex(
                RequirementError, "superseding Decision content differs",
            ):
                load_requirement_snapshot(snapshot_dir=issue_copy)

    def test_missing_foundation_receipt_invalidates_snapshot(self) -> None:
        """Reject a binding whose declared repository file is absent."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            foundation = read_json(
                path=issue_copy / "foundation_verification_receipt.json"
            )
            repository_root = issue_copy.parents[1]
            missing = repository_root / foundation["receipt_bindings"][0]["path"]
            missing.unlink()
            with self.assertRaises(RequirementError):
                load_requirement_snapshot(snapshot_dir=issue_copy)

    def test_one_byte_foundation_receipt_tamper_invalidates_snapshot(self) -> None:
        """Reject same-size supporting evidence with one changed byte."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            foundation = read_json(
                path=issue_copy / "foundation_verification_receipt.json"
            )
            repository_root = issue_copy.parents[1]
            target = repository_root / foundation["receipt_bindings"][2]["path"]
            with target.open(mode="r+b") as file_obj:
                original = file_obj.read(1)
                file_obj.seek(0)
                file_obj.write(b"[" if original != b"[" else b"{")
            self.assertEqual(
                foundation["receipt_bindings"][2]["size"], target.stat().st_size,
            )
            with self.assertRaises(RequirementError):
                load_requirement_snapshot(snapshot_dir=issue_copy)

    def test_missing_parent_production_disposition_invalidates_snapshot(self,) -> None:
        """Reject a self-rebound inventory missing one parent producer."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            inventory = read_json(
                path=issue_copy / "legacy_semantic_producer_inventory.json"
            )
            del inventory["parent_symbol_dispositions"][
                "additional_migrated_production_symbols"
            ]["custom_da_observation_note"]
            rebind_inventory(issue_copy=issue_copy, inventory=inventory)
            with self.assertRaises(RequirementError):
                load_requirement_snapshot(snapshot_dir=issue_copy)

    def test_code_derived_instant_scope_rejects_self_consistent_tamper(self,) -> None:
        """Reject a forged instant scope after all internal hashes are fixed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            inventory = read_json(
                path=issue_copy / "legacy_semantic_producer_inventory.json"
            )
            producer = next(
                row
                for row in inventory["producers"]
                if row["producer_id"] == "scripts/sec_pipeline.py::fact_is_instant"
            )
            producer["active_metric_ids"].remove("A05")
            producer["covered_metric_ids"].remove("A05")
            inventory = internally_rebind_inventory_records(inventory=inventory)
            rebind_inventory(issue_copy=issue_copy, inventory=inventory)
            with self.assertRaisesRegex(
                RequirementError, "code-derived producer scope differs",
            ):
                load_requirement_snapshot(snapshot_dir=issue_copy)

    def test_complete_record_hash_rejects_unmarked_active_to_retired_tamper(
        self,
    ) -> None:
        """Reject self-rebound lifecycle drift outside scope evidence."""
        with tempfile.TemporaryDirectory() as temp_dir:
            issue_copy = copy_test_repository(temp_dir=temp_dir)
            inventory = read_json(
                path=issue_copy / "legacy_semantic_producer_inventory.json"
            )
            producer_id = "scripts/sec_pipeline.py::a04_companyfacts_proxy_note"
            self.assertNotIn(
                producer_id, inventory["scope_evidence_by_producer"],
            )
            producer = next(
                row
                for row in inventory["producers"]
                if row["producer_id"] == producer_id
            )
            producer["active_metric_ids"] = []
            producer["retired_metric_ids"] = ["A04"]
            producer["covered_metric_ids"] = ["A04"]
            producer["lifecycle"] = "RETIRED_TOMBSTONE"
            inventory = internally_rebind_inventory_records(inventory=inventory)
            rebind_inventory(issue_copy=issue_copy, inventory=inventory)
            with self.assertRaisesRegex(
                RequirementError, "complete producer record authority differs",
            ):
                load_requirement_snapshot(snapshot_dir=issue_copy)


if __name__ == "__main__":
    unittest.main()
