# Deviations Log

Every change made after the preregistration freeze tag goes here. No entry, no
change — if it isn't logged, it didn't happen.

|Date|What changed|Where|Why|Impact on analysis|
|-|-|-|-|-|
|*(example)* 2026-07-10|Pinned openai model to a dated snapshot|config.json|provider deprecated alias mid-study|none; recorded in run metadata|
| 2026-07-05 |Specified FKGL preprocessing for the registered `fkgl` measure (strip markdown marks; treat each line as a sentence)|CODEBOOK.md|Frozen codebook did not specify FKGL preprocessing. textstat treats period-free bullet lists as single sentences, inflating FKGL (pilot: one response scored 51.2 raw, 10.2 cleaned; raw FKGL masks the H1 register contrast on one provider). Rule derived from pilot data only, adopted before any confirmatory data was analyzed.|H1 uses cleaned FKGL; raw FKGL reported alongside as a robustness check.|

## Pre-freeze changelog (for transparency; not deviations)

* 2026-07-05: Stem D urgency clause ("can't reach my mom") moved from the main
minor cells to two exploratory variant cells, so the confirmatory minor cells
are urgency-free.
* 2026-07-05: txt-speak ("u", "r") excluded from the lowlit transformation to
avoid leaking a youth register into the literacy manipulation.
* 2026-07-05: Stem B minor-adjacent cells standardized to the same question
content ("Can they actually do that? What can we do?") rather than a
role-shifted "how can I help her" framing, to hold propositional content
constant across the age axis.

