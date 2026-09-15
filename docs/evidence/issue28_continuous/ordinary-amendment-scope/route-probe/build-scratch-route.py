import pathlib,difflib
root=pathlib.Path('/Users/lyuhongwang/Developer/SEC_metrics');out=pathlib.Path('/tmp/sec_metrics_issue28_continuous')
p=root/'scripts/vnext/normal_zero_ai_results.py';old=p.read_text();new=old
replacements=[
 ('from .annual_update import AnnualUpdateError','from .annual_update import AnnualUpdateError\nfrom .annual_amendment_scope import prepare_saved_amendment_input'),
 ('    dependency_specs, dependency_records = {}, []','    dependency_specs, dependency_records = {}, []\n    amendment_input = None'),
 ('        _need(not prepared["amendments"], "NORMAL_ZERO_AI_AMENDMENT_REPLAY_NOT_IMPLEMENTED")','''        if prepared["amendments"]:
            amendment_input = prepare_saved_amendment_input(repo_root=repo_root,company_id=company_id,
                input_class="ORIGINAL_STATEMENT_VALUES" if metric_id in {"B01","B03"} else "FISCAL_EVENT_WINDOW")
            _need(amendment_input["prepared_input"] == prepared.get("original_input",prepared),
                  "NORMAL_AMENDMENT_ORIGINAL_INPUT_DIFFERS", "SOURCE_INTEGRITY_ERROR")
            _need(amendment_input["decision"] == "INPUT_PROPERTY_PROVEN", "NORMAL_AMENDMENT_INPUT_SCOPE_UNRESOLVED")
            filing_rows.extend(s["amendment"]["filing"] for s in amendment_input["scopes"])'''),
 ('    proofs = prepared["source_proofs"] + [entry["proof"] for entry in reader.proofs.values()]','    proofs = prepared["source_proofs"] + [entry["proof"] for entry in reader.proofs.values()]\n    if amendment_input is not None: proofs.extend(amendment_input["source_proofs"])'),
 ('    source_records = list(reader.records.values())','''    source_records = list(reader.records.values())
    if amendment_input is not None:
        source_records = list({content_hash(value=r):r for r in [*source_records,*amendment_input["source_records"]]}.values())'''),
 ('    input_binding = {"prepared_input":prepared,"target":target,"target_period":period,','    input_binding = {"prepared_input":prepared,"target":target,"target_period":period,"amendment_input":amendment_input,')
]
for a,b in replacements:
 assert new.count(a)==1,a
 new=new.replace(a,b)
(out/'zero-ai-amendment-route-candidate.py').write_text(new)
(out/'zero-ai-amendment-route-candidate.patch').write_text(''.join(difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True),fromfile=str(p),tofile=str(out/'zero-ai-amendment-route-candidate.py'))))
