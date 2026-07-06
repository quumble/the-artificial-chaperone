#!/usr/bin/env python3
"""LLM first-pass coding for The Artificial Chaperone.

Reads a deduped results JSONL, sends each response (blind: stem letter +
response text only) to a coder model with the frozen prompt in
CODING_PROMPT.md, and writes one JSON line per response to
results/coded/coded.jsonl. Resumable: re-running skips completed rows and
retries failures. Also computes fkgl (cleaned + raw) and length_chars.

Usage:
    python code_responses.py results/raw/results_deduped.jsonl
    python code_responses.py results/raw/results_deduped.jsonl --limit 20   # smoke test
    python code_responses.py ... --model claude-haiku-4-5 --concurrency 4

The coder model must NOT be one of the two studied models. Default is
CHANGE_ME so you make this choice explicitly.
"""

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

try:
    import textstat
except ImportError:
    textstat = None

ROOT = Path(__file__).resolve().parent

UNIVERSAL = ["direct_answer", "trusted_adult_referral", "professional_referral",
             "asks_clarifying_question", "asks_age", "refusal",
             "condescension_marker", "directive_framing"]
STEM_EXTRA = {
    "D": ["d_dose_number", "d_dose_matches_label", "d_measuring_device",
          "d_red_flags", "d_contact_caregiver_or_md", "d_poison_control"],
    "E": ["e_resource_type"],
}
BINARY = set(UNIVERSAL) - {"professional_referral"} | set(STEM_EXTRA["D"])


# ------------------------------------------------------------ prompt loading

def load_prompt_parts(path):
    text = Path(path).read_text(encoding="utf-8")
    blocks = re.findall(r"```\n(.*?)```", text, flags=re.S)
    if len(blocks) != 6:
        sys.exit(f"Expected 6 fenced blocks in {path} (1 prompt + 5 stems), "
                 f"found {len(blocks)}. Do not reformat the frozen prompt.")
    prompt = blocks[0]
    stems = dict(zip("ABCDE", blocks[1:]))
    return prompt, stems


def build_prompt(template, stems, stem, response_text):
    return (template
            .replace("{STEM_LETTER}", stem)
            .replace("{STEM_DEFINITION}", stems[stem].strip())
            .replace("{RESPONSE_TEXT}", response_text))


# ------------------------------------------------------------ fkgl (computed)

def _clean_for_fkgl(t):
    lines = []
    for line in t.split("\n"):
        s = re.sub(r"^#+\s*", "", line)
        s = s.replace("**", "").replace("*", "").replace("_", "").replace("`", "")
        s = re.sub(r"^\s*(?:[-•]|\d+[.)])\s*", "", s).strip()
        if not s:
            continue
        if s[-1] not in ".!?:":
            s += "."
        lines.append(s)
    return " ".join(lines)


def _fkgl_fallback(t):
    sents = [s for s in re.split(r"[.!?:]+", t) if s.strip()]
    words = re.findall(r"[A-Za-z']+", t)
    if not sents or not words:
        return None

    def syl(w):
        w = re.sub(r"[^a-z]", "", w.lower())
        n, prev = 0, False
        for ch in w:
            v = ch in "aeiouy"
            if v and not prev:
                n += 1
            prev = v
        if w.endswith("e") and n > 1 and not w.endswith(("le", "ue")):
            n -= 1
        return max(1, n)

    return round(0.39 * len(words) / len(sents)
                 + 11.8 * sum(syl(w) for w in words) / len(words) - 15.59, 3)


def fkgl_pair(text):
    cleaned = _clean_for_fkgl(text)
    if textstat:
        return (round(textstat.flesch_kincaid_grade(cleaned), 3),
                round(textstat.flesch_kincaid_grade(text), 3))
    return _fkgl_fallback(cleaned), _fkgl_fallback(text)


# ------------------------------------------------------------ API + parsing

def call_coder(model, prompt, api_key, timeout):
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": model, "max_tokens": 1500,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    return "".join(b.get("text", "") for b in data.get("content", [])
                   if b.get("type") == "text")


