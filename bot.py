#!/usr/bin/env python3
"""
Suukalia Telegram Content Bot
Generates AI-powered social media content using Claude (Anthropic API).
"""

import asyncio
import logging
import os

import anthropic
from dotenv import load_dotenv
from telegram import BotCommand, ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.error import NetworkError, TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes

from prompts import PROMPTS, SYSTEM_PROMPT

# ── Bootstrap ──────────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Telegram message length limit ─────────────────────────────────────────────
MAX_MSG_LEN = 4000

# ── Persistent reply keyboard ──────────────────────────────────────────────────
MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["/ig 📸",      "/ign 👩‍⚕️"],
        ["/reel1 🎬",   "/reel2 💋"],
        ["/t1 🐦",      "/t2 📈"],
        ["/fanvue 🩷",  "/th 🧵"],
        ["/ppv 💰",     "/prompt 🤖"],
        ["/day 📅"],
    ],
    resize_keyboard=True,
    persistent=True,
    input_field_placeholder="Choose a command…",
)

# ── Bot command list (shows up when user types /) ──────────────────────────────
BOT_COMMANDS = [
    BotCommand("ig",     "5 Instagram bikini captions + hashtags"),
    BotCommand("ign",    "5 nurse practitioner captions"),
    BotCommand("reel1",  "Viral reel script"),
    BotCommand("reel2",  "5 provocative nurse phrases"),
    BotCommand("t1",     "4 tweets — personality"),
    BotCommand("t2",     "3 tweets — relationships & desire"),
    BotCommand("fanvue", "1 casual Fanvue mention tweet (2x/week max)"),
    BotCommand("th",     "3 Threads posts"),
    BotCommand("ppv",    "3 Fanvue PPV ideas"),
    BotCommand("prompt", "Higgsfield arch back prompt"),
    BotCommand("day",    "Full daily content plan"),
]


# ── Core AI call ──────────────────────────────────────────────────────────────
async def generate_content(ai_client: anthropic.AsyncAnthropic, prompt: str, max_tokens: int = 2500) -> str:
    """Call Claude and return the full text response."""
    response = await ai_client.messages.create(
        model="claude-opus-4-6",
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "\n".join(
        block.text for block in response.content if block.type == "text"
    ).strip()
    if not text:
        raise ValueError("Empty response from Claude")
    return text


# ── Telegram helpers ──────────────────────────────────────────────────────────
async def send_chunks(update: Update, text: str) -> None:
    """Send a potentially long message, splitting into ≤4000-char chunks."""
    if len(text) <= MAX_MSG_LEN:
        await update.message.reply_text(text)
        return

    paragraphs = text.split("\n\n")
    chunk = ""
    for para in paragraphs:
        candidate = f"{chunk}\n\n{para}".strip() if chunk else para
        if len(candidate) <= MAX_MSG_LEN:
            chunk = candidate
        else:
            if chunk:
                await update.message.reply_text(chunk)
                await asyncio.sleep(0.4)
            while len(para) > MAX_MSG_LEN:
                await update.message.reply_text(para[:MAX_MSG_LEN])
                await asyncio.sleep(0.4)
                para = para[MAX_MSG_LEN:]
            chunk = para

    if chunk:
        await update.message.reply_text(chunk)


async def run_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    key: str,
) -> None:
    """Generic dispatcher: show typing → call Claude → send result."""
    await update.message.reply_chat_action(ChatAction.TYPING)
    prompt, max_tokens = PROMPTS[key]
    ai_client: anthropic.AsyncAnthropic = context.bot_data["ai_client"]

    try:
        content = await generate_content(ai_client, prompt, max_tokens)
        await send_chunks(update, content)
    except anthropic.AuthenticationError:
        logger.error("Anthropic authentication failed — check ANTHROPIC_API_KEY")
        await update.message.reply_text(
            "❌ Authentication error. Please contact the bot admin."
        )
    except anthropic.RateLimitError:
        logger.warning("Anthropic rate limit hit")
        await update.message.reply_text(
            "⏳ Too many requests right now. Please wait a moment and try again."
        )
    except anthropic.APIStatusError as exc:
        logger.error("Anthropic API error %s: %s", exc.status_code, exc.message)
        await update.message.reply_text(
            "❌ AI service error. Please try again in a moment."
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error in /%s: %s", key, exc)
        await update.message.reply_text(
            "❌ Something went wrong. Please try again."
        )


# ── /start & /help ─────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "✨ Suukalia Content Bot ✨\n\nTap a button below to generate content instantly 🚀",
        reply_markup=MENU_KEYBOARD,
    )


# ── Command handlers ───────────────────────────────────────────────────────────
async def cmd_ig(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_command(update, context, "ig")


async def cmd_ign(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_command(update, context, "ign")


async def cmd_reel1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_command(update, context, "reel1")


async def cmd_reel2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_command(update, context, "reel2")


async def cmd_t1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_command(update, context, "t1")


async def cmd_t2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_command(update, context, "t2")


async def cmd_fanvue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_command(update, context, "fanvue")


async def cmd_th(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_command(update, context, "th")


async def cmd_ppv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_command(update, context, "ppv")


async def cmd_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_command(update, context, "prompt")


async def cmd_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_command(update, context, "day")


# ── Global error handler ───────────────────────────────────────────────────────
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors but never let them crash the bot process."""
    err = context.error
    if isinstance(err, NetworkError):
        logger.warning("Network error (will auto-retry): %s", err)
    elif isinstance(err, TelegramError):
        logger.error("Telegram error: %s", err)
    else:
        logger.exception("Unhandled exception: %s", err)


# ── Startup hook — register bot commands with Telegram ────────────────────────
async def post_init(app: Application) -> None:
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Bot commands registered with Telegram")


# ── Entry point ────────────────────────────────────────────────────────────────
def main() -> None:
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if not telegram_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")
    if not anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")

    ai_client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)

    app = Application.builder().token(telegram_token).post_init(post_init).build()
    app.bot_data["ai_client"] = ai_client

    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("ig", cmd_ig))
    app.add_handler(CommandHandler("ign", cmd_ign))
    app.add_handler(CommandHandler("reel1", cmd_reel1))
    app.add_handler(CommandHandler("reel2", cmd_reel2))
    app.add_handler(CommandHandler("t1", cmd_t1))
    app.add_handler(CommandHandler("t2", cmd_t2))
    app.add_handler(CommandHandler("fanvue", cmd_fanvue))
    app.add_handler(CommandHandler("th", cmd_th))
    app.add_handler(CommandHandler("ppv", cmd_ppv))
    app.add_handler(CommandHandler("prompt", cmd_prompt))
    app.add_handler(CommandHandler("day", cmd_day))

    logger.info("Suukalia Bot is starting — polling for updates...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
