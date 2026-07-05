# The Artificial Chaperone

Do LLMs infer a user's age from their writing, and does that inference change
what they're told? This study crosses **literacy register** (polished vs.
low-literacy) with a **five-level age-signal gradient** (explicit adult → no
info → weak minor cue → strong minor cue → explicit minor) across five benign,
high-stakes question stems (analgesic dosing, eviction, wage deduction,
pediatric fever dosing, persistent low mood), querying the Anthropic and
OpenAI APIs.

The headline test lives in the off-diagonal cells: if a stated adult age fails
to rescue full content in the low-literacy register, low-literacy **adults**
are being served child-calibrated responses. See `PREREGISTRATION.md`.

## Repository structure

```
├── README.md                     ← you are here
├── PREREGISTRATION.md            ← hypotheses, design, analysis plan (freeze before collecting!)
├── CODEBOOK.md                   ← DV definitions and coding procedure
├── DEVIATIONS.md                 ← log of post-freeze changes
├── LICENSE / CITATION.cff
├── config.json                   ← models, sample sizes, concurrency
├── .env.example                  ← template for API keys
├── requirements.txt
├── run.ps1                       ← PowerShell entry point
├── run_experiment.py             ← the actual runner
├── summarize_results.py          ← descriptive sanity checks (NOT the coding pipeline)
└── stimuli/
    ├── stimuli.csv               ← the 52-cell grid, verbatim
    └── TRANSFORMATION_PROTOCOL.md← how lowlit variants were constructed
```

## Setup (Windows / PowerShell)

1. Install Python 3.9+ from python.org (check **Add python.exe to PATH**).
2. Copy `.env.example` to `.env` and add your `ANTHROPIC_API_KEY` and
   `OPENAI_API_KEY`.
3. **Verify the model strings in `config.json`.** Model names change; pin a
   dated snapshot if the provider offers one, and record what you ran (the
   runner writes both requested and reported model IDs into every record).
4. If script execution is blocked, run via:
   `powershell -ExecutionPolicy Bypass -File .\run.ps1 -Validate`

`run.ps1` creates a `.venv` and installs dependencies automatically on first run.

## Pipeline (run in this order)

```powershell
.\run.ps1 -Validate    # 1. integrity checks on stimuli + config (no API calls)
.\run.ps1 -DryRun      # 2. preview planned calls (no API calls)
.\run.ps1 -Pilot       # 3. 208 calls (2/cell) -- READ the raw output before proceeding
# 4. freeze: git add -A; git commit -m "freeze stimuli+prereg"; git tag v1.0-frozen
.\run.ps1              # 5. full run: 5,200 calls (50/cell x 52 cells x 2 providers)
.venv\Scripts\python.exe summarize_results.py results\raw\results.jsonl   # 6. sanity check
```

The runner is resumable: interrupt it (or run out of quota) and re-running the
same command skips completed calls and retries failures. Progress, ETA, and
error counts display live.

**Expected duration:** roughly 45–90 minutes for the full run at the default
concurrency (4 workers per provider). **Expected cost:** on the order of tens
of dollars total; verify current per-token pricing for the models you pin
before running.

## Design summary

- 5 stems × 2 registers × 5 age levels = 50 confirmatory cells, plus 2
  exploratory urgency variants of the fever stem (52 total).
- n = 50 samples/cell/provider = 5,200 calls. Pilot mode: n = 2 (208 calls).
- Fresh stateless conversation per call; task order shuffled with a fixed seed
  so providers and cells interleave (avoids time-of-day confounds).
- **No system prompt**, and sampling parameters are omitted (provider
  defaults). Some current models reject non-default `temperature`; if you need
  to pass provider-specific parameters (e.g., `reasoning_effort`), use
  `extra_params` in `config.json` and log it in `DEVIATIONS.md`.

## Important caveats

- **API ≠ product.** Raw API calls don't include the consumer apps' system
  prompts, which contain guidance about suspected minors. Findings characterize
  base-model dispositions, not what a real 13-year-old sees in a deployed app.
- **`summarize_results.py` is not measurement.** Its keyword screens are crude
  sanity checks. Confirmatory coding follows `CODEBOOK.md`.
- Stimuli are US-flavored (Tylenol, DOL, pay-or-quit notices); legal stems
  assume US jurisdiction variability.

## Ethics

No human subjects; all personas are synthetic. Every stimulus is a benign
question with a legitimate, age-appropriate answer at every age level — the
study measures response *calibration*, not guardrail circumvention. Use of the
APIs is subject to each provider's usage policies.

## License

MIT — see `LICENSE`.
