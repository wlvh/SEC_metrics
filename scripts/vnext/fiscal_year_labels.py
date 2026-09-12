"""Audit issuer fiscal labels independently of frozen ordinary input rules.

Dates remain the measurement identity. Explicit source definitions, DEI and
Company Facts labels are retained separately; conflicts are never erased by
renaming a machine label an 'analysis year'. No Run or existing label changes.
"""
from datetime import date, datetime
from pathlib import Path
import json
import re

from .canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_loads
from .deterministic_router import parse_accession_xbrl_source
from .governance_signals import _qname
from .normal_annual_input import annual_period, prepare_saved_annual_input
from .normal_source_authority import verify_saved_source_proofs
from .sources import resolve_repository_file
from .text_coverage import _Blocks, _byte_offsets
from .text_results_v2 import _ReportedFactMetadata, _verified_context


_MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
_DATE = _MONTH + r"\s+[0-9]{1,2},\s+[0-9]{4}"
_SINGLE = re.compile(r"References to fiscal\s+(?P<label>[0-9]{4}),?\s+(?:for example,\s+)?refer to the fiscal year end(?:ing|ed)\s+(?P<end>" + _DATE + r")\.", re.I)
_MULTI = re.compile(r"Fiscal years?\s+(?P<labels>[^.;]{1,100}?)\s+ended on\s+(?P<ends>[^.;]{1,150}?),?\s+respectively\.", re.I)
_REFERENCES = re.compile(r"References to\s+(?P<labels>[\"'’“”]*[0-9]{4}[^.;]{0,96}?)\s+are references to the Company[’']s fiscal years ended\s+(?P<ends>[^.;]{1,150}?),?\s+respectively\.", re.I)
_SELF = re.compile(r"^(?:Our|The Company[’']s)\s+fiscal year ends\b", re.I)
_DEI_NAMES = {"documentfiscalyearfocus", "documentperiodenddate", "documentfiscalperiodfocus", "entitycentralindexkey", "documenttype", "entityregistrantname"}


class FiscalYearLabelError(ValueError):
    pass


def _need(condition, reason):
    if not condition:
        raise FiscalYearLabelError(reason)


