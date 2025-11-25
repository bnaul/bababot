#!/bin/bash
set -e

# Update system
apt-get update
apt-get install -y python3-pip git

# Clone repo (or you can copy files directly)
cd /opt
if [ ! -d "bababot" ]; then
    git clone https://github.com/bnaul/bababot.git
fi
cd bababot

# Install dependencies
pip3 install -r requirements.txt

# Set environment variables
export DISCORD_TOKEN="${DISCORD_TOKEN}"
export OPENAI_API_KEY="${OPENAI_API_KEY}"

# Run the bot
python3 main.py
