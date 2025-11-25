"""Process Slack export and prepare training data for fine-tuning."""

import json
import os
from glob import glob
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm.auto import tqdm

# Configuration
SLACK_EXPORT_PATH = os.path.expanduser("~/bababot/Tati's Amoebae Slack export Feb 24 2016 - Nov 23 2025")
TARGET_USER_ID = "U0NSX3SCT"  # John Flinchbaugh's user ID
OUTPUT_FILE = "all_messages.jsonl"
SYSTEM_PROMPT = """You are John Flinchbaugh talking to his friends on Discord.

You are a Dallas Mavericks and Texas Rangers fan, you like music and have a very silly non-sensical Discord persona.

Whenever you are asked a question, you always answer with confidence, and never say "I dunno" or "Haha".
"""


def main():
    print(f"Processing Slack export from: {SLACK_EXPORT_PATH}")

    # Load all message files
    print("Loading message files...")
    files = glob(f"{SLACK_EXPORT_PATH}/*/20*.json")
    print(f"Found {len(files)} message files")

    # Load users
    print("Loading users...")
    users_path = f"{SLACK_EXPORT_PATH}/users.json"
    users = pd.read_json(users_path).set_index("id").name
    print(f"Found {len(users)} users")

    # Load and process messages
    print("Loading messages...")
    df = pd.concat([
        pd.read_json(f).assign(channel=f.split("/")[-2])
        for f in tqdm(files, desc="Processing files")
    ])[['text', 'user', 'channel']].astype("string[pyarrow]")

    df['user_channel'] = df['channel'].str.cat(df['user'], sep=';')
    df['text'] += '\n'

    print(f"Loaded {len(df)} messages")

    # Replace user IDs with names
    print("Replacing user IDs with names...")
    for id, name in tqdm(users.items(), desc="Replacing IDs"):
        df["text"] = df.text.str.replace(f"<@{id}>", f"@{name}")

    # Group messages into conversations
    print("Grouping into conversations...")
    convos = df.groupby([
        (df['user_channel'] != df['user_channel'].shift(1)).astype("bool").cumsum(),
        "user",
        "channel"
    ]).text.sum().reset_index()

    print(f"Created {len(convos)} conversation blocks")

    # Filter for target user's messages
    print(f"Filtering for target user {TARGET_USER_ID}...")
    user_inds, = np.where(convos['user'].fillna("") == TARGET_USER_ID)
    print(f"Found {len(user_inds)} messages from target user")

    # Create training data
    print(f"Creating training data in {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w") as f:
        for i in tqdm(user_inds, desc="Writing training data"):
            # Get previous message as context if it's in the same channel
            user_content = ""
            if i > 0 and convos.channel.iloc[i - 1] == convos.channel.iloc[i]:
                user_content = convos.text.iloc[i - 1]

            json.dump({
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                    {"role": "assistant", "content": convos.text.iloc[i]}
                ]
            }, f)
            f.write("\n")

    print(f"\n✓ Training data saved to {OUTPUT_FILE}")
    print(f"✓ Total training examples: {len(user_inds)}")
    print("\nNext step: Run fine_tune.py to upload and start fine-tuning")


if __name__ == "__main__":
    main()
