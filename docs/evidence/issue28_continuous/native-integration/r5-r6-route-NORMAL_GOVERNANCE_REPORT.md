# Normal C03/C04 source discovery increment

The adapter now starts with normal_annual_input.prepare_saved_annual_input and its subject_policy, discovers filing identities from current-subject SEC submissions/current/history bodies, and returns actual source proofs and native resolver arguments. No outputs/latest_filings_inventory.csv, material inventory, old result, fixed company answer, manual source_role argument or fabricated request attempt is used. Data-root registry bytes must equal the installed configured scope.

Entry: prepare_saved_governance_input(repo_root, company_id).
- input_binding contains prepared annual input, subject policy, complete relevant metadata, ordered current/prior amendment chains, latest same-CIK proxy/absence, accession index/XML material sets, exact successful source_proofs, source_bindings, failed_source_attempts, history conflicts and metric_input_status.
- source_proofs is directly consumable by normal_source_authority.verify_saved_source_proofs.
- records contains the native RawBlob and SourceReference records; resolver_inputs contains bytes/native records plus resolver arguments and explicit Spec paths.
- source-set manifests are bound separately in input_binding; they are not falsely appended as a different existing native record type.
- no resolver, Run freeze, network fetch, publication or grant occurs in the preparation API.

C04 v2 is explicit and leaves v1 unchanged. It includes 8-K and 8-K/A, uses the existing native adapter, and retains ordered current/prior amendment chains before original fallback. An actual current conflict stops fallback. Metadata date order uses actual acceptance timestamps when same-day filings require disambiguation.

Actual normal-material run (292 successful real request proofs, all independently accepted by the installed source baseline):
- C03: all10 companies yield a supported original-source value:9 ECD and Paramount's current PartIII SCT. Paramount remains63,211,569USD for actual2025-08-07 to2025-12-31, not a fabricated whole-year or predecessor value.
- C04:7 numeric zero flags; Paramount preserves current PwC but no same-CIK comparable prior; Salesforce stops at the actually latest failed header GET; JPM stops at inconsistent saved current-index/history-body coverage.
- Marriott8-K/A0001193125-25-118861 and Macy's8-K/A0000794367-25-000165 are included as8-K/A, never relabeled8-K.

Important findings preserved rather than bypassed:
1. Repeated legacy GETs can make saved_source's automatic selector ambiguous. Only that exact error uses existing validate_request_attempt_binding against the validated ledger's final real GET; the original LEGACY_WORKING_LOCATOR classification and real request:attempt ID remain. A later failed GET cannot fall back to an older200.
2. Salesforce header0001108524-25-000083 has final failed row844, request:attempt:7cd5ba82de3138295c0fcaa8499597bca7f3ca6b16bbc11ea723b261eaf5bf44, timestamp2026-07-09T08:56:16.899501+00:00, status0, SSL EOF. C03 continues; C04 cannot claim a complete event set.
3. JPM current metadata declares history001 as2025-07-15 to2025-08-13, while saved history001 contains July1 events. Histories002–006 show similar shifts. These authentic saved bytes do not constitute a coherent source snapshot. The adapter records all explicit conflicting rows and isolates C04; it does not weaken the dates check or claim source nondisclosure. The initial company-wide failure is retained separately; current C03 remains available from its sufficient current source.

Validation:
- test_normal_governance_input:14 tests PASS, including actual request-proof selection, no derived-inventory/result reads or network, registry relabel refusal, latest failed request protection, metadata conflict/history absence, exact filing order,8-K/A deletion and v2 amendment chains.
- unchanged/current test_governance_signals:22 PASS; combined36 tests PASS.
- normal_governance_probe.py:10-company actual discovery→installed source authority→native resolver composition, no unexpected errors.
- normal_governance_probe.py --replay:new process reproduced each final input binding, native source records, source authority receipt and resolver output.
- portable_normal_probe.py:new process using minimal imported data roots with no.git reproduced Marriott (61 files,29 real proofs) and Paramount (35 files,16 real proofs), including actual short-period SCT. No code repository/worktree was copied into these data roots.

Files:normal_governance_summary.json, normal_governance_probe.json, normal_governance_material_final.log, normal_governance_cold_replay.log, normal_governance_portable.log, portable_normal_probe.json, normal_governance_implementation_hashes.json. No commit/push/production operation was performed by this subtask; provider/paid/SEC remains0/0/0.

Integration cautions:PREPARED is input availability, not metric success or permission. Consult metric_input_status and limitations before final acceptance; do not use a readable fallback to hide source/semantic conflicts. verify_current_governance_preparation re-discovers current state; historical frozen Run replay must use its pinned proofs rather than retargeting to a later input. The parent owns Requirement/Run/publication integration and permissions for any refresh of the blocked sources.
