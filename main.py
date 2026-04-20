"""Discord bot that responds to messages using a fine-tuned GPT model."""

import datetime
import logging
import os
import re
import zoneinfo
from collections import defaultdict

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
    """Post weekly Wordle leaderboard every Monday at 6am Eastern."""
    now = datetime.datetime.now(EASTERN)
    if now.weekday() != 0:
        return
    channel = bot.get_channel(PUBIS_WEDNESDAY_CHANNEL_ID)
    if channel is None:
        channel = await bot.fetch_channel(PUBIS_WEDNESDAY_CHANNEL_ID)

    # Collect last 7 days of messages (Mon–Sun)
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
