#!/usr/bin/env python3
"""The Artificial Chaperone -- experiment runner.

Queries the Anthropic and OpenAI chat APIs over the 52-cell stimulus grid
(register x age-signal x stem) and writes one JSON line per call to
results/raw/. Safe to interrupt and re-run: completed calls are skipped.

Normally invoked via run.ps1. Direct usage:

    python run_experiment.py --validate      # check stimuli + config, no calls
    python run_experiment.py --dry-run       # show planned calls, no calls
    python run_experiment.py --pilot         # 2 samples/cell (208 calls)
    python run_experiment.py                 # full run (5,200 calls)
    python run_experiment.py --provider anthropic
"""

import argparse
import csv
import json
import os
import platform
import random
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    from tqdm import tqdm
except ImportError:  # progress still reported, just less prettily
    tqdm = None

ROOT = Path(__file__).resolve().parent

REQUIRED_COLUMNS = ["cell_id", "stem", "register", "age_level", "exploratory", "prompt_text"]
REGISTERS = {"polished", "lowlit"}
AGE_LEVELS = {"adult", "none", "weak", "strong", "minor"}
FATAL_STATUS = {400, 401, 403, 404}
MAX_ATTEMPTS = 5
PLACEHOLDER_MODELS = {"", "CHANGE_ME"}


# ---------------------------------------------------------------- utilities

def utc_now():
    return datetime.now(timezone.utc).isoformat()


