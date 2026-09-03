"""Source-bound successor facts consumed by the existing Evidence Checker.

This is not a Reader, table selector or alternate financial verifier. Callers
name reviewed source coordinates. Every returned fact is reconstructed from
the unchanged complete source/asset and the selected Requirement's authority.
No source text is copied into a table/caption and no network code is present.
"""

from __future__ import annotations

import html
import re
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Mapping, Optional

from .canonical import arithmetic_context, canonical_json_bytes, content_hash
from .canonical import decimal_text, parse_decimal, sha256_bytes, strict_json_file
from .constraints import parse_numeric_claim
from .records import EXPLICIT_ARTIFACT_GENERATION, validate_record
from .scope_contract import exact_enum_alias, scope_satisfies_contract
from .sources import resolve_repository_file
from .table_grid import resolve_cell


NUMERIC_POLICY_PATH = "config/r4_numeric_normalization_v1.json"
PROOF_TYPE = "SOURCE_BOUND_EVIDENCE_PROOF"
PROOF_FIELDS = frozenset({
    "record_type", "schema_version", "source_bound_proof_id",
    "artifact_requirement_generation", "requirement_id", "requirement_closure_hash",
    "requirement_hashes", "raw_blob", "source_reference", "source_sha256", "source_size",
    "full_derived_asset_id", "task_contract_id", "task_contract_hash", "metric_id",
    "target_locator", "numeric_normalization", "composite_scope", "qualification_credit",
})
RECIPE_FIELDS = frozenset({
    "section_heading", "section_end_heading", "association_heading",
    "association_end_heading", "selected_scope_spans", "target_measure_name",
    "table_association_span",
})


class CompositeScopeError(ValueError):
    """Fail closed on source/section/scale/scope ambiguity or identity drift."""


def _exact(value: object, fields: frozenset, label: str) -> Mapping:
    if type(value) is not dict or set(value) != fields:
        raise CompositeScopeError(label + " fields are not exact")
    return value


def _choice(*, requirement: Mapping, kind: str) -> Mapping:
    choices = [d["choice"] for d in requirement["effective_decisions"].values()
               if d["status"] == "APPROVED" and d["choice"]["kind"] == kind]
    if len(choices) != 1:
        raise CompositeScopeError("Source-bound policy is absent or ambiguous: " + kind)
    return choices[0]


class _SourceStructure(HTMLParser):
    """Index original byte spans without materializing or rewriting table cells."""

    _BLOCKS = {"div", "p", "h1", "h2", "h3", "h4", "h5", "h6"}
    _VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, source_bytes: bytes):
        super().__init__(convert_charrefs=False)
        self.source_bytes = source_bytes
        self.source = source_bytes.decode("utf-8")
        self.lines = [0] + [m.end() for m in re.finditer("\n", self.source)]
        self.char_cursor = 0
        self.byte_cursor = 0
        self.stack = []
        self.root_counts = {}
        self.tables = []
        self.blocks = []

    def _position(self):
        line, column = self.getpos()
        position = self.lines[line - 1] + column
        self.byte_cursor += len(self.source[self.char_cursor:position].encode("utf-8"))
        self.char_cursor = position
        return self.byte_cursor

    def handle_starttag(self, tag, attrs):
        start = self._position()
        if tag in self._VOID:
            if tag == "br":
                self.handle_data("\n")
            return
        counts = self.stack[-1]["children"] if self.stack else self.root_counts
        counts[tag] = counts.get(tag, 0) + 1
        path = (list(self.stack[-1]["path"]) if self.stack else []) + [tag + ":" + str(counts[tag])]
        frame = {"tag": tag, "start": start, "attrs": [[k, v or ""] for k, v in attrs],
                 "path": path, "children": {}, "parts": [], "nested_block": False,
                 "inside_table": any(f["tag"] == "table" for f in self.stack)}
        if tag in self._BLOCKS or tag == "table":
            for ancestor in self.stack:
                if ancestor["tag"] in self._BLOCKS:
                    ancestor["nested_block"] = True
        if tag == "table":
            frame["table_order"] = len(self.tables)
            self.tables.append(None)
        self.stack.append(frame)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self._VOID:
            self.handle_endtag(tag)

    def _finish(self, frame, end):
        if frame["tag"] == "table":
            self.tables[frame["table_order"]] = {
                "table_order": frame["table_order"], "start_byte": frame["start"], "end_byte": end,
                "structure_path": frame["path"],
                "span_sha256": sha256_bytes(content=self.source_bytes[frame["start"]:end]),
            }
        elif frame["tag"] in self._BLOCKS and not frame["nested_block"]:
            text = "".join(frame["parts"])
            if text.strip():
                self.blocks.append({"start_byte": frame["start"], "end_byte": end,
                    "tag": frame["tag"], "attributes": frame["attrs"],
                    "inside_table": frame["inside_table"],
                    "structure_path": frame["path"], "visible_text": text,
                    "span_sha256": sha256_bytes(content=self.source_bytes[frame["start"]:end])})

    def handle_endtag(self, tag):
        start = self._position()
        end_char = self.source.find(">", self.char_cursor)
        if end_char < 0:
            raise CompositeScopeError("Source structure has an incomplete closing tag")
        end = start + len(self.source[self.char_cursor:end_char + 1].encode("utf-8"))
        matches = [i for i, frame in enumerate(self.stack) if frame["tag"] == tag]
        if not matches:
            return
        index = matches[-1]
        for frame in reversed(self.stack[index:]):
            self._finish(frame, end)
        del self.stack[index:]

    def handle_data(self, data):
        for frame in self.stack:
            if frame["tag"] in self._BLOCKS and not frame["nested_block"]:
                frame["parts"].append(data)

    def handle_entityref(self, name):
        self.handle_data(html.unescape("&" + name + ";"))

    def handle_charref(self, name):
        self.handle_data(html.unescape("&#" + name + ";"))

    def finish(self):
        self.feed(self.source)
        self.close()
        for frame in reversed(self.stack):
            self._finish(frame, len(self.source_bytes))
        self.blocks.sort(key=lambda b: b["start_byte"])
        return {"source_sha256": sha256_bytes(content=self.source_bytes),
                "source_size": len(self.source_bytes), "tables": self.tables, "blocks": self.blocks}


