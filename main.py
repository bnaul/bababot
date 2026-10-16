"""Discord bot that responds to messages using a fine-tuned GPT model."""

import asyncio
import datetime
import logging
import os
import random
import re
import zoneinfo
from collections import defaultdict
from pathlib import Path

import discord
from discord.ext import commands, tasks
from openai import OpenAI

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "trumpbot-1470174245960")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GPT_MODEL_ID = "ft:gpt-4.1-nano-2025-04-14:replica::CfGoUdMt"
SYSTEM_PROMPT = """You are John Flinchbaugh talking to his friends on Discord.

You are a Dallas Mavericks and Texas Rangers fan, you like music and have a very silly non-sensical Discord persona.

Whenever you are asked a question, you always answer with confidence, and never say "I dunno" or "Haha".
"""

# "finetune" uses GPT_MODEL_ID; "prompt" uses PROMPT_MODEL_ID with few-shot examples
# built by scripts/build_persona_prompt.py; "local" uses the self-hosted LoRA fine-tune
# (Qwen3.5-4B) served by llama-server's OpenAI-compatible API
BOT_BACKEND = os.getenv("BOT_BACKEND", "finetune")
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://127.0.0.1:8088/v1")
PROMPT_MODEL_ID = os.getenv("PROMPT_MODEL_ID", "gpt-6-luna")
PERSONA_EXAMPLES_PATH = Path(os.getenv("PERSONA_EXAMPLES_PATH", Path(__file__).parent / "data" / "persona_examples.txt"))
PROMPT_STYLE_GUIDE = """
You are not an assistant. Never offer help, never explain yourself, never break character, and never mention being an AI.

The whole point of this bot is to be dumb, absurd, and nonsensical. Do NOT be clever or witty:
- No jokes, puns, wordplay, punchlines, or witty observations about what your friend said.
- Never repeat or riff on your friend's words back to them.
- Often only half-follow the conversation, misunderstand it, or ignore it entirely and bring up \
something unrelated that came out of nowhere. Vary the tangents a lot; never fall into a pattern \
like tacking on a sports score.
- It's fine to be confidently wrong, mundane, rambling, or to contradict yourself.
- Sloppy is good: typos, odd capitalization, no closing punctuation, several short lines.

Match the voice of the real messages below. Most are short, but sometimes John goes on a long tangent.

Here are real messages John sent, each with the message from a friend he was replying to:
"""
# Chance of planting a random past John message as a "thought" to pull the reply off topic,
# mimicking the fine-tuned model's tangents
TANGENT_PROBABILITY = float(os.getenv("TANGENT_PROBABILITY", "0.5"))


def build_prompt_system_message():
    """System prompt for the prompt-based backend. Kept byte-identical across calls so it is cached."""
    return SYSTEM_PROMPT + PROMPT_STYLE_GUIDE + "\n" + PERSONA_EXAMPLES_PATH.read_text()


def load_tangent_pool():
    """John's replies from the example file, used to seed random tangents."""
    return re.findall(r"^john: (.*?)\n</example>", PERSONA_EXAMPLES_PATH.read_text(), re.M | re.S)


def tangent_message():
    """Added after the conversation (so the cached prefix is unchanged) to push replies off topic."""
    if random.random() >= TANGENT_PROBABILITY:
        return []
    thought = random.choice(TANGENT_POOL)
    return [{"role": "system", "content": f"Something random on your mind right now (riff on it, or on something else, instead of the conversation):\n{thought}"}]

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Store conversation history per channel (last 10 messages)
conversation_history = {}

# Channel for scheduled posts
PUBIS_WEDNESDAY_CHANNEL_ID = 1418289476781998153

# 6am Eastern time
EASTERN = zoneinfo.ZoneInfo("America/New_York")
TUESDAY_POST_TIME = datetime.time(hour=6, minute=0, tzinfo=EASTERN)
WEDNESDAY_POST_TIME = datetime.time(hour=6, minute=0, tzinfo=EASTERN)
MONDAY_POST_TIME = datetime.time(hour=6, minute=0, tzinfo=EASTERN)

WORDLE_BOT_ID = 1211781489931452447
WORDLE_USER_ID_TO_NAME = {
    "1293357226949345354": "jflinchb4",
    "1418330168560320564": "brittbruttbrottboof",
    "805134315616862208": "bnaul",
    "794037600003817502": "djontology",
    "160295234746580993": "darthnowitzki41",
    "789364254855135252": "ragonk_nd",
}
WORDLE_NAME_ALIASES = {
    "brutt": "bnaul",
    "Fontanananana": "jflinchb4",
    "Brott": "darthnowitzki41",
}


