# What each C02 reader was told besides the brief

One reader per position: a fresh-context subagent of the same model family as
the executor, not a person. Every reader got `reader-brief.md` verbatim, the
path of its one packet, where to write its answer, and the same wrapper - no
reader was given an example drawn from an earlier finding, the selector's
rules, or any other reading:

> You are an independent reader for one packet. The brief below is your whole
> instruction on what counts; read it first. Judge every SELECTED block
> exactly once, and list only POOL blocks that state a composition fact, each
> with the other blocks in the packet that state the same fact. Every verdict
> is your own reading of the text: you may use Python only to print or search
> the packet's blocks, to write the answer JSON and to check that every
> SELECTED block is judged once - never to decide a verdict by a keyword or a
> program rule. Use only the brief and the packet: open no other file in the
> repository or the scratch directory. Modify nothing except the answer file.
> When done, report the counts of FACT, MIXED and NOT among the selected
> blocks, how many pool facts you listed, and anything notable about the
> filing's layout.

The answers were merged by `tools/read_c02_composition.py --merge`, which
refuses an answer that leaves a selected block unjudged, judges one twice, or
lists as a found fact a block that is not in the pool.