def index_source_structure(*, source_bytes: bytes) -> dict:
    """Expose exact structural coordinates for offline source-specific audit.

    The result does not choose a table, subsection or scope span. Production
    validation consumes an already audited recipe, never a guessed heading.
    """
    if type(source_bytes) is not bytes:
        raise CompositeScopeError("Source structure requires exact immutable bytes")
    return _SourceStructure(source_bytes).finish()


def _span(*, source_bytes: bytes, start: int, end: int) -> dict:
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(source_bytes):
        raise CompositeScopeError("Source byte span is out of range")
    value = source_bytes[start:end]
    try:
        exact = value.decode("utf-8")
    except UnicodeError as error:
        raise CompositeScopeError("Source byte span splits UTF-8") from error
    return {"start_byte": start, "end_byte": end, "exact_source_utf8": exact,
            "span_sha256": sha256_bytes(content=value)}


def _node(*, locator: Mapping, structure: Mapping, source_bytes: bytes,
          allow_table_heading: bool = False) -> dict:
    _exact(locator, frozenset({"start_byte", "end_byte"}), "Source block locator")
    nodes = [block for block in structure["blocks"]
             if block["start_byte"] == locator["start_byte"] and block["end_byte"] == locator["end_byte"]]
    if len(nodes) != 1 or (nodes[0]["inside_table"] and not allow_table_heading):
        raise CompositeScopeError("Audited span is not one original non-table HTML block")
    return {**deepcopy(nodes[0]), **_span(source_bytes=source_bytes,
        start=locator["start_byte"], end=locator["end_byte"])}


def _alias_occurrences(*, text: str, alias: str) -> list:
    exact = [m.span() for m in re.finditer(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text)]
    if exact:
        return exact
    tokens = alias.split(" ")
    if len(tokens) < 2 or any(not token or re.fullmatch(r"\w+", token) is None for token in tokens):
        return []
    return [m.span() for m in re.finditer(r"(?<!\w)" + r"\W+".join(map(re.escape, tokens)) + r"(?!\w)", text)]


