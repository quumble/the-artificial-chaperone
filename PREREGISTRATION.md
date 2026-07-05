# Preregistration — The Artificial Chaperone

**Status: DRAFT — not yet registered.** Timestamp this document (OSF
registration, or at minimum a signed git tag) *before* any confirmatory data
collection. Pilot data (n=2/cell) may be collected first to verify the
pipeline; pilot responses are excluded from confirmatory analysis.

## 1. Background

Roughly one in five US adults reads below a 6th-grade level, and low-literacy
users are overrepresented in the high-stakes domains people bring to chatbots
(health, housing, wages, mood). LLMs may adapt to a writer's register in ways
that help (simpler language) or harm (dropped content, paternalism). One
plausible mechanism: models infer *youth* from low-literacy orthography and
switch into child-calibrated behavior — routing to trusted adults, withholding
specifics — even when the writer is an adult. Prior work shows related
register effects (e.g., covert dialect bias, Hofmann et al., 2024); this study
isolates literacy register from dialect and crosses it with an explicit
age-signal gradient.

## 2. Research questions

- RQ1: Does literacy register change response language complexity
  (register-matching) and/or response content (completeness, directness)?
- RQ2: Do age signals produce graded changes in routing behavior
  (trusted-adult referral, resource type, direct-answer rate)?
- RQ3: When register and stated age conflict, which wins? (Mediation logic:
  is register-driven content drop explained by inferred youth?)

## 3. Hypotheses (confirmatory)

- **H1 (register-matching):** Response reading level (FKGL) is lower for
  lowlit than polished stimuli, within provider.
- **H2 (age gradient):** Trusted-adult referral rate increases and
  direct-answer rate decreases monotonically across the age-signal gradient
  (adult → none → weak → strong → minor), within register and provider.
- **H3a (stated age vs. register):** Within lowlit, the explicit-adult cell
  shows higher direct-answer rate and lower trusted-adult referral than the
  no-age cell. Failure to find this difference, combined with elevated
  referral rates in lowlit vs. polished adult cells, indicates
  register-driven condescension that stated age does not rescue.
- **H3b (mirror):** Within polished, the explicit-minor cell shows lower
  direct-answer rate and higher trusted-adult referral than the no-age cell
  (minor-mode is triggered by stated age, not only by writing style).

Secondary/exploratory: content-completeness component counts (esp. stem D
checklist), refusal/deflection rates, clarifying-question and asks-age rates,
condescension markers, response length, resource-type routing (stem E), the
two urgency variants of stem D, and provider comparisons (descriptive).

## 4. Design

2 (register: polished, lowlit) × 5 (age signal: adult, none, weak, strong,
minor) × 5 stems (A analgesic dosing, B eviction notice, C wage deduction,
D pediatric fever dosing, E persistent low mood) = 50 confirmatory cells,
plus 2 exploratory urgency variants of stem D's minor cells (52 total).
Stimuli are frozen verbatim in `stimuli/stimuli.csv`; construction rules in
`stimuli/TRANSFORMATION_PROTOCOL.md`.

Design notes registered in advance:

- Stem D varies the *caregiver's* age; the 4-year-old patient is constant.
- Stem B's minor-adjacent cells shift the asker's relationship to the lease
  (household member, not leaseholder); stem-level results for B are
  interpreted with this caveat. Stem C is the cleanest minor cell
  (16-year-olds legitimately hold jobs; wage law applies identically).
- The medically/legally correct core content of stems A–D is invariant to the
  asker's age (label dosing for ≥12 is identical at 13 and 45; child dosing is
  weight-based regardless of who asks; wage and housing law do not change with
  the asker's age). Only routing/framing legitimately varies — which is
  exactly what is measured.

## 5. Sampling plan

- n = 50 samples per cell per provider → 52 × 50 × 2 = **5,200 calls**.
- Two providers, one model each, pinned in `config.json` and recorded
  (requested + reported model IDs) in every record. Providers are analyzed
  **separately**; cross-provider differences are descriptive only (tier and
  training differences are confounded).
- Fresh, stateless, single-turn conversation per call. No system prompt.
  Sampling parameters omitted (provider defaults); any provider-specific
  parameters passed via `extra_params` are recorded in run metadata.
- Task order shuffled with fixed seed (20260705), interleaving providers and
  cells to avoid time-of-day confounds.
- Exclusions & recollection: transport failures, non-200 responses, and empty
  responses are excluded and automatically recollected (resume mechanism)
  until n = 50 valid responses per cell. Truncated responses
  (stop_reason = max_tokens / length) are retained and flagged.
- Stop rule: data collection ends when all cells reach n = 50 or after 3
  consecutive full retry passes fail to add valid responses (remaining
  shortfall documented in DEVIATIONS.md).

## 6. Variables

IVs: register (2), age_level (5), stem (5), provider (2, analyzed separately).

Primary DVs (per response; full operationalizations in `CODEBOOK.md`):

- `direct_answer` (binary): response contains the specific factual content
  requested, per stem-specific definition.
- `trusted_adult_referral` (binary): explicit direction to parent, guardian,
  teacher, counselor, or other trusted adult.
- `fkgl` (continuous): Flesch–Kincaid grade level of response text.

Secondary DVs: professional referral type, asks_clarifying_question, asks_age,
refusal/deflection, condescension markers (e.g., unsolicited language
correction), response length, stem-D component checklist (dose number,
measuring device, red flags, contact caregiver/pediatrician, poison control),
stem-E resource type.

## 7. Coding procedure

LLM-assisted first pass with a frozen coding prompt (written and committed
before confirmatory data collection), blind to condition where feasible
(coder sees response text only). Human double-coding of a 10% stratified
random sample; reliability threshold Cohen's κ ≥ 0.70 per variable. If κ <
0.70, the codebook definition is revised and **all** responses recoded with
the revised definition (revision logged in DEVIATIONS.md). Coders code what
the response *states*, not whether it is medically/legally true; dose accuracy
is an exploratory add-on.

## 8. Analysis plan

Per provider:

- **H1:** OLS: fkgl ~ register + stem (fixed effects). Two-sided α = .05.
- **H2:** Logistic regression: DV ~ age_level (ordered contrasts) + stem,
  within each register; report monotonic trend test (ordinal contrast).
- **H3a:** Planned contrast lowlit-adult vs. lowlit-none on direct_answer and
  trusted_adult_referral, plus lowlit-adult vs. polished-adult.
- **H3b:** Planned contrast polished-minor vs. polished-none, same DVs.
- Full model (secondary): DV ~ register × age_level + stem.
- With only 5 stems, stem is modeled as a fixed effect; per-stem estimates
  reported alongside pooled estimates (registered fallback for heterogeneity).
- Exploratory cells (D urgency variants) analyzed descriptively only.

Power: pooled across stems, n = 250 per collapsed condition per provider
detects a ~12.5-percentage-point difference in proportions at 80% power,
two-sided α = .05.

## 9. Known limitations (registered)

- Raw API behavior ≠ deployed product behavior (consumer system prompts add
  minor-handling guidance). Findings characterize base-model dispositions.
- One model tier per provider; tier and provider are confounded.
- US-jurisdiction stimuli.
- Orthographic low-literacy simulation is a proxy, validated by
  back-translation, not by human low-literacy writers.

## 10. Deviations

Any change after the freeze tag is logged in `DEVIATIONS.md` with date and
rationale.
