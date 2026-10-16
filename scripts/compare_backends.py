"""Blind side-by-side comparison of the fine-tuned and prompt-based backends.

Runs each held-out Discord prompt (from scripts/build_persona_prompt.py) through both
backends and writes data/comparison.md with the replies shuffled as A/B and the answer
key at the bottom.

Usage: python scripts/compare_backends.py [--limit 40]
"""

import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main  # noqa: E402

HOLDOUT_FILE = ROOT / "data" / "holdout_prompts.jsonl"
OUTPUT_FILE = ROOT / "data" / "comparison.md"


def reply(backend, prompt):
    main.BOT_BACKEND = backend
    messages = [{"role": "system", "content": main.SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
    start = time.time()
    try:
        text = main.query_gpt_model(messages)
    except Exception as e:
        text = f"[error: {e}]"
    return text.strip(), time.time() - start


def main_():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--backends", nargs=2, default=["finetune", "prompt"])
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    parser.add_argument("--prompts", type=Path, default=HOLDOUT_FILE)
    args = parser.parse_args()

    main.PROMPT_SYSTEM_MESSAGE = main.build_prompt_system_message()
    main.TANGENT_POOL = main.load_tangent_pool()
    random.seed(1)
    rows = [json.loads(line) for line in open(args.prompts)][: args.limit]

    # One backend at a time, since query_gpt_model reads the module-level BOT_BACKEND
    results = {}
    for backend in args.backends:
        with ThreadPoolExecutor(8) as pool:
            results[backend] = list(pool.map(lambda r: reply(backend, r["prompt"]), rows))

    rng = random.Random(0)
    lines, key = ["# Bababot blind comparison", ""], []
    for i, row in enumerate(rows):
        pair = [(b, results[b][i][0]) for b in args.backends]
        rng.shuffle(pair)
        key.append(f"{i + 1}: A={pair[0][0]}, B={pair[1][0]}")
        quoted = "\n".join(f"> {line}" for line in row["prompt"].splitlines())
        lines += [f"## {i + 1}", quoted, "", f"**A:** {pair[0][1]}", "", f"**B:** {pair[1][1]}", "",
                  f"<details><summary>Actual reply</summary>\n\n{row['actual']}\n</details>", ""]

    lines += ["---", "## Answer key", "", *key]
    args.output.write_text("\n".join(lines))

    for backend in results:
        latencies = sorted(t for _, t in results[backend])
        print(f"{backend}: median latency {latencies[len(latencies) // 2]:.1f}s")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main_()