def _composite(*, recipe: Mapping, source_bytes: bytes, full_derived_asset: Mapping,
               target_locator: Mapping, task_contract: Mapping, requirement: Mapping,
               offline_context=None) -> dict:
    _exact(recipe, RECIPE_FIELDS, "Composite scope recipe")
    policy = _choice(requirement=requirement, kind="SOURCE_BOUND_COMPOSITE_SCOPE_POLICY")
    if (policy["metric_id"] != task_contract["metric_ids"][0]
            or policy["mechanism"] != "SOURCE_BOUND_COMPOSITE_SCOPE_PROOF_V1"):
        raise CompositeScopeError("Composite scope is not authorized for this task")
    if offline_context is None:
        structure = index_source_structure(source_bytes=source_bytes)
    else:
        if offline_context._structure is None:
            offline_context._structure = index_source_structure(source_bytes=source_bytes)
        structure = offline_context._structure
    if len(structure["tables"]) != len(full_derived_asset["tables"]):
        raise CompositeScopeError("Source structure/full DerivedAsset table census differs")
    table = next((t for t in full_derived_asset["tables"] if t["table_id"] == target_locator["table_id"]), None)
    if table is None:
        raise CompositeScopeError("Composite target table is absent")
    table_span = deepcopy(structure["tables"][table["order"]])
    heading = _node(locator=recipe["section_heading"], structure=structure, source_bytes=source_bytes, allow_table_heading=True)
    end_heading = _node(locator=recipe["section_end_heading"], structure=structure, source_bytes=source_bytes, allow_table_heading=True)
    association = _node(locator=recipe["association_heading"], structure=structure, source_bytes=source_bytes, allow_table_heading=True)
    association_end = _node(locator=recipe["association_end_heading"], structure=structure, source_bytes=source_bytes, allow_table_heading=True)
    table_association = _node(locator=recipe["table_association_span"], structure=structure, source_bytes=source_bytes)
    measure = recipe["target_measure_name"]
    if (type(measure) is not str or not measure
            or not _alias_occurrences(text=table_association["visible_text"], alias=measure)
            or not association["end_byte"] <= table_association["start_byte"] < table_association["end_byte"] <= table_span["start_byte"]
            or any(table_association["end_byte"] <= t["start_byte"] < table_span["start_byte"] for t in structure["tables"])):
        raise CompositeScopeError("Original source does not associate the named measure with the immediate target table")
    if (re.search(r"market\s+risk", heading["visible_text"], flags=re.IGNORECASE) is None
            or not heading["start_byte"] <= association["start_byte"] < table_span["start_byte"]
            or not table_span["end_byte"] <= association_end["start_byte"] <= end_heading["start_byte"]
            or association["end_byte"] > association_end["start_byte"]):
        raise CompositeScopeError("Target table is not in the audited named market-risk subsection")
    # Coordinates are supplied by offline audit; association is an exact
    # document-order interval between real heading nodes, not a TOC guesser.
    for block in structure["blocks"]:
        if (association["end_byte"] <= block["start_byte"] < table_span["start_byte"]
                and block["tag"] == association["tag"] and block["attributes"] == association["attributes"]
                and block["visible_text"].strip() == association["visible_text"].strip()):
            raise CompositeScopeError("Target association crosses a competing subsection heading")
    allowed = list(policy["scope_dimensions_allowed_from_text_span"])
    required = dict(policy["required_scope"])
    selected = recipe["selected_scope_spans"]
    if (type(selected) is not list or [x.get("dimension") for x in selected] != allowed
            or set(required) != set(allowed)):
        raise CompositeScopeError("Composite selected dimensions are not the exact authorized set")
    selected_records, normalized = [], {}
    from .evidence import _bounded_raw_value_match
    for item in selected:
        _exact(item, frozenset({"dimension", "raw_value", "start_byte", "end_byte"}), "Selected source scope span")
        node = _node(locator={key: item[key] for key in ("start_byte", "end_byte")},
                     structure=structure, source_bytes=source_bytes)
        if not association["end_byte"] <= node["start_byte"] < node["end_byte"] <= association_end["start_byte"]:
            raise CompositeScopeError("Scope span leaves the target-table association")
        canonical = exact_enum_alias(contract=task_contract["scope_contract"],
                                     dimension=item["dimension"], raw_value=item["raw_value"])
        if (canonical != required[item["dimension"]]
                or not _bounded_raw_value_match(raw_text=node["visible_text"], raw_value=item["raw_value"])
                or not _alias_occurrences(text=node["visible_text"], alias=measure)):
            raise CompositeScopeError("Source span does not prove the approved exact scope alias")
        normalized[item["dimension"]] = canonical
        selected_records.append({**item, "canonical_value": canonical, "source_span": node})
    census = []
    aliases = task_contract["scope_contract"]["exact_enum_aliases"]
    for block in structure["blocks"]:
        if block["inside_table"]:
            continue
        if not heading["end_byte"] <= block["start_byte"] < block["end_byte"] <= end_heading["start_byte"]:
            continue
        for dimension in allowed:
            for canonical, values in aliases[dimension].items():
                occurrences = sorted({span for alias in values
                                      for span in _alias_occurrences(text=block["visible_text"], alias=alias)})
                if not occurrences:
                    continue
                inside = association["end_byte"] <= block["start_byte"] < block["end_byte"] <= association_end["start_byte"]
                disposition = ("SUPPORTING_SAME_SCOPE" if canonical == required[dimension]
                               else "CONFLICTING_SCOPE") if inside else "OUTSIDE_TARGET_SUBSECTION"
                measure_dispositions = []
                if disposition == "CONFLICTING_SCOPE":
                    # A source can explicitly discuss another declared measure
                    # in the same subsection. Only a same-sentence exact named
                    # forbidden-confusion label (not a fuzzy guess or generic
                    # single adjective) can disposition that other measure.
                    for occurrence_start, occurrence_end in occurrences:
                        sentence_start = block["visible_text"].rfind(". ", 0, occurrence_start) + 2
                        if sentence_start == 1:
                            sentence_start = 0
                        sentence_end = block["visible_text"].find(". ", occurrence_end)
                        if sentence_end < 0:
                            sentence_end = len(block["visible_text"])
                        sentence = block["visible_text"][sentence_start:sentence_end]
                        labels = [label for label in task_contract["forbidden_confusions"]
                                  if len(label.split()) >= 2
                                  and _alias_occurrences(text=sentence.casefold(), alias=label.casefold())]
                        if (len(labels) != 1
                                or _alias_occurrences(text=sentence.casefold(), alias=measure.casefold())):
                            raise CompositeScopeError("Conflicting same-subsection scope blocks auto-certification")
                        measure_dispositions.append({"named_measure": labels[0],
                            "sentence_start": sentence_start, "sentence_end": sentence_end,
                            "exact_visible_sentence": sentence})
                    disposition = "DIFFERENT_DECLARED_MEASURE"
                census.append({"start_byte": block["start_byte"], "end_byte": block["end_byte"],
                    "span_sha256": block["span_sha256"], "dimension": dimension,
                    "canonical_value": canonical, "visible_text_occurrences": [list(p) for p in occurrences],
                    "disposition": disposition, "measure_dispositions": measure_dispositions,
                    "unresolved": False})
    return {"mechanism": policy["mechanism"], "recipe": deepcopy(dict(recipe)),
        "section_heading": heading, "section_end_heading": end_heading,
        "association_heading": association, "association_end_heading": association_end,
        "target_measure_name": measure, "table_association_span": table_association,
        "association_rule": "EXACT_AUDITED_HEADING_INTERVAL_AND_ORIGINAL_TABLE_ORDER",
        "target_table_source_span": table_span, "target_table_grid_sha256": table["grid_sha256"],
        "selected_scope_spans": selected_records, "competing_scope_span_census": census,
        "normalized_scope": normalized, "source_structure_hash": content_hash(value={
            "table": table_span, "section": [heading, end_heading], "association": [association, association_end]})}


