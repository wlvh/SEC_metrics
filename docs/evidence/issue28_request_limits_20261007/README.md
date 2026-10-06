# M1 explicit request resource configuration

RequestLimits(output_tokens=4096,max_context_tokens=200000,max_payload_bytes=8388608)
is the existing default. It is resource configuration, not permission, budget,
model/endpoint choice or a new approval object. Frozen dataclass rejects bool,
nonpositive/noninteger fields and output reserve exhausting context.

Actual interfaces:
- continuous_semantic_calls.request_body(request,policy,limits=limits) and
  request_digest(...,limits=limits) retain default bytes/digest; changed output
  is reflected in provider parameters, not used to reset a call opportunity.
- continuous_request_context.measure_request(raw,limits=limits), render_prompt
  and measured_groups use the same max output/context/payload configuration.
- continuous_request_context.with_request_limits(saved_raw,limits=limits)
  validates a saved two-message envelope and creates new bytes changing only
  max_tokens; original bytes/model/messages/schema and Unicode stay intact.
- continuous_semantic_calls.usage_error(raw,limits=limits,
  enforce_total_context=True) checks explicit output/context; missing usage is
  USAGE_UNKNOWN, cost stays null. Omitted limits retains the old checker behavior.

Macy FY2024 B06 fixed8ab4af87 saved input, SHA
bdad31f0dc7b55a5f49f9308c74168b41dd44ee8748156bdfeeabc1ffa7a1966:
actual new API input reference188798 (unchanged), reserve8192, total196990,
maximum200000, fits=True. Only max_tokens differs from original envelope;
new wire SHA2a8da24e7a91973c6d3c031d3459e448b78cd01f500d0e1b12417209a8ee5c9f.
Offline configure+old/new meter0.578s. Reference format/tokens are not provider
usage, actual cost, model extraction accuracy or a live execution.

Seven short regressions0.369s include default literal wire/identity, explicit
8192 format/meter/usage, reserve-total and payload boundaries, unknown usage/cost,
real-tokenized source-preserving grouping, digest resource change and saved
Unicode strings. No synthetic response gets actual extraction/Result credit.

Development consumer example (does not open a socket):

    limits=RequestLimits(output_tokens=8192)
    wire=with_request_limits(saved_request_bytes,limits=limits)
    count=measure_request(wire,limits=limits,require_reference=True)
    assert count['fits']

The same limits must be passed to response checking. No global constant is
mutated. Existing live PreparedSemanticRequest/transport still constructs and
validates its old4096 request; this batch does not connect nondefault limits
to paid execution or grant the necessary purpose/configuration permission.
Old request/response/usage, source and quota are unchanged. Issue47 consumes
this shared interface for its already permitted initial+one substantive
correction; its references/answers/content responsibility remain its own.
Main/default company AI wiring and final target-model validation remain pending.
