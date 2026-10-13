# Explicit current B04 through finite online company entry

Base actual main c25872ee. Only allow the existing B04 producer in the online
selection; no new parser/calculator, prior-year requirement, AI pipeline, live
permission or budget. Preserve the previous no-metric B01/B02 default. A B04
call still requires an existing applicable context whose metric scope includes
B04; a B01/B02-only context rejects before capture/claims. No-context retained
native and saved-source entries keep their behavior.

Both actual tests start empty source/task roots, use original saved SEC HTTP
replies through RecordedSecHttpClient, and execute real discovery, persistence,
latest selection, B04 calculation/writer, repeated controller and independent
results/CSV. No producer/install/selection/calculation mock supplied answers.
Only sockets are forbidden and HTTP is the existing recorded boundary. The
fake ledgers are explicit RECORDED_TEST_ONLY and do not touch real195 claims.

- Marriott FY2025: 2601m USD, 2025-01-01–2025-12-31, CIK1048286,
  accession0001048286-26-000007. First5.086007s, forbidden-factory repeat1.067646s,
  independent reader0.420354s. Same58ed6c58 result and output files.
- Salesforce FY2026: 7457m USD, 2025-02-01–2026-01-31, CIK1108524,
  accession0001108524-26-000060. First5.314113s, forbidden-factory repeat1.100158s,
  independent reader0.317120s. Same765d46c2 result; rawCF FY2025 is not relabelled
  as the actual issuer FY2026 except by the existing verified annual selection.
- Marriott injected recorded submissions503: actual discovery/metric failed
  0.051134s; old successful files preserved. Original reply restored:2.085573s,
  no calculation, original same result. Failure is not cached as a success.

First captures5 replies; unchanged repeat refreshes2 metadata replies, as the
existing online workflow does, without re-fetching immutable annual/instance
files. This does not promise zero SEC metadata verification on a real repeat.
Every real new provider/paid/SEC count remains0/0/0. Recorded claim counters are
separate in the summaries. The claim/unknown/stop/no-retry logic is unchanged.

One small dispatch/scope regression first red, 19 online controls3.137s,
71 affected online/current-statement/company controls11.857s, zero skips.
Actual CLI used the named uncommitted three-file patch; summary code hashes
identify that state. Candidate head and tree are separately reported in PR.
Existing current B04 source semantics, source/period/unit/business limits and
unaccepted content status remain. No real new SEC acquisition, no model result,
no all-ten or all39 online acceptance, Ready/merge/adoption/deploy/active.

On the candidate, with an already applicable context:

```sh
python3 tools/vnext_company.py run --company marriott_international \
  --call-context /path/to/existing-applicable-context.json --metric B04 \
  --work-dir /path/to/new-task --output-dir /path/to/output --max-sec-requests 20
python3 tools/vnext_company.py results --company marriott_international \
  --state-root /path/to/task/company-state --output-root /path/to/read-output
```

Read-only sources preflight is still B01/B02/B03/E01; this candidate does not
quietly add B04 there. Historical online discovery, additional online metrics,
model permissions and all390 business acceptance remain incomplete.

First-head company-history CI failure was read and reproduced: the B03 source-preflight control still equated the entire online set with the former defaults. It now checks old B01/B02 defaults separately from explicit B04 admission and still forbids B03 online acquisition; the original no-fetch/no-execution B03 assertions remain. The same five affected modules were rerun; exact result is in ci-scope-regression-after.log. No business value/period/unit/subject or failure assertion was deleted.