def load_numeric_policy(*, repo_root: Path, requirement: Mapping) -> dict:
    """Load only the numeric interpretation file bound by current authority."""
    bindings = requirement["execution_authority"]["files"]
    if NUMERIC_POLICY_PATH not in bindings:
        raise CompositeScopeError("Numeric normalization is not in Requirement execution authority")
    path = resolve_repository_file(repo_root=repo_root, repo_relative_path=NUMERIC_POLICY_PATH)
    data = path.read_bytes()
    if (sha256_bytes(content=data) != bindings[NUMERIC_POLICY_PATH]["sha256"]
            or len(data) != bindings[NUMERIC_POLICY_PATH]["size"]):
        raise CompositeScopeError("Numeric normalization authority bytes differ")
    value = strict_json_file(path=path)
    _exact(value, frozenset({"record_type", "schema_version", "bindings"}), "Numeric policy")
    if value["record_type"] != "SOURCE_BOUND_NUMERIC_POLICY" or type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise CompositeScopeError("Numeric policy subtype/version differs")
    seen = set()
    for binding in value["bindings"]:
        _exact(binding, frozenset({"metric_id", "mechanism", "canonical_unit", "reported_unit"}), "Numeric policy binding")
        if (binding["metric_id"] in seen or binding["mechanism"] not in {
                "SAME_ROW_PERCENT_MARKER", "SAME_TABLE_HEADER_SCALE"}):
            raise CompositeScopeError("Numeric policy binding is duplicated or unsupported")
        seen.add(binding["metric_id"])
    return value


