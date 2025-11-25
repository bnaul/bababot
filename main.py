"""Discord webhook handler using FastAPI for serverless deployment."""

import logging
import os
from typing import Optional

import requests
from fastapi import FastAPI, Request, Response, HTTPException
from openai import OpenAI
from pydantic import BaseModel
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "trumpbot-1470174245960")
DISCORD_PUBLIC_KEY = os.getenv("DISCORD_PUBLIC_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
GPT_MODEL_ID = "ft:gpt-4.1-nano-2025-04-14:replica::CfGoUdMt"
SYSTEM_PROMPT = """You are John Flinchbaugh talking to his friends on Discord.

You are a Dallas Mavericks and Texas Rangers fan, you like music and have a very silly non-sensical Discord persona.

Whenever you are asked a question, you always answer with confidence, and never say "I dunno" or "Haha".
"""

logging.basicConfig(level=logging.INFO)

app = FastAPI()


def verify_signature(signature: str, timestamp: str, body: bytes) -> bool:
    """Verify Discord request signature."""
    if not DISCORD_PUBLIC_KEY:
        logging.warning("DISCORD_PUBLIC_KEY not set, skipping verification")
        return True

    try:
        verify_key = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))
        verify_key.verify(timestamp.encode() + body, bytes.fromhex(signature))
        return True
    except BadSignatureError:
        return False
    except Exception as e:
        logging.error(f"Signature verification error: {e}")
        return False


class DiscordInteraction(BaseModel):
    """Discord interaction payload."""
    type: int
    data: Optional[dict] = None
    guild_id: Optional[str] = None
    channel_id: Optional[str] = None
    member: Optional[dict] = None
    user: Optional[dict] = None
    token: str
    id: str


def query_gpt_model(prompt, min_tokens=4, max_tokens=256, temperature=0.7, max_retries=5):
    """Sends a prompt to the GPT model and returns its response."""
    client = OpenAI()

    for _ in range(max_retries):
        completion = client.chat.completions.create(
            model=GPT_MODEL_ID,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = completion.choices[0].message.content
        if len(content.split(" ")) >= min_tokens:
            break
    else:
        logging.error("Gave up after %d retries.", max_retries)

    return content

@app.post("/discord/interactions")
async def handle_interaction(request: Request):
    """Handle Discord interactions (slash commands)."""
    # Get headers and body for signature verification
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")
    body = await request.body()

    # Verify the request signature
    if not verify_signature(signature, timestamp, body):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse the interaction
    import json
    interaction_data = json.loads(body)

    # Type 1: PING - Discord verifies the endpoint
    if interaction_data.get("type") == 1:
        return {"type": 1}

    # Type 2: Application Command
    if interaction_data.get("type") == 2:
        command_name = interaction_data.get("data", {}).get("name")

        if command_name == "baba":
            # Get the user's message
            options = interaction_data.get("data", {}).get("options", [])
            prompt = options[0].get("value", "Hi Baba") if options else "Hi Baba"

            # Generate response
            gpt_response = query_gpt_model(prompt)

            # Return response to Discord
            return {
                "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                "data": {
                    "content": gpt_response
                }
            }

    return {"type": 1}


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "bot": "bababot"}


@app.get("/health")
async def health():
    """Health check for Cloud Run."""
    return {"status": "healthy"}
