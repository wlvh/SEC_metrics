# Current request runtime: confirmed initial failure, not a completed fix

Base main6e51f416, isolated own worktree issue28-current-request-runtime.
Actual socket-denied prepare_requests(company_id=enphase_energy,metric_id=D04)
fails after1.479s at RequirementError Normal candidate rule bytes differ:
scripts/vnext/normal_source_authority.py. Full traceback retained. Source
construction, claim and HTTP have not started. No changed API/runtime code yet.
This reproduces current queue M1 and receiving comment6078826360; it is not
another provider/usage failure or exhausted allowance.

Actual path still loads recursive snapshot, validates execution/semantic rule
byte authority, delegation proof and successor authority. SemanticRequest.validate,
build_plan, transport revalidation, _execute_semantic/wiring and CLI/live_ledger
also reach that old chain. Replacing only the first loader is insufficient.
The existing CallLedger owns count, lock, append claim, duplicate digest, batch
group opportunity and UNKNOWN/usage/402 stops; those are ordinary reliability
and scope duties to retain without changing its real binding/history.
The sole transport is ai_adapter's repository DeepSeek complete ->
_open_provider_request; reference context uses the existing pinned tokenizer.
PR103 supports offline body/config preview but does not fix this actual path.

Next implementation: consume existing ordinary transport/config/source checks
and ledger, replace current request/plan/execution ancestor proof dependencies,
carry RequestLimits through actual SemanticRequest/body/transport and recorded
HTTP seam. Old saved programs remain their own versions. Do not add Requirement
revision, general approval platform, unsafe_mode, alternative provider boundary,
new call scope/limit or response redraw. Real ledger untouched; first proof uses
isolated recorded ledger and only the HTTP boundary substituted, with source
construction/processing/usage/storage real. Source and native-result obligations
are not waived by retiring anti-forgery mechanics.