def _numeric(*, unit_locator: Mapping, target_locator: Mapping, full_derived_asset: Mapping,
             task_contract: Mapping, requirement: Mapping, repo_root: Path,
             offline_context=None) -> dict:
    policy = load_numeric_policy(repo_root=repo_root, requirement=requirement)
    matches = [b for b in policy["bindings"] if [b["metric_id"]] == task_contract["metric_ids"]]
    if len(matches) != 1:
        raise CompositeScopeError("Numeric mechanism is not authorized for this task")
    binding = matches[0]
    resolver = resolve_cell if offline_context is None else offline_context.resolve_cell
    value_cell = resolver(derived_asset=full_derived_asset, locator=target_locator)
    unit_cell = resolver(derived_asset=full_derived_asset, locator=unit_locator)
    if unit_locator["table_id"] != target_locator["table_id"]:
        raise CompositeScopeError("Numeric normalization crosses the target table")
    # A complete value-cell suffix is already normalized by the native parser;
    # applying a second scale would be a silent double conversion.
    if re.search(r"%|percent|million|billion", value_cell["text"], flags=re.IGNORECASE):
        raise CompositeScopeError("Source value already contains a unit/magnitude suffix")
    table = next(t for t in full_derived_asset["tables"] if t["table_id"] == target_locator["table_id"])
    census = []
    if binding["mechanism"] == "SAME_ROW_PERCENT_MARKER":
        if (unit_cell["text"] != "%" or unit_locator["row_index"] != target_locator["row_index"]
                or unit_locator["origin_column_index"] != target_locator["origin_column_index"] + value_cell["colspan"]):
            raise CompositeScopeError("Percent marker is not the adjacent original same-row cell")
        factor = "0.01"
        census = [{"locator": dict(unit_locator), "raw_text": unit_cell["raw_text"], "factor": factor}]
    else:
        if unit_locator["row_index"] >= target_locator["row_index"]:
            raise CompositeScopeError("Scale locator is not an original header before the value")
        scales = {"million": "1000000", "millions": "1000000", "billion": "1000000000", "billions": "1000000000"}
        selected = re.findall(r"\b(?:million|billion)s?\b", unit_cell["text"].lower())
        if len(selected) != 1:
            raise CompositeScopeError("Header scale is absent or ambiguous")
        factor = scales[selected[0]]
        for row in table["rows"][:target_locator["row_index"]]:
            for cell in row["cells"]:
                if not cell["is_origin"]:
                    continue
                units = re.findall(r"\b(?:million|billion)s?\b", cell["text"].lower())
                if units:
                    found = {scales[unit] for unit in units}
                    if found != {factor}:
                        raise CompositeScopeError("Competing same-table header scales conflict")
                    census.append({"row_index": cell["row_index"], "column_index": cell["column_index"],
                                   "raw_text": cell["raw_text"], "factor": factor})
    native = parse_numeric_claim(raw_value=value_cell["text"], reported_unit=binding["reported_unit"])
    with arithmetic_context():
        normalized = native * parse_decimal(value=factor)
    return {**binding, "policy_path": NUMERIC_POLICY_PATH,
        "policy_sha256": requirement["execution_authority"]["files"][NUMERIC_POLICY_PATH]["sha256"],
        "value_locator": dict(target_locator), "value_raw_text": value_cell["raw_text"],
        "value_text": value_cell["text"], "unit_locator": dict(unit_locator),
        "unit_raw_text": unit_cell["raw_text"], "unit_text": unit_cell["text"],
        "unit_census": census, "factor": factor,
        "normalized_value": decimal_text(value=normalized)}


