#!/usr/bin/env python3
"""
Suukalia Telegram Content Bot
Generates AI-powered social media content using Claude (Anthropic API).
"""

import asyncio
import logging
import os
import random

import anthropic
import httpx
from dotenv import load_dotenv
from telegram import BotCommand, ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.error import NetworkError, TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from prompts import PROMPTS, SYSTEM_PROMPT

# ââ Bootstrap ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ââ Telegram message length limit âââââââââââââââââââââââââââââââââââââââââââââ
MAX_MSG_LEN = 4000

# ââ Wavespeed ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
WAVESPEED_BASE = "https://api.wavespeed.ai/api/v2"
REFERENCE_IMAGE_URL = "https://drive.google.com/uc?export=download&id=1TfDZ_isId3LoLgb_MQvaJATJuAhADx42"

VIDEO_MOTIONS = {
    "video":  "twerking, slow bounce, low angle, hypnotic rhythm",
    "video2": "on all fours, looking directly at camera, slow crawl",
    "video3": "sitting on floor, legs spread, leaning back on hands",
    "video4": "squatting slowly, hands resting on knees, seductive gaze",
    "video5": "lying on bed, slow full body roll, tangled in sheets",
    "video6": "standing, hands slowly running down body from neck to hips",
    "video7": "arching back, dramatic hair flip, look over shoulder",
    "video8": "walking toward camera slowly, confident strut, direct eye contact",
}

VIDEO_OUTFITS = [
    "tiny triangle bikini",
    "black lace lingerie",
    "high cut bodysuit",
    "sheer mesh outfit",
    "sports bra and booty shorts",
    "silk bralette and thong",
]

# ââ Persistent reply keyboard ââââââââââââââââââââââââââââââââââââââââââââââââââ
MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["/faceswap ð",  "/video ð¬"],
        ["/ig ð¸",        "/ign ð©ââï¸"],
        ["/reel1 ð¬",     "/reel2 ð"],
        ["/t ð¦",         "/fanvue ð©·"],
        ["/th ð§µ",        "/ppv ð°"],
        ["/prompt ð¤",    "/day ð"],
        ["/checklist â"],
    ],
    resize_keyboard=True,
    input_field_placeholder="Choose a commandâ¦",
)

# ââ Weekly checklist items âââââââââââââââââââââââââââââââââââââââââââââââââââââ
CHECKLIST_ITEMS = [
    "GÃ©nÃ©rer prompts Higgsfield (/prompt x7)",
    "GÃ©nÃ©rer captions IG bikini (/ig x7)",
    "GÃ©nÃ©rer captions nurse (/ign x3)",
    "GÃ©nÃ©rer tweets semaine (/t x7)",
    "GÃ©nÃ©rer posts Threads (/th x3)",
    "Programmer sur Metricool",
    "PrÃ©parer contenu Fanvue (/ppv)",
    "Shooter les visuels de la semaine",
]


def render_checklist(checked: set) -> str:
    lines = ["ð *Checklist semaine* â rÃ©ponds avec un numÃ©ro pour cocher/dÃ©cocher\n"]
    for i, item in enumerate(CHECKLIST_ITEMS, start=1):
        box = "â" if i in checked else "â"
        lines.append(f"{box} {i}. {item}")
    done = len(checked)
    total = len(CHECKLIST_ITEMS)
    lines.append(f"\n_{done}/{total} complÃ©tÃ©{'s' if done != 1 else ''}_")
    return "\n".join(lines)

# ââ Bot command list (shows up when user types /) ââââââââââââââââââââââââââââââ
BOT_COMMANDS = [
    BotCommand("faceswap", "Face swap via Wavespeed Nano Banana 2"),
    BotCommand("video",  "Generate video â twerking (Kling 3.0)"),
    BotCommand("video2", "Generate video â crawl (Kling 3.0)"),
    BotCommand("video3", "Generate video â floor sit (Kling 3.0)"),
    BotCommand("video4", "Generate video â squat (Kling 3.0)"),
    BotCommand("video5", "Generate video â bed roll (Kling 3.0)"),
    BotCommand("video6", "Generate video â body run (Kling 3.0)"),
    BotCommand("video7", "Generate video â arch back (Kling 3.0)"),
    BotCommand("video8", "Generate video â catwalk (Kling 3.0)"),
    BotCommand("ig",     "5 Instagram bikini captions + hashtags"),
    BotCommand("ign",    "5 nurse practitioner captions"),
    BotCommand("reel1",  "Viral reel script"),
    BotCommand("reel2",  "5 provocative nurse phrases"),
    BotCommand("t",      "6 tweets â full mix (relatable + nurse)"),
    BotCommand("fanvue", "1 casual Fanvue mention tweet (2x/week max)"),
    BotCommand("th",     "3 Threads posts"),
    BotCommand("ppv",    "3 Fanvue PPV ideas"),
    BotCommand("prompt", "Higgsfield arch back prompt"),
    BotCommand("day",       "Full daily content plan"),
    BotCommand("checklist", "Weekly Monday checklist"),
]


