"""Versioned ordinary-candidate Evidence: exact source labels and ownership.

The retained checker owns source/geometry/numeric/scope checks. This wrapper
selects its existing raw-or-text primitive from the new annual policy and
adds bounded row/group/column provenance. It never searches for a replacement
value, rewrites the response, or supplies business aliases.
"""
from .canonical import content_hash
from .evidence import check_evidence
from .records import validate_record
from .r4_label_policy import RAW_LABEL_POLICY, SOURCE_LABEL_POLICY
from .table_grid import resolve_cell
from .constraints import parse_numeric_claim, ConstraintError
from .requirement_profile_v7 import REQUIREMENT_ID, DECISION_ID, candidate_choice


def policy_choice(requirement):
    """Old Runs always retain raw-only semantics, regardless of inherited R4 tips."""
    if requirement is None:
        return None
    current_id, decision_id, generation, validator = REQUIREMENT_ID, DECISION_ID, "PROFILE_DRIVEN_V7", candidate_choice
    if requirement.get("requirement_id") == "issue_28_v8":
        from . import requirement_profile_v9 as continuity
        current_id, decision_id = continuity.REQUIREMENT_ID, continuity.DECISION_ID
        generation, validator = continuity.PROFILE_REQUIREMENT_GENERATION, continuity.candidate_choice
    if requirement.get("requirement_id") != current_id:
        return None
    if requirement.get("requirement_generation") != generation:
        raise ValueError("ANNUAL_LABEL_REQUIREMENT_GENERATION_INVALID")
    decision = requirement["effective_decisions"][decision_id]
    if decision["status"] != "APPROVED":
        raise ValueError("ANNUAL_LABEL_POLICY_NOT_APPROVED")
    choice = validator(choice=decision["choice"])
    if choice["label_comparison"] != {
        "policy": SOURCE_LABEL_POLICY,
        "accepted_cell_fields": ["raw_text", "text"],
        "authoritative_cell_field": "raw_text",
        "caption_policy": RAW_LABEL_POLICY,
        "response_rewrite_allowed": False,
        "fuzzy_matching_or_locator_search_allowed": False,
    }:
        raise ValueError("ANNUAL_LABEL_POLICY_DIFFERS")
    return choice


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _covers(cell, column):
    return (
        cell["origin_column_index"]
        <= column
        < cell["origin_column_index"] + cell["colspan"]
    )


