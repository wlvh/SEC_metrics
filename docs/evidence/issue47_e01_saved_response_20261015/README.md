# E01 historical saved-response consumer seam

Progress on #47, based on actualmain97005a37. Public #28 owns HTTP execution, the original allocated ledger, saved-response reader, company CLI and rendering. This branch modifies only the existing historical E01 producer and its small consumer tests/selector. It is not yet a complete executable model-to-company delivery.

## Concrete behavior

prepare_historical_e01_source_context remains AST-identical, including actual fiscal labels/subject, complete event union, amendment checks, declared attachment handling and exact item texts. Existing source-only company factory delegates to finish_historical_e01_case with no reply; completed zero-candidate walks and precise missing-response/source-conflict outcomes remain.

historical_e01_response_factory(response_reader=...) prepares the actual source context first and asks the public reader only when source graph is complete and a matching content answer is required. The callback does not execute a model. Its input is the full current request; saved reply files must be supplied separately as ordinary processing_inputs by the public company dispatcher.

finish_historical_e01_case(context, reviewed_response=None) requires the current request identity/content/company/CIK/window, original_execution_mode LIVE, known nonnegative integer input/output usage, original execution/terminal IDs and raw_output bytes. The shared reader remains responsible for the HTTP terminal, exact saved files and request/response verification. Internal constructed tests exercise the same boundary but grant no model or SEC business credit.

V1 uses the existing item-decision grammar and exact 20–600-character quote validation. Each candidate is answered once. All resolved decisions derive one annual count through the existing Calculator; any CANNOT_TELL keeps the entire window null, without exporting the settled subset. Hallucinated/wrong-block quotes, missing/repeated items and wrong request are rejected. Source conflict, unavailable incorporated source and unsupported successor windows cannot be bypassed by a reply.

The incorporated V2_DEVELOPMENT contract remains development-only: its answer is mechanically summarized and recorded, but never promoted into a metric value. This does not change the adopted V1 definition or extend attachment permission.

Observation provenance explicitly says MODEL_ITEM_DECISIONS_DERIVED_COUNT and retains all decisions/quotes, request/response digest, original execution/terminal IDs and semantic_correctness_verifiedFalse. Mathematical count precision is not legal/M&A semantic acceptance. The shared public renderer must expose that distinction rather than imply an original directly reported structured fact.

## Actual offline verification

91 affected required tests in .222s, zero failures/errors/skips. The new classes run once in the existing fast partition:9tests/.053s/return0. No new runner or whole-company fixture installation. before.log preserves missing-consumer failures; source-preparation-unchanged.json proves the source preparation AST unchanged.

The public controller control uses the real E01 factory/compiled Spec/Calculator/controller with explicitly constructed sources, reply and writer. Stable success does not reread/recalculate; changed reply processes once to whole-window withholding; stable withholding does not process again; original result directories remain. The writer substitute carries the same selected E01 Spec marker as the real writer, retaining the existing rejection of obsolete item-code results. This is a control, not a real live-model first calculation or independent financial result read.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py tests.vnext.test_historical_e01_company_case tests.vnext.test_historical_ma_confirmation tests.vnext.test_historical_e01_incorporated_input tests.vnext.test_history_company_dispatch
```

## Required public integration

The reader callback returns request_id, fullrequest, raw_output bytes, original_execution_mode, usage_known, usage(input_tokens/output_tokens), original_execution_id and original_terminal_id. No new historical file reader/HTTP client is implemented here. Public CLI needs to wire the saved answer selector and its processing input files to this factory, while preserving other families/periods. Public output should retain model-derived provenance and quoted sources.

True first processing, unchanged-response zero processing and independent results/CSV have not yet been demonstrated with actual new authorized responses. They will be run through the fixed shared reader/CLI after integration, initially using the approved small pilot. No old35answer relabelling or paid retry. Actual new SEC/provider/paid0/0/0. Physical executor is public #28 fallback; both environments currently lack API key, and reserved81+1 is not an executed call. Full five-year/1950, source discovery and all E01 semantics remain incomplete. No authorReady/merge/adoption/deploy/active.