def build_source_bound_proof(*, requirement: Mapping, repo_root: Path, source_bytes: bytes,
                            raw_blob: Mapping, source_reference: Mapping,
                            full_derived_asset: Mapping, task_contract: Mapping,
                            target_locator: Mapping, numeric_locator: Optional[Mapping] = None,
                            composite_scope_recipe: Optional[Mapping] = None,
                            _offline_context=None) -> dict:
    """Construct exact numeric/narrative facts without mutating source authority."""
    if (requirement["artifact_requirement_generation"] != EXPLICIT_ARTIFACT_GENERATION
            or requirement["requirement_closure_hash"] != content_hash(value=requirement["hashes"])):
        raise CompositeScopeError("Source-bound successor Requirement identity differs")
    for value in (raw_blob, source_reference):
        validate_record(record=value)
    if _offline_context is None:
        validate_record(record=full_derived_asset)
    else:
        from .evidence import OfflineEvidenceContext
        if type(_offline_context) is not OfflineEvidenceContext:
            raise CompositeScopeError("Source-bound offline context type is not exact")
        _offline_context._source_bound_inputs(requirement=requirement, raw_blob=raw_blob,
            source_reference=source_reference, source_bytes=source_bytes,
            derived_asset=full_derived_asset, task_contract=task_contract)
    digest = sha256_bytes(content=source_bytes)
    if (raw_blob["raw_asset_id"] != "sha256:" + digest or raw_blob["byte_length"] != len(source_bytes)
            or source_reference["raw_asset_id"] != raw_blob["raw_asset_id"]
            or list(full_derived_asset["parent_raw_asset_ids"]) != [raw_blob["raw_asset_id"]]):
        raise CompositeScopeError("Source-bound proof source/asset bytes differ")
    resolver = resolve_cell if _offline_context is None else _offline_context.resolve_cell
    resolver(derived_asset=full_derived_asset, locator=target_locator)
    if numeric_locator is None and composite_scope_recipe is None:
        raise CompositeScopeError("Empty enrichment is not a source-bound proof")
    numeric = None if numeric_locator is None else _numeric(unit_locator=numeric_locator,
        target_locator=target_locator, full_derived_asset=full_derived_asset,
        task_contract=task_contract, requirement=requirement, repo_root=repo_root,
        offline_context=_offline_context)
    composite = None if composite_scope_recipe is None else _composite(recipe=composite_scope_recipe,
        source_bytes=source_bytes, full_derived_asset=full_derived_asset, target_locator=target_locator,
        task_contract=task_contract, requirement=requirement, offline_context=_offline_context)
    body = {"record_type": PROOF_TYPE, "schema_version": 1,
        "artifact_requirement_generation": EXPLICIT_ARTIFACT_GENERATION,
        "requirement_id": requirement["requirement_id"],
        "requirement_closure_hash": requirement["requirement_closure_hash"],
        "requirement_hashes": dict(requirement["hashes"]),
        "raw_blob": dict(raw_blob), "source_reference": dict(source_reference),
        "source_sha256": digest, "source_size": len(source_bytes),
        "full_derived_asset_id": full_derived_asset["derived_asset_id"],
        "task_contract_id": task_contract["task_contract_id"],
        "task_contract_hash": task_contract["catalog_task_contract_hash"],
        "metric_id": task_contract["metric_ids"][0], "target_locator": dict(target_locator),
        "numeric_normalization": numeric, "composite_scope": composite,
        "qualification_credit": "NONE_OFFLINE_SOURCE_PROOF"}
    return {**body, "source_bound_proof_id": content_hash(value=body)}


def validate_source_bound_proof(*, proof: Mapping, expected_proof_id: str, **authority) -> dict:
    """Reconstruct the complete proof, including all competing source spans."""
    _exact(proof, PROOF_FIELDS, "Source-bound proof")
    if proof["source_bound_proof_id"] != expected_proof_id:
        raise CompositeScopeError("Source-bound proof differs from the containing scope pin")
    numeric = proof["numeric_normalization"]
    composite = proof["composite_scope"]
    rebuilt = build_source_bound_proof(target_locator=proof["target_locator"],
        numeric_locator=None if numeric is None else numeric["unit_locator"],
        composite_scope_recipe=None if composite is None else composite["recipe"], **authority)
    if dict(proof) != rebuilt:
        raise CompositeScopeError("Source-bound proof source/span/scale/Requirement identity differs")
    return rebuilt


def source_bound_scope(*, proof: Mapping, native_scope: Mapping, task_contract: Mapping) -> dict:
    """Merge only independently proven authorized dimensions, never overwrite."""
    scope = dict(native_scope)
    extra = {} if proof["composite_scope"] is None else proof["composite_scope"]["normalized_scope"]
    for dimension, value in extra.items():
        if dimension in scope and scope[dimension] != value:
            raise CompositeScopeError("Native table scope conflicts with source-bound narrative")
        scope[dimension] = value
    if not scope_satisfies_contract(contract=task_contract["scope_contract"], normalized_scope=scope):
        raise CompositeScopeError("Source-bound scope remains incomplete")
    return scope
