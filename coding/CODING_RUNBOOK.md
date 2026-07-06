# Coding-phase runbook

Files to add to the repo root: `dedupe_results.py`, `CODING_PROMPT.md`,
`code_responses.py`, `reliability.py`.

## Order of operations

```powershell
# 0. housekeeping: dedupe the raw file (13 duplicate openai records)
.venv\Scripts\python.exe dedupe_results.py results\raw\results.jsonl

# 1. pick the coder model — NOT claude-sonnet-5 or gpt-5.5 (self-coding is a
#    validity risk). A small/cheap different-tier model is fine; the runner
#    refuses the two studied model strings.

# 2. FREEZE before coding anything:
git add dedupe_results.py CODING_PROMPT.md code_responses.py reliability.py
git commit -m "freeze coding prompt + pipeline"
git tag v1.0-coding-frozen
# record the commit hash in DEVIATIONS.md

# 3. smoke test (20 responses), read the output by hand:
.venv\Scripts\python.exe code_responses.py results\raw\results_deduped.jsonl --model <coder> --limit 20

# 4. full first pass (5,200 responses; resumable):
.venv\Scripts\python.exe code_responses.py results\raw\results_deduped.jsonl --model <coder>

# 5. draw the stratified 10% human sample (blind: no condition columns;
#    the key file stays with the analyst, not the coder):
.venv\Scripts\python.exe reliability.py sample results\coded\coded.jsonl results\raw\results_deduped.jsonl

# 6. human fills human_* columns in human_coding_sample.csv, then:
.venv\Scripts\python.exe reliability.py kappa results\coded\coded.jsonl human_coding_sample.csv
# kappa >= 0.70 per variable = pass; otherwise revise the definition,
# log it, and recode ALL responses (per prereg section 7).
```

## Decisions to log in DEVIATIONS.md now

1. **Prereg timing.** `git_commit` is null in all run metadata and the prereg
   header still reads DRAFT: the freeze tag did not happen before collection.
   Either (a) reframe the run as a large pilot and rerun after a real freeze,
   or (b) timestamp the prereg now and disclose the ordering prominently.
   Do not badge the current data as preregistered-confirmatory as-is.
2. **Duplicate records.** 13 duplicate openai (provider, cell, sample_idx)
   rows from the resume mechanism; analysis uses the deduped file (keep-first
   rule).
3. **Two-chunk anthropic collection.** A credit-balance outage split the
   anthropic run into two temporal chunks (~70 min apart), so the seeded
   interleaving was partially broken for that provider. Likely immaterial;
   disclose it.
4. **Coder blinding scope.** The LLM coder sees the stem letter (required to
   apply stem-specific definitions) plus response text — never provider,
   register, age_level, or the prompt. Same for the human sample CSV.
5. **Coder model choice** (which model, and that it differs from both studied
   models).

## Analysis notes carried over from the sanity pass

- Expect H1 and H2 to confirm easily; H3a is trending null (that is the
  headline — register alone does not trigger minor-mode routing or core
  content drop).
- The register story likely lives in the stem-D checklist components
  (poison-control mentions drop sharply in lowlit) and response length,
  not in `direct_answer`.
- Watch stem A anthropic polished-minor: the one pocket of real gatekeeping
  (~38% refusal-ish by keyword screen), and it is *stronger* in polished
  than lowlit — opposite of H3's direction. Small-n; flag for follow-up
  rather than overclaiming.
- Keyword screens have known false positives (e.g. "your age may matter"
  headers matched asks_age); do not reuse them beyond sanity checks.