class _MetadataSpans(_ReportedFactMetadata):
    """Add exact source spans to the existing namespace-aware metadata scan."""
    def __init__(self, text):
        super().__init__()
        self.text = text
        self.lines = [0] + [m.end() for m in re.finditer("\n", text)]
        self.active_dei = []
        self.dei_spans = {}
        self.active_context_spans = []
        self.context_spans = {}

    def _offset(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        namespace, local = _qname(tag, self.stack[-1][1] if self.stack else {})
        if (namespace,local)==("http://www.xbrl.org/2003/instance","context"):
            self.active_context_spans.append((tag,dict(attrs)["id"],self._offset(),len(self.stack)))
        if "contextref" not in dict(attrs):
            return
        metadata = self.facts[self.ordinal]
        namespace, local = metadata["concept"]
        if re.fullmatch(r"https?://xbrl\.sec\.gov/dei/[0-9]{4}", namespace) and local.casefold() in _DEI_NAMES:
            self.active_dei.append((tag, self.ordinal, self._offset(), len(self.stack)))

    def handle_endtag(self, tag):
        if self.active_context_spans and self.active_context_spans[-1][0]==tag and self.active_context_spans[-1][3]==len(self.stack):
            _, key, start, _ = self.active_context_spans.pop()
            self.context_spans[key]=(start,self.text.index(">",self._offset())+1)
        if self.active_dei and self.active_dei[-1][0] == tag and self.active_dei[-1][3] == len(self.stack):
            _, ordinal, start, _ = self.active_dei.pop()
            end = self.text.index(">", self._offset()) + 1
            self.dei_spans[ordinal] = (start, end)
        super().handle_endtag(tag)


def _iso_end(value):
    try:
        return datetime.strptime(value, "%B %d, %Y").date().isoformat()
    except ValueError as error:
        raise FiscalYearLabelError("FISCAL_DEFINITION_DATE_INVALID") from error


class _DefinitionBlocks(_Blocks):
    """Keep HTML quotation context alongside the original visible blocks."""
    def __init__(self, text):
        super().__init__(text)
        self.part_quoted = []

    def _part(self, raw):
        count = len(self.parts)
        quoted = any(row[0] in {"q", "blockquote", "cite"} for row in self.stack)
        super()._part(raw)
        if len(self.parts) > count:
            self.part_quoted.append(quoted)

    def _flush(self):
        count = len(self.blocks)
        quoted = any(self.part_quoted)
        super()._flush()
        if len(self.blocks) > count:
            self.blocks[-1]["quoted_context"] = quoted
        self.part_quoted = []


def _issuer_alias_prefix(prefix, names):
    def words(value):
        return " ".join(re.sub(r"[^a-z0-9\s]", " ", value.casefold().replace("'", "").replace("’", "")).split())
    text = words(prefix)
    return any(text.startswith("unless the context requires otherwise references to " + words(name)
                              + " or the company are references to ") for name in names)


def _definitions(raw, target_end, registrant_names):
    text = raw.decode("utf-8-sig")
    parser = _DefinitionBlocks(text); parser.feed(text); parser.close(); parser._flush()
    _need(not parser.structural_errors and (parser.html_count,parser.body_count,parser.html_closed,parser.body_closed)==(1,1,1,1),
          "FISCAL_LABEL_FULL_DOCUMENT_REQUIRED")
    definitions, unparsed = [], []
    for index, block in enumerate(parser.blocks):
        text_value = block["text"]
        if block["linked"]:
            continue
        matches = [("EXPLICIT_EXAMPLE", m) for m in _SINGLE.finditer(text_value)]
        matches += [("EXPLICIT_ORDERED_YEARS", m) for m in _MULTI.finditer(text_value)]
        matches += [("EXPLICIT_REFERENCE_YEARS", m) for m in _REFERENCES.finditer(text_value)]
        definition_lead = (_SELF.search(text_value) or re.search(r"References to.{0,100}fiscal years? (?:ended|ending)",text_value,re.I))
        if not matches:
            if definition_lead:
                unparsed.append({"block_index":index,"text":text_value,"reason":"DEFINITION_SYNTAX_NOT_SUPPORTED"})
            continue
        for kind, match in matches:
            if block["quoted_context"]:
                unparsed.append({"block_index":index,"text":text_value,"reason":"DEFINITION_IN_QUOTED_CONTEXT"})
                continue
            if kind == "EXPLICIT_REFERENCE_YEARS" and not _issuer_alias_prefix(text_value[:match.start()],registrant_names):
                unparsed.append({"block_index":index,"text":text_value,"reason":"DEFINITION_ISSUER_ALIAS_NOT_PROVEN"})
                continue
            if kind != "EXPLICIT_REFERENCE_YEARS" and not _SELF.search(text_value):
                unparsed.append({"block_index":index,"text":text_value,"reason":"DEFINITION_ISSUER_SUBJECT_NOT_PROVEN"})
                continue
            if kind == "EXPLICIT_EXAMPLE":
                pairs = [{"fiscal_year":int(match["label"]),"period_end":_iso_end(match["end"])}]
            else:
                labels = re.findall(r"[0-9]{4}",match["labels"])
                ends = re.findall(_DATE,match["ends"],re.I)
                label_remainder = re.sub(r"[0-9]{4}|\band\b|[\s,\"'’“”]", "", match["labels"], flags=re.I)
                end_remainder = re.sub(_DATE + r"|\band\b|[\s,]", "",match["ends"],flags=re.I)
                if label_remainder or end_remainder or not labels or len(labels)!=len(ends) or len(set(labels))!=len(labels):
                    unparsed.append({"block_index":index,"text":text_value,"reason":"DEFINITION_ORDERED_MAPPING_NOT_PROVEN"})
                    continue
                pairs = [{"fiscal_year":int(y),"period_end":_iso_end(e)} for y,e in zip(labels,ends)]
            if any(not 1900<=p["fiscal_year"]<=9998 for p in pairs):
                unparsed.append({"block_index":index,"text":text_value,"reason":"DEFINITION_YEAR_LABEL_NOT_SUPPORTED"})
                continue
            offsets = _byte_offsets(text,[block["start"],block["end"]])
            bom = 3 if raw.startswith(b"\xef\xbb\xbf") else 0
            start, end = offsets[block["start"]]+bom, offsets[block["end"]]+bom
            definitions.append({"kind":kind,"block_index":index,"text":text_value,
                "raw_start_byte":start,"raw_end_byte":end,"raw_span_sha256":sha256_bytes(content=raw[start:end]),
                "mapping":pairs,"current_period_labels":[p["fiscal_year"] for p in pairs if p["period_end"]==target_end]})
    return definitions, unparsed


def inspect_fiscal_year_labels(*, primary_bytes: bytes, companyfacts_bytes: bytes,
                              expected_primary_sha256: str, expected_companyfacts_sha256: str,
                              expected_cik: str, filing: dict):
    """Inspect bound source bytes; this pure API grants no acquisition credit."""
    _need(sha256_bytes(content=primary_bytes)==expected_primary_sha256
          and sha256_bytes(content=companyfacts_bytes)==expected_companyfacts_sha256,"FISCAL_LABEL_SOURCE_BYTES_CHANGED")
    period = annual_period(raw=primary_bytes,cik=expected_cik,filing=filing)
    source_text = primary_bytes.decode("utf-8-sig")
    metadata = _MetadataSpans(source_text);metadata.feed(source_text);metadata.close()
    parsed = parse_accession_xbrl_source(raw_bytes=primary_bytes)
    _need(metadata.ordinal==len(parsed.facts) and not metadata.active_dei,"FISCAL_LABEL_DEI_STREAM_INCOMPLETE")
    dei=[]
    for fact in parsed.facts:
        if fact["ordinal"] not in metadata.dei_spans:
            continue
        start_char,end_char = metadata.dei_spans[fact["ordinal"]]
        offsets = _byte_offsets(source_text,[start_char,end_char])
        bom = 3 if primary_bytes.startswith(b"\xef\xbb\xbf") else 0
        start,end=offsets[start_char]+bom,offsets[end_char]+bom
        context={**dict(parsed.contexts[fact["context_ref"]]),"dimensions":dict(parsed.contexts[fact["context_ref"]]["dimensions"]),"context_ref":fact["context_ref"]}
        proof=_verified_context(native=context,metadata=metadata)
        context_start_char,context_end_char=metadata.context_spans[fact["context_ref"]]
        context_offsets=_byte_offsets(source_text,[context_start_char,context_end_char])
        context_start,context_end=context_offsets[context_start_char]+bom,context_offsets[context_end_char]+bom
        dei.append({"concept_namespace":metadata.facts[fact["ordinal"]]["concept"][0],
            "concept":metadata.facts[fact["ordinal"]]["concept"][1],"value_raw":fact["text"],
            "ordinal":fact["ordinal"],"context":context,"verified_context":proof,
            "context_locator":{"raw_start_byte":context_start,"raw_end_byte":context_end,
                               "raw_span_sha256":sha256_bytes(content=primary_bytes[context_start:context_end])},
            "raw_start_byte":start,"raw_end_byte":end,"raw_span_sha256":sha256_bytes(content=primary_bytes[start:end])})
    cf=strict_json_loads(text=companyfacts_bytes.decode("utf-8"))
    _need(type(cf.get("cik")) in (int,str) and str(cf["cik"]).isdigit() and int(cf["cik"])==int(expected_cik),
          "FISCAL_LABEL_COMPANYFACTS_ENTITY_CONFLICT")
    cf_rows=[]
    for taxonomy, concepts in cf["facts"].items():
        for concept, data in concepts.items():
            for unit, rows in data["units"].items():
                for index, fact in enumerate(rows):
                    if fact.get("accn")==filing["accessionNumber"]:
                        cf_rows.append({"locator":{"taxonomy":taxonomy,"concept":concept,"unit":unit,"index":index},
                            "fiscal_year_raw":fact.get("fy"),"period_start":fact.get("start"),"period_end":fact.get("end"),
                            "form":fact.get("form"),"fiscal_period":fact.get("fp"),"filed":fact.get("filed")})
    _need(bool(cf_rows),"FISCAL_LABEL_SAME_ACCESSION_COMPANYFACTS_MISSING")
    cf_labels=sorted({r["fiscal_year_raw"] for r in cf_rows if type(r["fiscal_year_raw"]) is int})
    invalid_cf=[r for r in cf_rows if type(r["fiscal_year_raw"]) is not int or not 1900<=r["fiscal_year_raw"]<=9998]
    registrant_names = sorted({f["value_raw"] for f in dei if f["concept"].casefold() == "entityregistrantname"
        and str(f["context"]["entity_identifier"]).isdigit()
        and int(f["context"]["entity_identifier"]) == int(expected_cik)
        and f["context"]["period_end"] == period["period_end"] and not f["context"]["dimensions"]})
    definitions,unparsed=_definitions(primary_bytes,period["period_end"],registrant_names)
    labels=sorted({y for d in definitions for y in d["current_period_labels"]})
    machine={period["fiscal_year"],*cf_labels}
    unresolved_current=[u for u in unparsed if re.search(r"(?:"+_MONTH+r")\s+[0-9]{1,2},\s*"+period["period_end"][:4],u["text"],re.I)]
    if len(labels)>1 or unresolved_current:
        status="EXPLICIT_DEFINITION_UNRESOLVED"
        proposed=None
    elif len(labels)==1:
        proposed=labels[0]
        status="SOURCE_LABEL_CONFLICT" if machine!={proposed} or invalid_cf else "SOURCE_LABELS_CONSISTENT"
    else:
        status="SOURCE_LABEL_CONFLICT" if len(machine)>1 or invalid_cf else "METADATA_LABEL_ONLY"
        proposed=None
    body={"record_type":"FISCAL_YEAR_LABEL_SOURCE_INSPECTION","schema_version":1,
        "source_validation":"HASH_BOUND_BYTES_ONLY","primary_sha256":expected_primary_sha256,
        "companyfacts_sha256":expected_companyfacts_sha256,"accession":filing["accessionNumber"],"entity":str(int(expected_cik)),
        "actual_period":{"period_start":period["period_start"],"period_end":period["period_end"]},
        "dei_fiscal_year":period["fiscal_year"],"dei_facts":dei,"registrant_names":registrant_names,
        "companyfacts_fiscal_year_values":cf_labels,
        "companyfacts_same_accession_row_count":len(cf_rows),"companyfacts_rows":cf_rows,"invalid_companyfacts_fy_rows":invalid_cf,
        "companyfacts_fy_interpretation":"FILING_METADATA_LABEL_NOT_EACH_FACT_MEASUREMENT_YEAR",
        "source_definitions":definitions,"unsupported_definition_leads":unparsed,"current_definition_labels":labels,
        "status":status,"source_defined_fiscal_year":proposed,"analysis_group_year":None,
        "analysis_group_year_policy":"NOT_DEFINED_BY_THIS_COMPONENT_OR_EXISTING_NORMAL_INPUT",
        "new_rule_label_proposal":proposed,"existing_input_or_Run_changed":False,
        "production_authorized":False}
    canonical_json_bytes(value=body)  # Validate JSON types without rewriting original source characters.
    body=strict_json_loads(text=json.dumps(body,ensure_ascii=False,allow_nan=False))
    return {**body,"inspection_id":content_hash(value=body)}


def _inspect_prepared_input(*, repo_root: Path, prepared: dict):
    admission=verify_saved_source_proofs(data_root=repo_root,proofs=prepared["source_proofs"])
    def raw_input(item):
        return resolve_repository_file(repo_root=repo_root,repo_relative_path=item["source_repo_relative_path"]).read_bytes()
    primary, facts=raw_input(prepared["table_input"]),raw_input(prepared["companyfacts_input"])
    inspected=inspect_fiscal_year_labels(primary_bytes=primary,companyfacts_bytes=facts,
        expected_primary_sha256=sha256_bytes(content=primary),expected_companyfacts_sha256=sha256_bytes(content=facts),
        expected_cik=prepared["entity"],filing=prepared["filing"])
    return {"inspection":inspected,"prepared_input":prepared,"source_admission":admission,
            "source_proofs":prepared["source_proofs"],"calls":{"provider":0,"paid":0,"sec":0},
            "native_run_status":"NOT_CREATED","production_authorized":False}


def inspect_saved_fiscal_year_label(*, repo_root: Path, company_id: str):
    prepared=prepare_saved_annual_input(repo_root=repo_root,company_id=company_id)
    return _inspect_prepared_input(repo_root=repo_root,prepared=prepared)
