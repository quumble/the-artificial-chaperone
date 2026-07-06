#!/usr/bin/env python3
"""Deduplicate a results JSONL on (provider, cell_id, sample_idx).

The resume mechanism can occasionally double-write a record (observed: 13
duplicate openai records in the v1 run). Keeps the FIRST successful record
per key; drops non-ok records entirely (they were recollected anyway).

Usage:
    python dedupe_results.py results/raw/results.jsonl
    # writes results/raw/results_deduped.jsonl and prints a report
"""

import json
import sys
from collections import Counter
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = Path(sys.argv[1])
    out_path = path.with_name(path.stem + "_deduped.jsonl")

    seen = set()
    kept, dup_ok, non_ok, bad_lines = 0, 0, 0, 0
    cells = Counter()

    with open(path, encoding="utf-8") as f, \
         open(out_path, "w", encoding="utf-8") as out:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                bad_lines += 1
                continue
            if r.get("status") != "ok" or not r.get("response_text"):
                non_ok += 1
                continue
            key = (r["provider"], r["cell_id"], r["sample_idx"])
            if key in seen:
                dup_ok += 1
                continue
            seen.add(key)
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
            kept += 1
            cells[(r["provider"], r["cell_id"])] += 1

    print(f"kept {kept} | duplicate ok-records dropped {dup_ok} | "
          f"non-ok dropped {non_ok} | unparseable lines {bad_lines}")
    short = {k: v for k, v in cells.items() if v != 50}
    if short:
        print("cells with n != 50:")
        for k, v in sorted(short.items()):
            print(f"  {k}: {v}")
    else:
        providers = sorted({p for p, _ in cells})
        print(f"all cells at n = 50 for providers: {', '.join(providers)}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
