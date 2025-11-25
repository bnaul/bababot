"""Register the /baba slash command with Discord."""

import os
import requests

APPLICATION_ID = os.getenv("DISCORD_APPLICATION_ID")
BOT_TOKEN = os.getenv("DISCORD_TOKEN")

if not APPLICATION_ID or not BOT_TOKEN:
    print("Error: Set DISCORD_APPLICATION_ID and DISCORD_TOKEN environment variables")
    exit(1)

url = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/commands"

command = {
    "name": "baba",
    "description": "Talk to Baba (John Flinchbaugh bot)",
    "options": [
        {
            "name": "message",
            "description": "What do you want to say?",
            "type": 3,  # STRING type
            "required": True
        }
    ]
}

headers = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type": "application/json"
}

response = requests.post(url, json=command, headers=headers)

if response.status_code in [200, 201]:
    print("✓ Command registered successfully!")
    print(f"  Command: /baba")
    print(f"  Users can now use: /baba message:hello")
else:
    print(f"✗ Failed to register command")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.text}")
