# Marriott prior FY2020 audit-reference amendment: source investigation

Progress on #28; current branch starts from actualmain31e4, task/issue28-audit-note-input-scope. This is additional necessary source comparison, not new acquisition, company execution, amended-input admission or an accepted B02 result. Original earlier audit-note/selection/withheld company evidence is reused.

Saved original 0001628280-21-002433 / SHA3b4e35ef3b9aacae886c270b2f76bc98ae42184e2e8bdaef8a7252d9ca11c00d; amendment0001628280-21-006440 / SHA f37221e249636c8a17667b412e7ddf0a038f7d5d6998af7c95c28de654ce2281. Same registered entity/annual report-end. Full source reader and complete visible-block parse were executed on both originals,3.685s, with sockets denied. The first nohup observation had a missing process and empty log; it is not execution evidence. The maintained exec handle completed this read normally. No remote request was made or repeated.

## New verified facts

The amendment repeats the complete report, rather than containing only the explanatory note. Original has2137 visible blocks/amended2134. Raw aligned block diff has166 changes, most involving pagination/reflow; certification/signature sections also change. visible-diff.json retains the complete read findings. They are not all substantive financial changes and not all irrelevant.

There are two separate auditor reports. The first is ICFR, not the financial-statement opinion. The initial audit-report-diff.json captured the ICFR interval and a page-number change; it must not be presented as the financial-opinion correction. The correct financial-statement report is separately extracted and retained in financial-audit-report-diff.json. Removing only actual standalone-number/linked-Table-of-Contents pairs, its word stream changes exactly adverse to unqualified. Actual report heading, entity, signature and original opinion date are preserved.

Complete visible statements/notes up to the actual Item9 boundary:16,372 words on each side, exact word sequence equal after only proven page-navigation omission and ordinary whitespace joining. table-compare.json independently records38 tables/4,776 original cells per side; order, text,header,rowspan,colspan all equal. Original SEC bytes remain untouched, and raw positions/filings are retained in the readings. No blanket script/ID/number deletion is used.

Native comparison provides a different fact: the original has1,346 total facts/1,312 non-DEI, while amendment has34 DEI and zero non-DEI. They are not equal native datasets. The repeated financial body has dropped native tagging; absence of tagged financial facts alone cannot prove financial inputs unchanged. native-compare.json keeps counts/digests/samples; the full3.5MB read is preserved outside Git with path/SHA and is reproducible by compare_native.py. Do not use this fact to grant a new result.

## Current implementation boundary

Current annual_amendment_scope_v2 first looks for an explanatory note extending to a Part heading or cautionary note. Here the next body starts with the linked Table of Contents and all repeated report content before the actual PartII, so the note's8-paragraph guard sees far more than the true two explanatory paragraphs and raises AMENDMENT_EXPLANATORY_SCOPE_UNSUPPORTED. Correcting that boundary alone will not grant input clearance: the existing classification handles only bounded exhibit-link corrections and PartIII additions. Audit-reference correction is not silently classified as one of those.

Marriott FY2021 B02 remains the earlier explicit stable withheld result4b532, not missing source or N/A. Next engineering must bind the true note, complete financial visible/table relations and audit-report correction before proposing/connecting an appropriate source-property rule. If the effective input-policy change requires owner approval, give that exact change and evidence; do not ask which revenue number to choose or make native absence the sole premise. No financial calculation, normal-result credit, production operation or policy relaxation is granted here.

## Reproduction and limits

The code in this folder only reads already saved official originals. It uses the existing source/period/text/native/table parsers and ordinary output files; it builds no trust/permission platform. Full read intermediate is /private/tmp/issue28-audit-originals-20261013.json. Statement/table comparison currently uses the verified fixed source intervals as investigation coordinates, not company/year rules in production. A production successor must locate and validate boundaries generically.

Sources: /Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs, read only. Calls0/0/0; oldresponses/ledger/Run/Result and peer workspace unchanged. This evidence is not a full audit of all report content or an approved amendment model. No receipt is upgraded to success.

## Bounded note boundary implementation

On local base 9cc38cdf (actual main remains 31e4a00d), an uncommitted successor change now ends the explanatory note at a linked contents marker followed by this document's registrant name and the actual Form 10-K contents banner. An isolated link, another issuer, or absent report banner cannot shorten the scope. SEC's slash-delimited two-letter registrant suffix is omitted only for this title comparison; native entity identity and original strings remain unchanged. Extra purposes before that boundary remain part of the note. Legacy blocks-v1 behavior is unchanged.

The first full saved-source run failed because the native name carried /MD/ and the visible title did not (actual-note-after.log); that failed observation is retained. The corrected actual parser run completed in 5.049s (actual-note-fixed.log / actual-note-after.json), locating blocks41..44 with both complete explanatory paragraphs. It still returns UNRESOLVED / AMENDMENT_DECLARED_LIMITED_SCOPE_NOT_PROVEN and does not grant ORIGINAL_STATEMENT_VALUES. This is a parsing fix, not completed B02 or amendment admission. No Calculator/Run/Result was created and no live call was issued.

The 14 layout tests pass in0.004s, including two actual name representations, non-state suffix refusal, foreign/missing banner, preserved additional purpose and existing layout/negation/correction protections. The related full-API regressions are in note-related-tests.log. These tests ran on the local base plus the explicitly recorded source/test difference; no remote SHA or CI coverage is asserted for the uncommitted tree. Full source/statement/table investigation and existing withheld company result are reused.
