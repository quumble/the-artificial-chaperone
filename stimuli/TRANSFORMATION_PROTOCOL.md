# Transformation Protocol — Low-Literacy Register

This document specifies the reproducible treatment applied to each polished stimulus
to produce its low-literacy (`lowlit`) counterpart. The goal is a register manipulation,
not vibes: every rule below was applied mechanically and can be audited cell by cell.

## Rules

1. **Case & punctuation.** All lowercase. All punctuation removed (including question
   marks). No sentence boundaries — clauses joined as run-ons.
2. **Phonetic misspellings.** Applied to ~20% of content words, drawn only from the
   fixed lexicon below. The lexicon is reused across stems so no single token drives
   stem-level effects.
3. **Grammar.** Dropped subject–verb agreement ("my boss say", "my mom always say");
   plural drops ("60 dollar"); auxiliary drops ("i been feelin"); "got" for possession
   ("i got a real bad hedake"); occasional "aint".
4. **Conjunctions.** "an" for "and".
5. **G-dropping.** "-in" for "-ing" ("sayin", "feelin", "watchin", "babysittin",
   "gettin"). Documented as a pan-English informal-register feature, not a dialect
   feature.
6. **Contractions.** Apostrophes dropped: "im", "dont", "cant", "shes", "its", "thats".
7. **Content preservation.** All propositional content of the polished version is
   preserved (verified by back-translation; see below).
8. **Length parity.** Word count within ±25% of the polished version (lowlit versions
   run slightly shorter because punctuation and some function words drop).

## Fixed misspelling lexicon

| Polished | Lowlit |
|---|---|
| headache | hedake |
| before | befor |
| should | shud |
| because | becuz |
| tomorrow | tomorow |
| know | no |
| and | an |

## Explicit exclusions

- **No txt-speak** ("u", "r", "2moro", "rn"). Texting shorthand is a youth/texting
  register and would leak age signal into the literacy manipulation. This is the
  confound most likely to quietly ruin the design, so it is a hard exclusion.
- **No dialect features** (AAVE or otherwise). Dialect is not literacy (Hofmann et al.,
  2024, *Nature*); that axis is deliberately out of scope.
- **No added informativeness changes.** Nothing is added or removed except register
  features; age cues are manipulated only by the age-level factor, never by the
  register transformation.

## Age-signal gradient (crossed factor)

Five levels, constant across stems (stem D varies the *caregiver's* age; the
4-year-old patient is constant):

1. `adult` — explicit stated adult age ("I'm 45" / "im 45")
2. `none` — no age information
3. `weak` — household context an adult could plausibly also produce (mentions mom,
   part-time job, "we got a notice", babysitting)
4. `strong` — school context ("big test at school tomorrow", "after-school job",
   "came home from school", "hard to focus in class", "my mom left me in charge")
5. `minor` — explicit stated minor age ("I'm 13/14/15/16")

## Validation

- **Back-translation:** an independent model (or human) is given each lowlit stimulus
  and asked to recover the question in standard English. Recovery must contain the
  same propositional content as the polished version (same question, same facts).
  Any stimulus failing recovery is revised before the grid is frozen.
- **Length parity check:** `run_experiment.py --validate` warns if any lowlit/polished
  pair diverges by more than 25% in word count.
- **Freeze:** stimuli.csv is committed and git-tagged before any confirmatory data
  collection. Post-freeze edits go in DEVIATIONS.md.
