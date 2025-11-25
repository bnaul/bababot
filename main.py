"""Discord bot that responds to messages using a fine-tuned GPT model."""

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

@bot.event
async def on_ready():
    """Called when the bot is ready."""
    logging.info(f"{bot.user} has connected to Discord!")


@bot.event
async def on_message(message):
    """Respond to messages in Discord channels."""
    if message.author == bot.user:
        return

    if message.author.bot:
        return

    logging.info(f"Message from {message.author}: {message.content}")

    try:
        async with message.channel.typing():
            gpt_response = query_gpt_model(message.content)

        await message.reply(gpt_response)
    except Exception as e:
        logging.error(f"Error processing message: {e}")
        await message.reply("Sorry, I had trouble responding to that!")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is not set")
    bot.run(DISCORD_TOKEN)
