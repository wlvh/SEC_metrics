import pathlib,difflib
root=pathlib.Path('/Users/lyuhongwang/Developer/SEC_metrics');out=pathlib.Path('/tmp/sec_metrics_issue28_continuous')
p=root/'scripts/vnext/normal_companyfacts_results.py';old=p.read_text();new=old
old_gate='''    common_error = ("NORMAL_COMPANYFACTS_SUCCESSOR_SCOPE_NOT_IMPLEMENTED" if prepared["subject_policy"]["mode"] != "CONTINUOUS_PRIMARY"
        else "NORMAL_COMPANYFACTS_CURRENT_AMENDMENT_REPLAY_NOT_IMPLEMENTED" if prepared["amendments"] else None)'''
new_gate='''    amendment_input = None
    common_error = "NORMAL_COMPANYFACTS_SUCCESSOR_SCOPE_NOT_IMPLEMENTED" if prepared["subject_policy"]["mode"] != "CONTINUOUS_PRIMARY" else None
    if prepared["amendments"] and common_error is None:
        amendment_input = prepare_saved_amendment_input(repo_root=repo_root,company_id=company_id,input_class="ORIGINAL_STATEMENT_VALUES")
        _need(amendment_input["prepared_input"] == prepared.get("original_input",prepared), "NORMAL_AMENDMENT_ORIGINAL_INPUT_DIFFERS")
        if amendment_input["decision"] != "INPUT_PROPERTY_PROVEN":
            common_error = "NORMAL_COMPANYFACTS_AMENDMENT_INPUT_SCOPE_UNRESOLVED"'''
replacements=[
 ('from .normal_annual_input import annual_period, _registry_rows, NormalAnnualInputError','from .normal_annual_input import annual_period, _registry_rows, NormalAnnualInputError\nfrom .annual_amendment_scope import prepare_saved_amendment_input'),
 (old_gate,new_gate),
 ('    admission = verify_saved_source_proofs(data_root=repo_root, proofs=proofs)\n    body =', '''    if amendment_input is not None:
        proofs = list({content_hash(value=p):p for p in [*proofs,*amendment_input["source_proofs"]]}.values())
    admission = verify_saved_source_proofs(data_root=repo_root, proofs=proofs)
    source_records = list(reader.records.values())
    if amendment_input is not None:
        source_records = list({content_hash(value=r):r for r in [*source_records,*amendment_input["source_records"]]}.values())
    body ='''),
 ('"source_records":list(reader.records.values()),','"source_records":source_records,"amendment_input":amendment_input,')
]
for a,b in replacements:
 assert new.count(a)==1,a
 new=new.replace(a,b)
(out/'companyfacts-amendment-route-candidate.py').write_text(new)
(out/'companyfacts-amendment-route-candidate.patch').write_text(''.join(difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True),fromfile=str(p),tofile=str(out/'companyfacts-amendment-route-candidate.py'))))
