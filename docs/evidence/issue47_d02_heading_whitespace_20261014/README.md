# D02 heading indentation: preserve the visible heading format

Responds to [PR249 review 4260733588](https://github.com/wlvh/SEC_metrics/pull/249#discussion_r4260733588) and [receiver reproduction/conditions 4260872498](https://github.com/wlvh/SEC_metrics/pull/249#discussion_r4260872498). Base is actual main c25872ee388c933b697d9d3a9764e5eb7d1859e3. PR259's independent incorporated-caption migration is not included.

A leading newline or non-breaking space inside a paragraph was recorded before the styled inner span. That lost the heading's font size: a lone 10pt procedural subsection could end a 12pt note, falsely excluding the remaining disclosure. The format observer now waits for the first non-whitespace decoded source text. The original block start/end offsets, text, document and source identities are retained.

Two methods are added to the existing TextResultV2SourceTest, already executed by the source-material workflow. Four negative variants use no indentation, newline, newline plus spaces and an HTML non-breaking-space reference. All must refuse the incomplete note; the actual D02 preparation consumer also rejects navigation, rather than creating a shortened disclosure. Four positive variants put whitespace independently on the referenced note or the true following note. They remain located and the actual preparation path retains the court paragraph. Each asserts that the complete document is unchanged. No runner, workflow, model contract, company/year special case or source rewriting is introduced.

Before the production change, two methods produced seven failed subcases in 0.023s (one negative variant was already correct). After the change, the positive consumer assertion initially used a wrong return key and then compared IDs from two different fixture bindings. Those test setup errors were corrected; their logs remain under work, and are not financial-source failures. The final four affected modules pass 65 tests in 0.447s, zero skips:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 -m unittest -v \
  tests.vnext.test_text_results_v2 \
  tests.vnext.test_text_business_candidates \
  tests.vnext.test_text_coverage \
  tests.vnext.test_d02_reviewed_source
```

The three saved Paramount FY2022–FY2024 sources that previously exposed real heading layout differences are checked only at the changed source-navigation seam. The baseline main function and this function receive the same parsed document and original bytes. Their complete proposals are identical: Note20 2859..2924, Note19 2599..2662 and Note19 2830..2891 respectively. Exact source hashes, document IDs and actual times (1.488371/1.261488/1.307344s) are in paramount-source-controls.json. No company first execution, new financial calculation, model/request replay or full five-year census is performed.

Receiver's previous 45-source record remains attached to main/PR249. A new 45-source comparison and new-head CI are receiver checks still to complete; the three-source comparison is not presented as all 45. The repaired constructed consumer rejects unsafe truncation but is not a model/legal content acceptance. Existing source/answers/results and paid-call history are untouched. New SEC/provider/model calls 0/0/0; no Ready, merge, formal adoption, deployment or active switch. Progress on #47.