def _resolve_wordle_name(token):
    mention = re.match(r"<@(\d+)>", token)
    if mention:
        name = WORDLE_USER_ID_TO_NAME.get(mention.group(1), f"<@{mention.group(1)}>")
    else:
        name = token.lstrip("@")
    return WORDLE_NAME_ALIASES.get(name, name)


def _parse_wordle_score(score_str):
    return 7 if score_str.upper().startswith("X") else int(score_str.split("/")[0])


def _format_weekly_wordle_stats(messages, since: datetime.date):
    records = []
    for msg in messages:
        if msg.author.id != WORDLE_BOT_ID:
            continue
        if "yesterday" not in msg.content.lower():
            continue
        post_date = msg.created_at.astimezone(EASTERN).date()
        game_date = post_date - datetime.timedelta(days=1)
        if game_date < since:
            continue
        for line in msg.content.split("\n"):
            m = re.match(r"[👑\s]*([X\d]/6):\s*(.+)", line)
            if not m:
                continue
            score = _parse_wordle_score(m.group(1))
            for player in re.split(r"\s+", m.group(2).strip()):
                name = _resolve_wordle_name(player)
                if name:
                    records.append({"date": str(game_date), "player": name, "score": score})

    if not records:
        return None

    stats = defaultdict(lambda: {"games": 0, "total": 0, "fails": 0, "wins": 0})
    for r in records:
        p = r["player"]
        stats[p]["games"] += 1
        stats[p]["total"] += r["score"]
        if r["score"] == 7:
            stats[p]["fails"] += 1
        else:
            stats[p]["wins"] += 1

    ranked = sorted(stats.items(), key=lambda x: x[1]["total"] / x[1]["games"])
    num_days = len(set(r["date"] for r in records))

    lines = [f"**Weekly Wordle Leaderboard** ({since.strftime('%b %d')} – {(since + datetime.timedelta(days=6)).strftime('%b %d')}, {num_days} day{'s' if num_days != 1 else ''})"]
    lines.append("```")
    lines.append(f"{'Player':<25} {'Games':>5} {'Avg':>5} {'Fails':>5} {'Win%':>6}")
    lines.append("-" * 50)
    for name, s in ranked:
        avg = s["total"] / s["games"]
        win_pct = 100 * s["wins"] / s["games"]
        lines.append(f"{name:<25} {s['games']:>5} {avg:>5.2f} {s['fails']:>5} {win_pct:>5.1f}%")
    lines.append("```")
    return "\n".join(lines)


def _is_todays_wordle_recap(message, today: datetime.date):
    return (
        message.channel.id == PUBIS_WEDNESDAY_CHANNEL_ID
        and message.author.id == WORDLE_BOT_ID
        and "yesterday" in message.content.lower()
        and message.created_at.astimezone(EASTERN).date() == today
    )


async def _wait_for_todays_wordle_recap(channel, today: datetime.date):
    """Wait until the Wordle bot has posted today's recap in the channel."""
    check = lambda message: _is_todays_wordle_recap(message, today)

    # Start listening before checking history so a recap arriving during the
    # history request cannot slip through the gap.
    waiter = asyncio.create_task(bot.wait_for("message", check=check))
    try:
        start_of_day = datetime.datetime.combine(today, datetime.time.min, tzinfo=EASTERN)
        async for message in channel.history(limit=100, after=start_of_day):
            if check(message):
                logging.info("Today's Wordle recap is already available")
                return message

        logging.info("Waiting for today's Wordle recap before posting the weekly leaderboard")
        message = await waiter
        logging.info("Today's Wordle recap arrived")
        return message
    finally:
        if not waiter.done():
            waiter.cancel()


def query_gpt_model(messages, min_tokens=4, max_tokens=256, temperature=0.7, max_retries=5):
    """Sends messages to the GPT model and returns its response.

    Args:
        messages: List of message dicts with 'role' and 'content' keys
    """
    client = OpenAI(base_url=LOCAL_LLM_URL, api_key="unused") if BOT_BACKEND == "local" else OpenAI()

    if BOT_BACKEND == "local":
        # The small model loops ("no\nno\nno...") without repetition penalties; DRY + a
        # slightly higher temperature keeps it rambling without getting stuck
        request = dict(
            model="bababot",
            max_tokens=max_tokens,
            temperature=0.9,
            extra_body={"dry_multiplier": 0.8, "repeat_penalty": 1.1},
        )
    elif BOT_BACKEND == "prompt":
        # Swap in the few-shot system prompt; Luna-style reasoning models don't accept
        # temperature or max_tokens
        messages = (
            [{"role": "system", "content": PROMPT_SYSTEM_MESSAGE}]
            + [m for m in messages if m["role"] != "system"]
            + tangent_message()
        )
        request = dict(model=PROMPT_MODEL_ID, max_completion_tokens=max_tokens, reasoning_effort="none")
    else:
        request = dict(model=GPT_MODEL_ID, max_tokens=max_tokens, temperature=temperature)

    for _ in range(max_retries):
        completion = client.chat.completions.create(messages=messages, **request)
        content = completion.choices[0].message.content
        if len(content.split(" ")) >= min_tokens:
            break
    else:
        logging.error("Gave up after %d retries.", max_retries)

    return content


