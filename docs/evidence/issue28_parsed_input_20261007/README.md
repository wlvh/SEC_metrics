# Fixed parsed D04 input comparison

Main8588 short branch reuses text_coverage, native XBRL and table_grid parses.
No metric selector, language classifier, Calculator or model is run to build
the comparison input. Exact JSON UTF8 is hashed without NFC-changing evidence.
All visible blocks/sections, native facts/contexts/units/namespaces, full tables,
ID/header/footnote and media relationships remain. Embedded script data/code
is retained opaque; an empty external script excluded by the existing D04
visible/native task does not change that input. Raw originals are not edited.
Original raw spans/hashes remain separate for citation lookup.

Real original c372495a(2048661bytes) and archived live2 2068d818(2048769bytes):
1965blocks,68tables and complete retained native/relationship input equal.
Local parsing1.327s/2.130s. The existing archive was read from fixed4227fb98,
SHA10d5e21437f3ceea4d3fd5b20b41076bca35ec0bcdd31173ba0dcd538833db34,
matching its original report; no archive regenerated or source reacquired.

compare_annual_inputs now has an explicit D04 parsed-task option, preserving
its previous default/return shape. It first compares entity, selected filing,
amendments and actual period. New/missing files or unsupported non-HTML body
changes remain changes. For D04, unrelated 8-K additions in submissions do not
change the already compared annual selection; other JSON sources remain raw
conservative. Changed HTML is re-read and checked against its own declared
SHA, then compared through the fixed parser. Real preparation from original
and archived source roots passes PARSED_TASK_INPUT_UNCHANGED in2.223s. It
creates no source authenticity, result or response identity credit.

21directed tests0.226s include unchanged non-business script, changed disclosure,
embedded script payload, quantity/unit/table/header/media/ID relation changes,
subject/period errors, Unicode037E preservation, and the actual comparison entry
(default still marks raw changed; explicit D04 parser compares content).
Synthetic fixtures and real-source preparation/comparison are distinct.

Still incomplete R2: company update control has not yet selected this option,
all AI prompt/model configuration and filing-set responsibilities must be tied
at that caller; old AI request/response/Result are unchanged, not re-signed or
accepted against a new source. This is mechanical change detection, not a
full annual assessment, source admission, provider validation or publication.
It does not generalize D04 equivalence to other metrics. No business calls,
extra budget, account action or production operation.
