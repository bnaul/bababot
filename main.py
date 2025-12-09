"""Discord bot that responds to messages using a fine-tuned GPT model."""

import argparse
import asyncio
import logging
import os

import discord
from discord.ext import commands
from openai import OpenAI

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "trumpbot-1470174245960")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GPT_MODEL_ID = "ft:gpt-4.1-nano-2025-04-14:replica::CfGoUdMt"
SYSTEM_PROMPT = """You are John Flinchbaugh talking to his friends on Discord.

You are a Dallas Mavericks and Texas Rangers fan, you like music and have a very silly non-sensical Discord persona.

Whenever you are asked a question, you always answer with confidence, and never say "I dunno" or "Haha".
"""

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Store conversation history per channel (last 10 messages)
conversation_history = {}


def query_gpt_model(messages, min_tokens=4, max_tokens=256, temperature=0.7, max_retries=5):
    """Sends messages to the GPT model and returns its response.

    Args:
        messages: List of message dicts with 'role' and 'content' keys
    """
    client = OpenAI()

    for _ in range(max_retries):
        completion = client.chat.completions.create(
            model=GPT_MODEL_ID,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = completion.choices[0].message.content
        if len(content.split(" ")) >= min_tokens:
            break
    else:
        logging.error("Gave up after %d retries.", max_retries)

    return content

@bot.event
async def on_ready():
    """Called when the bot is ready."""
    logging.info(f"{bot.user} has connected to Discord!")


@bot.event
async def on_message(message):
    """Respond to messages when mentioned."""
    if message.author == bot.user:
        return

    if message.author.bot:
        return

    # Only respond if the bot is mentioned
    if bot.user not in message.mentions:
        return

    logging.info(f"Mentioned by {message.author}: {message.content}")

    try:
        # Remove the mention from the message
        content = message.content.replace(f'<@{bot.user.id}>', '').strip()

        # Get or create conversation history for this channel
        channel_id = message.channel.id
        if channel_id not in conversation_history:
            conversation_history[channel_id] = []

        # Build messages with conversation context
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add last 10 messages from history
        messages.extend(conversation_history[channel_id][-10:])

        # Add current message
        messages.append({"role": "user", "content": content})

        async with message.channel.typing():
            gpt_response = query_gpt_model(messages)

        # Save to conversation history
        conversation_history[channel_id].append({"role": "user", "content": content})
        conversation_history[channel_id].append({"role": "assistant", "content": gpt_response})

        # Keep only last 20 messages (10 exchanges) in history
        if len(conversation_history[channel_id]) > 20:
            conversation_history[channel_id] = conversation_history[channel_id][-20:]

        await message.reply(gpt_response)
    except Exception as e:
        logging.error(f"Error processing message: {e}")
        await message.reply("Sorry, I had trouble responding to that!")


async def post_message(channel_id: int, message: str):
    """Post a message to a Discord channel as the bot."""
    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is not set")

    client = discord.Client(intents=discord.Intents.default())

    @client.event
    async def on_ready():
        try:
            channel = client.get_channel(channel_id)
            if channel is None:
                channel = await client.fetch_channel(channel_id)
            await channel.send(message)
            logging.info(f"Posted message to channel {channel_id}")
        finally:
            await client.close()

    await client.start(DISCORD_TOKEN)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Discord bot for Baba")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Run bot command (default)
    subparsers.add_parser("run", help="Run the Discord bot")

    # Post message command
    post_parser = subparsers.add_parser("post", help="Post a message as the bot")
    post_parser.add_argument("channel_id", type=int, help="Discord channel ID")
    post_parser.add_argument("message", type=str, help="Message to post")

    args = parser.parse_args()

    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is not set")

    if args.command == "post":
        asyncio.run(post_message(args.channel_id, args.message))
    else:
        # Default to running the bot
        bot.run(DISCORD_TOKEN)