PROMPT_SYSTEM_MESSAGE = build_prompt_system_message() if BOT_BACKEND == "prompt" else None
TANGENT_POOL = load_tangent_pool() if BOT_BACKEND == "prompt" else None

@tasks.loop(time=TUESDAY_POST_TIME)
async def tumor_tuesday():
    """Post Happy Tumor Tuesday message every Tuesday at 6am Eastern."""
    # Check if today is Tuesday (weekday 1)
    now = datetime.datetime.now(EASTERN)
    if now.weekday() == 1:
        channel = bot.get_channel(PUBIS_WEDNESDAY_CHANNEL_ID)
        if channel is None:
            channel = await bot.fetch_channel(PUBIS_WEDNESDAY_CHANNEL_ID)
        await channel.send("@here Happy Tumor Tuesday!")
        logging.info("Posted Tumor Tuesday message")


@tasks.loop(time=WEDNESDAY_POST_TIME)
async def pubis_wednesday():
    """Post Happy Pubis Wednesday message every Wednesday at 6am Eastern."""
    # Check if today is Wednesday (weekday 2)
    now = datetime.datetime.now(EASTERN)
    if now.weekday() == 2:
        channel = bot.get_channel(PUBIS_WEDNESDAY_CHANNEL_ID)
        if channel is None:
            channel = await bot.fetch_channel(PUBIS_WEDNESDAY_CHANNEL_ID)
        await channel.send("@here Happy Pubis Wednesday!")
        logging.info("Posted Pubis Wednesday message")


@tasks.loop(time=MONDAY_POST_TIME)
async def wordle_monday():
    """Post the weekly Wordle leaderboard after Monday's recap arrives."""
    now = datetime.datetime.now(EASTERN)
    if now.weekday() != 0:
        return
    channel = bot.get_channel(PUBIS_WEDNESDAY_CHANNEL_ID)
    if channel is None:
        channel = await bot.fetch_channel(PUBIS_WEDNESDAY_CHANNEL_ID)

    await _wait_for_todays_wordle_recap(channel, now.date())

    # Collect last 7 days of messages (Mon–Sun), including Sunday's results
    # from the recap that was just posted today.
    since = (now - datetime.timedelta(days=7)).date()
    after_dt = datetime.datetime.combine(since, datetime.time.min, tzinfo=EASTERN)
    messages = [msg async for msg in channel.history(limit=500, after=after_dt, oldest_first=True)]

    summary = _format_weekly_wordle_stats(messages, since)
    if summary:
        await channel.send(f"@here {summary}")
        logging.info("Posted weekly Wordle leaderboard")

        gpt_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Here are the Wordle results for the past week:\n\n{summary}\n\nWhat do you think?"},
        ]
        async with channel.typing():
            gpt_response = query_gpt_model(gpt_messages, max_tokens=512)
        await channel.send(gpt_response)
    else:
        logging.info("No Wordle data found for the past week")


@bot.event
async def on_ready():
    """Called when the bot is ready."""
    logging.info(f"{bot.user} has connected to Discord!")
    if not tumor_tuesday.is_running():
        tumor_tuesday.start()
    if not pubis_wednesday.is_running():
        pubis_wednesday.start()
    if not wordle_monday.is_running():
        wordle_monday.start()



@bot.event
async def on_message(message):
    """Respond to messages when mentioned."""
    if message.author == bot.user:
        return

    if message.author.bot:
        return

    # Only respond if the bot is mentioned
    if bot.user not in message.mentions:
        # On Wednesdays, respond to all messages in the Pubis Wednesday channel
        now = datetime.datetime.now(EASTERN)
        if now.weekday() == 2 and message.channel.id == PUBIS_WEDNESDAY_CHANNEL_ID:
            await message.reply("Don't forget Pubis Wednesday!")
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


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is not set")
    bot.run(DISCORD_TOKEN)