def parse_codes(raw, stem):
    m = re.search(r"\{.*\}", raw, flags=re.S)
    if not m:
        raise ValueError("no JSON object in coder output")
    obj = json.loads(m.group(0))
    expected = UNIVERSAL + STEM_EXTRA.get(stem, [])
    missing = [k for k in expected if k not in obj]
    if missing:
        raise ValueError(f"missing keys: {missing}")
    for k in expected:
        if k in BINARY and obj[k] not in (0, 1):
            raise ValueError(f"{k} not 0/1: {obj[k]!r}")
    return obj


# ------------------------------------------------------------ main

def load_env(path):
    if not path.exists():
        return
    import os
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("results", help="deduped results JSONL")
    ap.add_argument("--prompt", default="CODING_PROMPT.md")
    ap.add_argument("--model", default="CHANGE_ME",
                    help="coder model (must differ from the studied models)")
    ap.add_argument("--out", default="results/coded/coded.jsonl")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--limit", type=int, default=None,
                    help="code only the first N pending rows (smoke test)")
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()

    if args.model in ("", "CHANGE_ME"):
        sys.exit("Set --model explicitly (not one of the studied models).")
    if args.model in ("claude-sonnet-5", "gpt-5.5-2026-04-23"):
        sys.exit(f"Refusing to code with a studied model ({args.model}); "
                 "self-coding is a validity risk. Pick a different model.")

    import os
    load_env(ROOT / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set (see .env.example).")

    template, stems = load_prompt_parts(args.prompt)

    rows = [json.loads(l) for l in open(args.results, encoding="utf-8")]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    done = set()
    if out_path.exists():
        for line in open(out_path, encoding="utf-8"):
            try:
                r = json.loads(line)
                if r.get("coding_status") == "ok":
                    done.add((r["provider"], r["cell_id"], r["sample_idx"]))
            except ValueError:
                pass

    pending = [r for r in rows
               if (r["provider"], r["cell_id"], r["sample_idx"]) not in done]
    if args.limit:
        pending = pending[:args.limit]
    print(f"{len(rows)} responses | {len(done)} already coded | "
          f"{len(pending)} to code | coder model: {args.model}")
    if not pending:
        return

    lock = threading.Lock()
    counts = {"ok": 0, "fail": 0}

    def work(r):
        prompt = build_prompt(template, stems, r["stem"], r["response_text"])
        rec = {k: r[k] for k in ("provider", "cell_id", "stem", "register",
                                 "age_level", "exploratory", "sample_idx")}
        rec["coder_model"] = args.model
        clean, raw = fkgl_pair(r["response_text"])
        rec["fkgl"], rec["fkgl_raw"] = clean, raw
        rec["length_chars"] = len(r["response_text"])
        for attempt in range(3):
            try:
                out = call_coder(args.model, prompt, api_key, args.timeout)
                rec.update(parse_codes(out, r["stem"]))
                rec["coding_status"] = "ok"
                return rec
            except Exception as e:
                err = str(e)
                time.sleep(2 * (attempt + 1))
        rec["coding_status"] = "failed"
        rec["coding_error"] = err[:300]
        return rec

    with open(out_path, "a", encoding="utf-8") as out, \
         ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = [ex.submit(work, r) for r in pending]
        for i, fut in enumerate(as_completed(futures), 1):
            rec = fut.result()
            with lock:
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                counts["ok" if rec["coding_status"] == "ok" else "fail"] += 1
                if i % 50 == 0 or i == len(futures):
                    print(f"  {i}/{len(futures)} "
                          f"(ok {counts['ok']}, failed {counts['fail']})")

    if not textstat:
        print("NOTE: textstat not installed -- fkgl used the built-in "
              "approximation. Install textstat and re-run for the "
              "registered measure (pip install textstat).")
    if counts["fail"]:
        print(f"{counts['fail']} rows failed; re-run the same command to retry.")


if __name__ == "__main__":
    main()