def _ownership(*, candidate, derived_asset, target_period, choice, task_contract):
    rule = choice["source_ownership"]
    _need(type(target_period) is dict, "ANNUAL_TARGET_PERIOD_REQUIRED")
    year = target_period["fiscal_year"]
    for claim in candidate["selected"].values():
        value = resolve_cell(derived_asset=derived_asset, locator=claim["locator"])
        row, column = value["origin_row_index"], value["origin_column_index"]
        table = next(
            t
            for t in derived_asset["tables"]
            if t["table_id"] == claim["locator"]["table_id"]
        )
        _need(
            claim["claimed_period"] == "FY" + str(year), "ANNUAL_CLAIM_PERIOD_MISMATCH"
        )
        _need(
            claim["claimed_reported_unit"] == rule["reported_unit"],
            "ANNUAL_UNIT_MISMATCH",
        )
        labels = {label["id"]: label for label in claim["scope_evidence_locators"]}
        scopes = {item["dimension"]: item for item in claim["claimed_scope"]}
        resolved = {}
        for dimension in rule["row_dimensions"] + rule["group_dimensions"]:
            _need(dimension in scopes, "ANNUAL_SCOPE_DIMENSION_MISSING")
            resolved[dimension] = []
            for lid in scopes[dimension]["evidence_locator_ids"]:
                label = labels[lid]
                _need(
                    label["location_type"] != "caption",
                    "ANNUAL_ROW_GROUP_LAYOUT_REQUIRED",
                )
                cell = resolve_cell(
                    derived_asset=derived_asset, locator=label["locator"]
                )
                _need(
                    cell["origin_column_index"] + cell["colspan"] <= column,
                    "ANNUAL_SCOPE_LABEL_NOT_ROW_HEADER",
                )
                resolved[dimension].append(cell)
        for dimension in rule["row_dimensions"]:
            _need(
                all(c["origin_row_index"] == row for c in resolved[dimension]),
                "ANNUAL_SCOPE_VALUE_ROW_MISMATCH",
            )
        group_rows = []
        for dimension in rule["group_dimensions"]:
            for cell in resolved[dimension]:
                headings = []
                for source_row in table["rows"][:row]:
                    nonempty = [
                        c for c in source_row["cells"] if c["is_origin"] and c["text"]
                    ]
                    if (
                        len(nonempty) == 1
                        and nonempty[0]["origin_column_index"]
                        == cell["origin_column_index"]
                    ):
                        headings.append(nonempty[0])
                _need(
                    bool(headings)
                    and all(
                        headings[-1][k] == cell[k]
                        for k in (
                            "origin_row_index",
                            "origin_column_index",
                            "rowspan",
                            "colspan",
                        )
                    ),
                    "ANNUAL_SCOPE_VALUE_GROUP_MISMATCH",
                )
                group_rows.append(cell["origin_row_index"])
        _need(len(set(group_rows)) == 1, "ANNUAL_SCOPE_GROUP_AMBIGUOUS")
        # This supported layout has a row-label column and two header levels.
        # Only a separate row label plus numeric source-unit cell is a data row.
        # Inspect every such row before the value, so a later overlapping year
        # or role cannot be hidden by an earlier matching header.
        label_columns = {
            c["origin_column_index"] for cells in resolved.values() for c in cells
        }
        _need(len(label_columns) == 1, "ANNUAL_LABEL_COLUMN_AMBIGUOUS")
        label_column = next(iter(label_columns))
        headers = []
        for source_row in table["rows"][:row]:
            nonempty = [c for c in source_row["cells"] if c["is_origin"] and c["text"]]
            row_labels = [
                c
                for c in nonempty
                if _covers(c, label_column)
                and c["origin_column_index"] + c["colspan"] <= column
            ]
            covered = [c for c in nonempty if _covers(c, column)]
            is_data = False
            if row_labels and len(covered) == 1 and not covered[0]["header"]:
                numeric = covered[0]
                unit_cells = [
                    c
                    for c in nonempty
                    if c["origin_column_index"]
                    == numeric["origin_column_index"] + numeric["colspan"]
                ]
                source_unit = (
                    numeric["text"].endswith(rule["visible_unit"])
                    or len(unit_cells) == 1
                    and unit_cells[0]["text"] == rule["visible_unit"]
                )
                if source_unit:
                    try:
                        parse_numeric_claim(
                            raw_value=numeric["text"],
                            reported_unit=rule["reported_unit"],
                        )
                        is_data = True
                    except ConstraintError:
                        pass
            if not is_data:
                headers.extend(covered)
        _need(len(headers) == 2, "ANNUAL_VALUE_HEADER_AMBIGUOUS")
        role = claim["role"]
        _need(role in task_contract["required_roles"], "ANNUAL_ROLE_MISMATCH")
        metric_headers = [
            c
            for c in headers
            if c["text"].casefold() == role.replace("_", " ").casefold()
        ]
        year_headers = [c for c in headers if c["text"] == str(year)]
        _need(
            len(metric_headers) == 1
            and len(year_headers) == 1
            and metric_headers[0]["origin_row_index"]
            < year_headers[0]["origin_row_index"],
            "ANNUAL_VALUE_HEADER_PERIOD_MISMATCH",
        )
        # The stated unit must also be visible at the exact value, not borrowed
        # from a different metric column or a percentage-change column.
        next_col = column + value["colspan"]
        adjacent = [
            c
            for c in table["rows"][row]["cells"]
            if c["is_origin"] and c["origin_column_index"] == next_col
        ]
        _need(
            value["text"].endswith(rule["visible_unit"])
            or len(adjacent) == 1
            and adjacent[0]["text"] == rule["visible_unit"],
            "ANNUAL_VALUE_UNIT_SOURCE_MISMATCH",
        )


def check_annual_evidence(*, requirement=None, target_period=None, **kwargs):
    """One version-selected checker used before transport acceptance, in Run, and replay."""
    choice = policy_choice(requirement)
    result = check_evidence(
        **kwargs, _label_policy=SOURCE_LABEL_POLICY if choice else RAW_LABEL_POLICY
    )
    if choice is None:
        return result
    reasons = list(result["reason_codes"])
    if not reasons:
        try:
            _need(
                result["system_approval_eligible"],
                "ANNUAL_SCOPE_UNRESOLVED_OR_UNSUPPORTED",
            )
            _ownership(
                candidate=kwargs["candidate"],
                derived_asset=kwargs["derived_asset"],
                target_period=target_period,
                choice=choice,
                task_contract=kwargs["reader_payload_body"]["task_contract"],
            )
        except ValueError as error:
            reasons.append(str(error))
    result = {
        **result,
        "checks": [
            *result["checks"],
            {
                "check": "ANNUAL_SOURCE_OWNERSHIP_V1",
                "status": "FAIL" if reasons else "PASS",
                "requirement_id": requirement["requirement_id"],
                "policy_hash": content_hash(value=choice),
            },
        ],
        "reason_codes": reasons,
        "status": "REJECTED" if reasons else "PASS",
        "system_approval_eligible": result["system_approval_eligible"] and not reasons,
    }
    result["evidence_check_id"] = content_hash(
        value={
            k: v
            for k, v in result.items()
            if k not in {"record_type", "evidence_check_id"}
        }
    )
    return validate_record(record=result)
