# Current B06 input and amendment evidence

Read validation-summary.json. Native material retains the current original and amendment in an OPEN Run; the existing unsupported Paramount debt-table result stays WITHHELD. Removal of original amendment bytes and self-signed omission of input checks both reject. Three previously working B06 results and four native graph attacks passed independently.

First failures remain separate: the new and two existing debt rejection paths initially passed extra target fields to the WITHHELD calculator (implementation fixed); the first material test guarded installer writes too broadly (test fixed); the second test correctly rejected a missing RawBlob but expected the wrong exception type (test fixed). The second intact baseline was successfully cold-replayed with copied runtime and no Git; it was not relabelled as a successful complete test run.

The archive has the complete final clean baseline and actual altered Run/binding controls, verified by member SHA/size. Unchanged duplicate attack data directories are indexed and can be rebuilt by the checked-in test. Raw source/log files with large bodies or trailing whitespace are losslessly compressed and read back. No budget, independent approval, source freshness or production completion is claimed.
