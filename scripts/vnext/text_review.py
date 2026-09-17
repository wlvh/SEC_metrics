"""Render exact source-excerpt review assets through the existing ReviewUnit."""

import re

from .canonical import canonical_json_bytes, sha256_bytes
from .review import build_review_unit


VERSION = "TEXT_SOURCE_REVIEW_V1"


def render_text_review(*, compiled_spec, candidate, evidence_check, source_bindings):
    """Return canonical full context and safely displayed source text."""
    context = {"protocol": VERSION, "compiled_spec": compiled_spec,
               "candidate": candidate, "evidence_check": evidence_check,
               "source_bindings": list(source_bindings)}
    context_bytes = canonical_json_bytes(value=context)

    def literal(text):
        return re.sub(r"([\\`*_{}\[\]()#+.!|<>])", r"\\\1", str(text))

    lines = ["# Source excerpt review", "",
             "These are the registrant's source disclosures, not assertions that the risks occurred.",
             "", "Method: " + literal(candidate.get("method", "AI_TEXT_CANDIDATE")),
             "Spec: " + literal(compiled_spec["spec_closure_hash"]),
             "Evidence: " + literal(evidence_check["evidence_check_id"]), ""]
    for role, claim in sorted(candidate["selected"].items(), key=lambda p: p[1]["order"]):
        lines.extend(["- " + literal(role) + ": " + literal(claim["text"]),
                      "  Source " + literal(claim["source_reference_id"]) + "; bytes "
                      + str(claim["raw_start_byte"]) + "–" + str(claim["raw_end_byte"])
                      + "; SHA256 " + literal(claim["raw_span_sha256"]), ""])
    lines.extend(["## Complete source set", ""])
    for source in source_bindings:
        lines.append("- " + literal(source["source_url"]) + " — " + literal(source["raw_asset_id"]))
    lines.extend(["", "Competing claims: " + literal(candidate["competing_candidates"]),
                  "Unresolved claims: " + literal(candidate["unresolved_competing_claims"]), ""])
    rendered_bytes = "\n".join(lines).encode("utf-8")
    return {"review_context_bytes": context_bytes, "rendered_review_bytes": rendered_bytes,
            "review_context_hash": sha256_bytes(content=context_bytes),
            "rendered_review_hash": sha256_bytes(content=rendered_bytes),
            "review_renderer_semantic_version": VERSION}


def build_text_review_unit(*, compiled_spec, candidate, evidence_check, source_bindings):
    assets = render_text_review(compiled_spec=compiled_spec, candidate=candidate,
        evidence_check=evidence_check, source_bindings=source_bindings)
    unit = build_review_unit(candidate=candidate, evidence_check=evidence_check,
        source_bindings=source_bindings, compiled_spec=compiled_spec,
        review_context_hash=assets["review_context_hash"],
        rendered_review_hash=assets["rendered_review_hash"],
        renderer_semantic_version=VERSION)
    return unit, assets
