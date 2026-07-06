#!/usr/bin/env python3
"""Reliability workflow: stratified double-coding sample + Cohen's kappa.

Step 1 — draw the human double-coding sample (stratified by provider x
register x age_level, per the codebook), joined with response text:

    python reliability.py sample results/coded/coded.jsonl \
        results/raw/results_deduped.jsonl --frac 0.10 --seed 20260705

    -> writes human_coding_sample.csv with the LLM codes HIDDEN and blank
       human_* columns to fill in. Response order is shuffled; provider /
       register / age columns are omitted from the CSV to keep the human
       coder blind (a separate key file maps row ids back).

Step 2 — after filling in human_* columns, compute per-variable kappa:

    python reliability.py kappa results/coded/coded.jsonl human_coding_sample.csv

Threshold per the prereg: kappa >= 0.70 per variable; otherwise revise the
codebook definition, log in DEVIATIONS.md, and recode ALL responses.
"""

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

BINARY_VARS = ["direct_answer", "trusted_adult_referral",
               "asks_clarifying_question", "asks_age", "refusal",
               "condescension_marker", "directive_framing",
               "d_dose_number", "d_dose_matches_label", "d_measuring_device",
               "d_red_flags", "d_contact_caregiver_or_md", "d_poison_control"]


def key(r):
    return f"{r['provider']}|{r['cell_id']}|{r['sample_idx']}"


def cmd_sample(args):
    coded = [json.loads(l) for l in open(args.coded, encoding="utf-8")
             if json.loads(l).get("coding_status") == "ok"]
    texts = {key(r): r["response_text"]
             for r in (json.loads(l) for l in open(args.results, encoding="utf-8"))}

    strata = defaultdict(list)
    for r in coded:
        if r.get("exploratory") == 0:
            strata[(r["provider"], r["register"], r["age_level"])].append(r)

    rng = random.Random(args.seed)
    sample = []
    for s, rows in sorted(strata.items()):
        k = max(1, round(len(rows) * args.frac))
        sample.extend(rng.sample(rows, k))
    rng.shuffle(sample)

    with open("human_coding_sample.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["row_id", "stem", "response_text"] +
                   [f"human_{v}" for v in BINARY_VARS] +
                   ["human_professional_referral", "human_e_resource_type",
                    "notes"])
        for r in sample:
            w.writerow([key(r), r["stem"], texts.get(key(r), "")] +
                       [""] * (len(BINARY_VARS) + 3))
    with open("human_coding_sample_key.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["row_id", "provider", "register", "age_level", "cell_id"])
        for r in sample:
            w.writerow([key(r), r["provider"], r["register"],
                        r["age_level"], r["cell_id"]])
    print(f"wrote human_coding_sample.csv ({len(sample)} rows, shuffled, "
          f"condition-blind) and human_coding_sample_key.csv (keep this "
          f"away from the human coder until coding is done)")


def cohen_kappa(pairs):
    n = len(pairs)
    if n == 0:
        return None
    po = sum(a == b for a, b in pairs) / n
    cats = sorted({v for p in pairs for v in p})
    pe = sum((sum(a == c for a, _ in pairs) / n) *
             (sum(b == c for _, b in pairs) / n) for c in cats)
    if pe == 1:
        return 1.0
    return (po - pe) / (1 - pe)


def cmd_kappa(args):
    coded = {}
    for line in open(args.coded, encoding="utf-8"):
        r = json.loads(line)
        if r.get("coding_status") == "ok":
            coded[key(r)] = r

    results = []
    with open(args.human, newline="", encoding="utf-8") as f:
        human_rows = [row for row in csv.DictReader(f)]

    for var in BINARY_VARS:
        pairs = []
        for row in human_rows:
            h = row.get(f"human_{var}", "").strip()
            llm = coded.get(row["row_id"], {})
            if h in ("0", "1") and var in llm:
                pairs.append((int(llm[var]), int(h)))
        if not pairs:
            continue
        k = cohen_kappa(pairs)
        agree = sum(a == b for a, b in pairs) / len(pairs)
        flag = "" if (k is not None and k >= 0.70) else "  <-- BELOW 0.70"
        ks = f"{k:.3f}" if k is not None else "  n/a"
        results.append((var, len(pairs), agree, ks, flag))

    print(f"{'variable':<28}{'n':>5}{'agree':>8}{'kappa':>8}")
    for var, n, agree, ks, flag in results:
        print(f"{var:<28}{n:>5}{agree:>8.2f}{ks:>8}{flag}")
    print("\nNote: kappa is undefined/unstable for very rare codes (near-zero "
          "base rates). For those, report raw agreement and consider "
          "Gwet's AC1 as a supplement (log any such decision in "
          "DEVIATIONS.md).")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("coded")
    s.add_argument("results")
    s.add_argument("--frac", type=float, default=0.10)
    s.add_argument("--seed", type=int, default=20260705)
    k = sub.add_parser("kappa")
    k.add_argument("coded")
    k.add_argument("human")
    args = ap.parse_args()
    if args.cmd == "sample":
        cmd_sample(args)
    else:
        cmd_kappa(args)


if __name__ == "__main__":
    main()
