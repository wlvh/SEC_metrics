# Ordinary source discovery evidence

This increment lists source dependencies from the installed saved-acquisition baseline. It makes no SEC/provider request, creates no Run and grants no new-source or production credit. The existing V14 draft remains f7352d6cffff8d28f18315c2acf2ff16205567b32d41cd526e2afb1327c95284 / 325 execution files; this discovery CLI is outside that execution closure.

Actual ten-company CLI: `PYTHONDONTWRITEBYTECODE=1 python3 tools/vnext_normal_update.py --discover-sources --output /tmp/sec_metrics_issue28_continuous/normal-source-requirements-ten.json`. Exit 2 retains all ten companies: 305 known GET URLs, 27 refresh datasets, eight missing/failed document URLs. JPM metadata is incoherent, so its downstream source inventory remains unproven. The other missing files are not all necessary for every metric; available XML can still serve supported routes.

Tests: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_normal_source_requirements` — eight PASS, 14.557s. The same command with `/usr/bin/python3` — eight PASS, 20.307s. Actual originals plus isolated missing-primary/index, changed-body, wrong directory/unsafe name and future-metadata cases. No legacy answers or network. Root implementation/testing is not another independent-agent approval.

`python3 tools/check_vnext_semantics.py` initially wrote its default tracked derived receipt. That exact generated receipt was copied here, and its only unintended root-output change was restored byte-for-byte from the previously clean HEAD. No active pointer or public matrix was changed. The scan returned PASS; subsequent egress/company scans explicitly used external outputs and PASS. This retained receipt is scan evidence, not a validation snapshot.

GitHub run34697238314 belongs to preceding b69cdacbd83659efc55645a19f3658ed6b32771a: all three jobs SUCCESS, including lodging native construction and adversarial replay. Its complete original log and terminal JSON are retained without treating them as CI for this increment.

New-source acquisition, normal fresh-source computations, D03/D04/B13, remaining source/subject/debt gaps, full390 integration, independent review and production confirmation remain required. Old closed calls remain closed.

The complete CLI JSON is stored as deterministic gzip to keep generated data out of the textual review diff. Decompression was byte-compared to the actual original output; both digests are in the manifest. The adjacent summary JSON remains directly readable.
