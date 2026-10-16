"""Build the few-shot example block used by the prompt-based (non-fine-tuned) backend.

Pulls (context, reply) pairs from the old fine-tuning file (Slack history) and from the
Discord channel history, and writes them to data/persona_examples.txt. The output is
deterministic so the prompt prefix stays identical between requests and gets cached.

Usage: python scripts/build_persona_prompt.py [--slack-examples 1500] [--holdout 40]
"""

import argparse
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLACK_FILE = ROOT / "data" / "all_messages.jsonl"
DISCORD_FILE = ROOT / "channel_1418289476781998153_history.json"
OUTPUT_FILE = ROOT / "data" / "persona_examples.txt"
HOLDOUT_FILE = ROOT / "data" / "holdout_prompts.jsonl"

TARGET_DISCORD_AUTHOR = "jflinchb4"
IGNORED_DISCORD_AUTHORS = {"Wordle#2092", "Bababot#2535", "Chess In The Park#9517"}
MAX_CHARS = 400


def clean(text):
    # Slack link formatting: <https://a|https://a> -> https://a
    text = re.sub(r"<(https?://[^|>]+)\|[^>]*>", r"\1", text)
    text = re.sub(r"<(https?://[^>]+)>", r"\1", text)
    text = text.strip()
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS].rsplit(" ", 1)[0] + " …"
    return text


def is_useful(context, reply):
    if not context or not reply:
        return False
    # Skip replies that are only a link or a giphy command
    if re.fullmatch(r"(https?://\S+\s*)+", reply) or reply.startswith("/giphy"):
        return False
    return True


def slack_pairs(n, seed):
    pairs = []
    with open(SLACK_FILE) as f:
        for line in f:
            msgs = json.loads(line)["messages"]
            context, reply = clean(msgs[1]["content"]), clean(msgs[2]["content"])
            if is_useful(context, reply):
                pairs.append((context, reply))
    random.Random(seed).shuffle(pairs)
    return pairs[:n]


def discord_pairs():
    """Group consecutive messages by author, then pair each John block with the block before it."""
    history = json.load(open(DISCORD_FILE))
    blocks = []
    for msg in history:
        if msg["author"] in IGNORED_DISCORD_AUTHORS or not msg["content"].strip():
            continue
        if blocks and blocks[-1][0] == msg["author"]:
            blocks[-1][1].append(msg["content"])
        else:
            blocks.append((msg["author"], [msg["content"]]))

    pairs = []
    for prev, cur in zip(blocks, blocks[1:]):
        if cur[0] == TARGET_DISCORD_AUTHOR and prev[0] != TARGET_DISCORD_AUTHOR:
            context, reply = clean("\n".join(prev[1])), clean("\n".join(cur[1]))
            if is_useful(context, reply):
                pairs.append((context, reply))
    return pairs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slack-examples", type=int, default=1500)
    parser.add_argument("--holdout", type=int, default=40, help="Most recent Discord pairs held out for evaluation")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    discord = discord_pairs()
    holdout, discord = discord[-args.holdout:], discord[:-args.holdout]
    examples = slack_pairs(args.slack_examples, args.seed) + discord

    with open(OUTPUT_FILE, "w") as f:
        for context, reply in examples:
            f.write(f"<example>\nfriend: {context}\njohn: {reply}\n</example>\n")
    with open(HOLDOUT_FILE, "w") as f:
        for context, reply in holdout:
            f.write(json.dumps({"prompt": context, "actual": reply}) + "\n")

    chars = OUTPUT_FILE.stat().st_size
    print(f"Wrote {len(examples)} examples ({len(discord)} Discord) to {OUTPUT_FILE} (~{chars // 4:,} tokens)")
    print(f"Wrote {len(holdout)} held-out prompts to {HOLDOUT_FILE}")


if __name__ == "__main__":
    main()