# ââ Core AI call ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
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


# ââ Telegram helpers ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
async def send_chunks(update: Update, text: str) -> None:
    """Send a potentially long message, splitting into â¤4000-char chunks."""
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
    """Generic dispatcher: show typing â call Claude â send result."""
    await update.message.reply_chat_action(ChatAction.TYPING)
    prompt, max_tokens = PROMPTS[key]
    ai_client: anthropic.AsyncAnthropic = context.bot_data["ai_client"]

    try:
        content = await generate_content(ai_client, prompt, max_tokens)
        await send_chunks(update, content)
    except anthropic.AuthenticationError:
        logger.error("Anthropic authentication failed â check ANTHROPIC_API_KEY")
        await update.message.reply_text(
            "â Authentication error. Please contact the bot admin."
        )
    except anthropic.RateLimitError:
        logger.warning("Anthropic rate limit hit")
        await update.message.reply_text(
            "â³ Too many requests right now. Please wait a moment and try again."
        )
    except anthropic.APIStatusError as exc:
        logger.error("Anthropic API error %s: %s", exc.status_code, exc.message)
        await update.message.reply_text(
            "â AI service error. Please try again in a moment."
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error in /%s: %s", key, exc)
        await update.message.reply_text(
            "â Something went wrong. Please try again."
        )


# ââ Wavespeed helpers ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
async def _wavespeed_poll(prediction_id: str, max_wait: int = 160, interval: int = 15) -> dict | None:
    """Poll Wavespeed until status == succeeded/failed or timeout."""
    wavespeed_api_key = os.environ.get("WAVESPEED_API_KEY", "").strip()
    headers = {"Authorization": f"Bearer {wavespeed_api_key}"}
    deadline = asyncio.get_event_loop().time() + max_wait
    async with httpx.AsyncClient(timeout=30) as client:
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(interval)
            try:
                resp = await client.get(
                    f"{WAVESPEED_BASE}/predictions/{prediction_id}", headers=headers
                )
                data = resp.json().get("data", {})
                status = data.get("status")
                if status == "succeeded":
                    return data
                if status in ("failed", "canceled"):
                    return None
            except Exception:
                pass
    return None


# ââ /faceswap âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
async def cmd_faceswap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["awaiting_faceswap"] = True
    await update.message.reply_text(
        "ð¸ Envoie-moi une photo â je vais swapper le visage !"
    )


async def handle_faceswap_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Triggered when the user sends a photo after /faceswap."""
    if not context.user_data.get("awaiting_faceswap"):
        return
    context.user_data["awaiting_faceswap"] = False

    wavespeed_api_key = os.environ.get("WAVESPEED_API_KEY", "").strip()
    if not wavespeed_api_key:
        await update.message.reply_text("â WAVESPEED_API_KEY non configurÃ©.")
        return

    await update.message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
    await update.message.reply_text("â³ Face swap en coursâ¦ (25-50 sec)")

    # Build direct Telegram download URL for the user's photo
    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    face_image_url = f"https://api.telegram.org/file/bot{token}/{tg_file.file_path}"

    headers = {
        "Authorization": f"Bearer {wavespeed_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "images": [REFERENCE_IMAGE_URL, face_image_url],
        "prompt": "Swap the face from the second image onto the person in the first image. Keep the body, clothes, and background exactly the same.",
        "output_format": "png",
        "resolution": "1k",
        "enable_base64_output": False,
        "enable_sync_mode": False,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{WAVESPEED_BASE}/google/nano-banana-2/edit",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            prediction_id = resp.json()["data"]["id"]

        result = await _wavespeed_poll(prediction_id)
        if result and result.get("outputs"):
            await update.message.reply_photo(result["outputs"][0])
        else:
            await update.message.reply_text(
                "â La gÃ©nÃ©ration a Ã©chouÃ© ou a pris trop de temps. RÃ©essaie dans un moment."
            )
    except Exception as exc:
        logger.exception("Face swap error: %s", exc)
        await update.message.reply_text("â Une erreur s'est produite. RÃ©essaie.")


# ââ /video â /video8 âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
async def _run_video(update: Update, cmd_key: str) -> None:
    wavespeed_api_key = os.environ.get("WAVESPEED_API_KEY", "").strip()
    if not wavespeed_api_key:
        await update.message.reply_text("â WAVESPEED_API_KEY non configurÃ©.")
        return

    motion = VIDEO_MOTIONS.get(cmd_key, VIDEO_MOTIONS["video"])
    outfit = random.choice(VIDEO_OUTFITS)
    prompt = (
        "Mixed woman, voluminous curly black hair, warm golden brown skin, "
        f"hourglass figure, slim waist, 1m68. Wearing {outfit}. "
        f"{motion}. "
        "Pink neon lighting, penthouse setting. "
        "Cinematic slow motion, low angle camera, 4K, ultra-realistic, seamless loop."
    )

    await update.message.reply_text("ð¬ GÃ©nÃ©ration en coursâ¦ (30-90 sec)")

    headers = {
        "Authorization": f"Bearer {wavespeed_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": {
            "image": REFERENCE_IMAGE_URL,
            "prompt": prompt,
            "duration": 15,
            "aspect_ratio": "9:16",
            "cfg_scale": 0.5,
        },
        "enable_safety_checker": False,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{WAVESPEED_BASE}/kling/kling-v3-0-image-to-video",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            prediction_id = resp.json()["data"]["id"]

        result = await _wavespeed_poll(prediction_id, max_wait=180, interval=20)
        if result and result.get("outputs"):
            await update.message.reply_video(result["outputs"][0])
        else:
            await update.message.reply_text(
                "â La gÃ©nÃ©ration a Ã©chouÃ© ou a dÃ©passÃ© le dÃ©lai. RÃ©essaie dans un moment."
            )
    except Exception as exc:
        logger.exception("Video generation error (%s): %s", cmd_key, exc)
        await update.message.reply_text("â Une erreur s'est produite. RÃ©essaie.")


async def cmd_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_video(update, "video")

async def cmd_video2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_video(update, "video2")

async def cmd_video3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_video(update, "video3")

async def cmd_video4(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_video(update, "video4")

async def cmd_video5(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_video(update, "video5")

async def cmd_video6(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_video(update, "video6")

async def cmd_video7(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_video(update, "video7")

async def cmd_video8(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_video(update, "video8")


# ââ /start & /help âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "â¨ Suukalia Content Bot â¨\n\nTap a button below to generate content instantly ð",
        reply_markup=MENU_KEYBOARD,
    )


# ââ Command handlers âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
async def cmd_ig(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_command(update, context, "ig")


async def cmd_ign(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_command(update, context, "ign")


async def cmd_reel1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_command(update, context, "reel1")


async def cmd_reel2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_command(update, context, "reel2")


async def cmd_t(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await run_command(update, context, "t")


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


# ââ /checklist âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
async def cmd_checklist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.setdefault("checklist", set())
    await update.message.reply_text(
        render_checklist(context.user_data["checklist"]),
        parse_mode="Markdown",
    )


async def handle_checklist_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle a checklist item when the user sends a bare number."""
    text = update.message.text.strip()
    if not text.isdigit():
        return
    n = int(text)
    if not (1 <= n <= len(CHECKLIST_ITEMS)):
        return
    checked: set = context.user_data.setdefault("checklist", set())
    if n in checked:
        checked.discard(n)
    else:
        checked.add(n)
    await update.message.reply_text(
        render_checklist(checked),
        parse_mode="Markdown",
    )


# ââ Global error handler âââââââââââââââââââââââââââââââââââââââââââââââââââââââ
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors but never let them crash the bot process."""
    err = context.error
    if isinstance(err, NetworkError):
        logger.warning("Network error (will auto-retry): %s", err)
    elif isinstance(err, TelegramError):
        logger.error("Telegram error: %s", err)
    else:
        logger.exception("Unhandled exception: %s", err)


# ââ Startup hook â register bot commands with Telegram ââââââââââââââââââââââââ
async def post_init(app: Application) -> None:
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Bot commands registered with Telegram")


# ââ Entry point ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
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
    # Wavespeed commands
    app.add_handler(CommandHandler("faceswap", cmd_faceswap))
    app.add_handler(CommandHandler("video",  cmd_video))
    app.add_handler(CommandHandler("video2", cmd_video2))
    app.add_handler(CommandHandler("video3", cmd_video3))
    app.add_handler(CommandHandler("video4", cmd_video4))
    app.add_handler(CommandHandler("video5", cmd_video5))
    app.add_handler(CommandHandler("video6", cmd_video6))
    app.add_handler(CommandHandler("video7", cmd_video7))
    app.add_handler(CommandHandler("video8", cmd_video8))
    # Photo handler â face swap (must come before text handler)
    app.add_handler(MessageHandler(filters.PHOTO, handle_faceswap_photo))
    # Content generation commands
    app.add_handler(CommandHandler("ig", cmd_ig))
    app.add_handler(CommandHandler("ign", cmd_ign))
    app.add_handler(CommandHandler("reel1", cmd_reel1))
    app.add_handler(CommandHandler("reel2", cmd_reel2))
    app.add_handler(CommandHandler("t", cmd_t))
    app.add_handler(CommandHandler("fanvue", cmd_fanvue))
    app.add_handler(CommandHandler("th", cmd_th))
    app.add_handler(CommandHandler("ppv", cmd_ppv))
    app.add_handler(CommandHandler("prompt", cmd_prompt))
    app.add_handler(CommandHandler("day", cmd_day))
    app.add_handler(CommandHandler("checklist", cmd_checklist))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_checklist_toggle))

    logger.info("Suukalia Bot is starting â polling for updates...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