def load_env(path):
    """Minimal .env loader; does not override variables already set."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def git_commit():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, timeout=10,
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


# ---------------------------------------------------------------- stimuli

def load_stimuli(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def validate_stimuli(rows):
    """Return (errors, warnings)."""
    errors, warnings = [], []
    if not rows:
        return ["stimuli file is empty"], warnings
    missing = [c for c in REQUIRED_COLUMNS if c not in rows[0]]
    if missing:
        return [f"missing columns: {missing}"], warnings

    ids = [r["cell_id"] for r in rows]
    if len(ids) != len(set(ids)):
        errors.append("duplicate cell_ids present")
    if len(rows) != 52:
        errors.append(f"expected 52 rows, found {len(rows)}")

    confirmatory = [r for r in rows if r["exploratory"] == "0"]
    if len(confirmatory) != 50:
        errors.append(f"expected 50 confirmatory rows, found {len(confirmatory)}")

    for r in rows:
        if r["register"] not in REGISTERS:
            errors.append(f"{r['cell_id']}: bad register {r['register']!r}")
        if r["age_level"] not in AGE_LEVELS:
            errors.append(f"{r['cell_id']}: bad age_level {r['age_level']!r}")
        if r["exploratory"] not in {"0", "1"}:
            errors.append(f"{r['cell_id']}: bad exploratory flag {r['exploratory']!r}")
        if not r["prompt_text"].strip():
            errors.append(f"{r['cell_id']}: empty prompt_text")

    # full crossing check on confirmatory rows
    combos = {(r["stem"], r["register"], r["age_level"]) for r in confirmatory}
    stems = sorted({r["stem"] for r in confirmatory})
    for s in stems:
        for reg in sorted(REGISTERS):
            for age in sorted(AGE_LEVELS):
                if (s, reg, age) not in combos:
                    errors.append(f"missing confirmatory cell: {s}/{reg}/{age}")

    # length parity warning (polished vs lowlit within stem x age)
    by_key = {(r["stem"], r["age_level"], r["exploratory"], r["register"]):
              len(r["prompt_text"].split()) for r in rows}
    for (s, age, exp, reg), n in by_key.items():
        if reg != "polished":
            continue
        low = by_key.get((s, age, exp, "lowlit"))
        if low and n and abs(low - n) / n > 0.25:
            warnings.append(
                f"length parity >25%: stem {s} age {age} (pol={n}w, low={low}w)")
    return errors, warnings


# ---------------------------------------------------------------- API calls

def call_anthropic(model, prompt, cfg, api_key):
    body = {
        "model": model,
        "max_tokens": cfg["max_output_tokens"],
        "messages": [{"role": "user", "content": prompt}],
    }
    body.update(cfg["providers"]["anthropic"].get("extra_params") or {})
    return requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=body,
        timeout=cfg["request_timeout_seconds"],
    )


def parse_anthropic(data):
    text = "".join(
        b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    usage = data.get("usage", {})
    return {
        "response_text": text,
        "model_reported": data.get("model"),
        "stop_reason": data.get("stop_reason"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
    }


def call_openai(model, prompt, cfg, api_key):
    body = {
        "model": model,
        "max_completion_tokens": cfg["max_output_tokens"],
        "messages": [{"role": "user", "content": prompt}],
    }
    body.update(cfg["providers"]["openai"].get("extra_params") or {})
    return requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=cfg["request_timeout_seconds"],
    )


def parse_openai(data):
    choice = (data.get("choices") or [{}])[0]
    usage = data.get("usage", {})
    return {
        "response_text": (choice.get("message") or {}).get("content") or "",
        "model_reported": data.get("model"),
        "stop_reason": choice.get("finish_reason"),
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
    }


PROVIDERS = {
    "anthropic": {"call": call_anthropic, "parse": parse_anthropic,
                  "key_env": "ANTHROPIC_API_KEY"},
    "openai": {"call": call_openai, "parse": parse_openai,
               "key_env": "OPENAI_API_KEY"},
}


class Pacer:
    """Enforces a minimum interval between request starts for one provider."""

    def __init__(self, min_interval):
        self.min_interval = min_interval
        self.lock = threading.Lock()
        self.last = 0.0

    def wait(self):
        with self.lock:
            delta = self.min_interval - (time.monotonic() - self.last)
            if delta > 0:
                time.sleep(delta)
            self.last = time.monotonic()


class ResultWriter:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(path, "a", encoding="utf-8")
        self.lock = threading.Lock()

    def write(self, record):
        with self.lock:
            self.fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            self.fh.flush()

    def close(self):
        self.fh.close()


def execute_task(task, cfg, pacer, writer, run_id):
    """Run one API call with retries. Returns final status string."""
    provider = task["provider"]
    spec = PROVIDERS[provider]
    api_key = os.environ[spec["key_env"]]
    model = cfg["providers"][provider]["model"]
    error_msg, status = None, "failed"
    attempt = 0

    for attempt in range(1, MAX_ATTEMPTS + 1):
        pacer.wait()
        t0 = time.monotonic()
        try:
            resp = spec["call"](model, task["prompt_text"], cfg, api_key)
        except requests.RequestException as exc:
            error_msg = f"transport: {exc}"
            time.sleep(min(2 ** attempt, 30))
            continue
        latency_ms = int((time.monotonic() - t0) * 1000)

        if resp.status_code == 200:
            try:
                parsed = spec["parse"](resp.json())
            except (ValueError, KeyError) as exc:
                error_msg = f"parse: {exc}"
                time.sleep(min(2 ** attempt, 30))
                continue
            if not parsed["response_text"].strip():
                error_msg = "empty response text"
                time.sleep(min(2 ** attempt, 30))
                continue
            record = make_record(task, run_id, model, attempt, "ok", None,
                                 latency_ms, parsed)
            writer.write(record)
            return "ok"

        error_msg = f"HTTP {resp.status_code}: {resp.text[:300]}"
        if resp.status_code in FATAL_STATUS:
            status = "fatal"
            break
        retry_after = resp.headers.get("retry-after")
        try:
            delay = float(retry_after) if retry_after else min(2 ** attempt, 60)
        except ValueError:
            delay = min(2 ** attempt, 60)
        time.sleep(delay)

    record = make_record(task, run_id, model, attempt, status, error_msg, None, None)
    writer.write(record)
    return status


def make_record(task, run_id, model, attempts, status, error, latency_ms, parsed):
    record = {
        "run_id": run_id,
        "timestamp_utc": utc_now(),
        "provider": task["provider"],
        "model_requested": model,
        "cell_id": task["cell_id"],
        "stem": task["stem"],
        "register": task["register"],
        "age_level": task["age_level"],
        "exploratory": int(task["exploratory"]),
        "sample_idx": task["sample_idx"],
        "prompt_text": task["prompt_text"],
        "attempts": attempts,
        "status": status,
        "error": error,
        "latency_ms": latency_ms,
        "response_text": None,
        "model_reported": None,
        "stop_reason": None,
        "input_tokens": None,
        "output_tokens": None,
    }
    if parsed:
        record.update(parsed)
    return record


# ---------------------------------------------------------------- main

def build_tasks(rows, cfg, n_samples, providers):
    tasks = []
    for provider in providers:
        for row in rows:
            for i in range(n_samples):
                tasks.append({
                    "provider": provider,
                    "cell_id": row["cell_id"],
                    "stem": row["stem"],
                    "register": row["register"],
                    "age_level": row["age_level"],
                    "exploratory": row["exploratory"],
                    "prompt_text": row["prompt_text"],
                    "sample_idx": i,
                })
    return tasks


def load_completed(path):
    done = set()
    if not path.exists():
        return done
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("status") == "ok":
                done.add((r["provider"], r["cell_id"], r["sample_idx"]))
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--pilot", action="store_true",
                    help="2 samples/cell, separate output file")
    ap.add_argument("--dry-run", action="store_true",
                    help="show planned calls without making any")
    ap.add_argument("--validate", action="store_true",
                    help="validate stimuli and config, then exit")
    ap.add_argument("--provider", choices=list(PROVIDERS),
                    help="restrict to a single provider")
    args = ap.parse_args()

    load_env(ROOT / ".env")
    cfg = json.loads((ROOT / args.config).read_text(encoding="utf-8"))
    rows = load_stimuli(ROOT / cfg["stimuli_path"])

    errors, warnings = validate_stimuli(rows)
    providers = [p for p, pc in cfg["providers"].items() if pc.get("enabled")]
    if args.provider:
        providers = [p for p in providers if p == args.provider]
    for p in providers:
        if cfg["providers"][p].get("model") in PLACEHOLDER_MODELS:
            errors.append(f"provider {p}: model not set in {args.config}")
    for w in warnings:
        print(f"WARNING: {w}")
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        sys.exit(1)
    print(f"Stimuli OK: {len(rows)} cells "
          f"({sum(r['exploratory'] == '0' for r in rows)} confirmatory, "
          f"{sum(r['exploratory'] == '1' for r in rows)} exploratory)")
    if args.validate:
        print("Config OK. Validation passed.")
        return

    n_samples = cfg["pilot_n_samples_per_cell"] if args.pilot else cfg["n_samples_per_cell"]
    results_dir = ROOT / cfg["results_dir"]
    results_path = results_dir / ("pilot_results.jsonl" if args.pilot else "results.jsonl")
    run_id = cfg["run_id"] + ("-pilot" if args.pilot else "")

    tasks = build_tasks(rows, cfg, n_samples, providers)
    rng = random.Random(cfg["seed"])
    rng.shuffle(tasks)  # interleave providers/cells to avoid time-of-day confounds

    done = load_completed(results_path)
    pending = [t for t in tasks
               if (t["provider"], t["cell_id"], t["sample_idx"]) not in done]

    print(f"Providers: {', '.join(providers)}")
    print(f"Planned calls: {len(tasks)}  |  already completed: {len(done)}  "
          f"|  pending: {len(pending)}")
    print(f"Output: {results_path}")

    if args.dry_run:
        for t in pending[:5]:
            print(f"  [{t['provider']}] {t['cell_id']} #{t['sample_idx']}: "
                  f"{t['prompt_text'][:70]}...")
        print("Dry run complete. No API calls made.")
        return
    if not pending:
        print("Nothing to do.")
        return

    for p in providers:
        if not os.environ.get(PROVIDERS[p]["key_env"]):
            sys.exit(f"ERROR: {PROVIDERS[p]['key_env']} not set. "
                     "Copy .env.example to .env and add your keys.")

    meta_dir = results_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "run_id": run_id, "started_utc": utc_now(), "args": vars(args),
        "config": cfg, "n_pending": len(pending), "git_commit": git_commit(),
        "python": platform.python_version(),
    }
    (meta_dir / f"meta_{run_id}_{int(time.time())}.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8")

    writer = ResultWriter(results_path)
    pacers = {p: Pacer(cfg["providers"][p]["min_interval_seconds"]) for p in providers}
    pools = {p: ThreadPoolExecutor(
        max_workers=cfg["providers"][p]["max_concurrency"],
        thread_name_prefix=p) for p in providers}

    futures = []
    for t in pending:
        futures.append(pools[t["provider"]].submit(
            execute_task, t, cfg, pacers[t["provider"]], writer, run_id))

    counts = {"ok": 0, "failed": 0, "fatal": 0}
    iterator = as_completed(futures)
    bar = tqdm(iterator, total=len(futures), unit="call") if tqdm else iterator
    t_start = time.monotonic()
    for i, fut in enumerate(bar, 1):
        counts[fut.result()] += 1
        if tqdm:
            bar.set_postfix(ok=counts["ok"], err=counts["failed"] + counts["fatal"])
        elif i % 25 == 0 or i == len(futures):
            rate = i / (time.monotonic() - t_start)
            eta_min = (len(futures) - i) / rate / 60 if rate else 0
            print(f"  {i}/{len(futures)} done "
                  f"(ok={counts['ok']}, err={counts['failed'] + counts['fatal']}, "
                  f"ETA {eta_min:.0f} min)")

    for pool in pools.values():
        pool.shutdown()
    writer.close()

    print(f"\nFinished: {counts['ok']} ok, {counts['failed']} failed, "
          f"{counts['fatal']} fatal.")
    if counts["failed"]:
        print("Re-run the same command to retry failures (completed calls are skipped).")
    if counts["fatal"]:
        print("Fatal errors (bad key/model?) — check the 'error' field in the JSONL.")


if __name__ == "__main__":
    main()
