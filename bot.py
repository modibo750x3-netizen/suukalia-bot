#!/usr/bin/env python3
"""
Suukalia Telegram Content Bo
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

# ── Bootstrap ──────────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Telegram message length limit ─────────────────────────────────────────────
MAX_MSG_LEN = 4000

# ── Wavespeed ──────────────────────────────────────────────────────────────────
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

# ── Persistent reply keyboard ──────────────────────────────────────────────────
MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["/faceswap 🔄",  "/video 🎬"],
        ["/ig 📸",        "/ign 👩‍⚕️"],
        ["/reel1 🎬",     "/reel2 💋"],
        ["/t 🐦",         "/fanvue 🩷"],
        ["/th 🧵",        "/ppv 💰"],
        ["/prompt 🤖",    "/day 📅"],
        ["/checklist ✅"],
    ],
    resize_keyboard=True,
    input_field_placeholder="Choose a command…",
)

# ── Weekly checklist items ─────────────────────────────────────────────────────
CHECKLIST_ITEMS = [
    "Générer prompts Higgsfield (/prompt x7)",
    "Générer captions IG bikini (/ig x7)",
    "Générer captions nurse (/ign x3)",
    "Générer tweets semaine (/t x7)",
    "Générer posts Threads (/th x3)",
    "Programmer sur Metricool",
    "Préparer contenu Fanvue (/ppv)",
    "Shooter les visuels de la semaine",
]


def render_checklist(checked: set) -> str:
    lines = ["📋 *Checklist semaine* — réponds avec un numéro pour cocher/décocher\n"]
    for i, item in enumerate(CHECKLIST_ITEMS, start=1):
        box = "✅" if i in checked else "☐"
        lines.append(f"{box} {i}. {item}")
    done = len(checked)
    total = len(CHECKLIST_ITEMS)
    lines.append(f"\n_{done}/{total} complété{'s' if done != 1 else ''}_")
    return "\n".join(lines)

# ── Bot command list (shows up when user types /) ──────────────────────────────
BOT_COMMANDS = [
    BotCommand("faceswap", "Face swap via Wavespeed Nano Banana 2"),
    BotCommand("video",  "Generate video — twerking (Kling 3.0)"),
    BotCommand("video2", "Generate video — crawl (Kling 3.0)"),
    BotCommand("video3", "Generate video — floor sit (Kling 3.0)"),
    BotCommand("video4", "Generate video — squat (Kling 3.0)"),
    BotCommand("video5", "Generate video — bed roll (Kling 3.0)"),
    BotCommand("video6", "Generate video — body run (Kling 3.0)"),
    BotCommand("video7", "Generate video — arch back (Kling 3.0)"),
    BotCommand("video8", "Generate video — catwalk (Kling 3.0)"),
    BotCommand("ig",     "5 Instagram bikini captions + hashtags"),
    BotCommand("ign",    "5 nurse practitioner captions"),
    BotCommand("reel1",  "Viral reel script"),
    BotCommand("reel2",  "5 provocative nurse phrases"),
    BotCommand("t",      "6 tweets — full mix (relatable + nurse)"),
    BotCommand("fanvue", "1 casual Fanvue mention tweet (2x/week max)"),
    BotCommand("th",     "3 Threads posts"),
    BotCommand("ppv",    "3 Fanvue PPV ideas"),
    BotCommand("prompt", "Higgsfield arch back prompt"),
    BotCommand("day",       "Full daily content plan"),
    BotCommand("checklist", "Weekly Monday checklist"),
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


# ── Wavespeed helpers ──────────────────────────────────────────────────────────
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


# ── /faceswap ─────────────────────────────────────────────────────────────────
HIGGSFIELD_BASE = "https://fnf.higgsfield.ai"


async def _higgsfield_upload(image_bytes: bytes, filename: str) -> dict:
    """Upload an image to Higgsfield, returns {id, url, type}."""
    import uuid as _uuid
    jwt = os.environ.get("HIGGSFIELD_JWT", "").strip()
    image_id = str(_uuid.uuid4())
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{HIGGSFIELD_BASE}/media/{image_id}/upload",
            headers={"Authorization": f"Bearer {jwt}"},
            files={"file": (filename, image_bytes, "image/jpeg")},
        )
        resp.raise_for_status()
        data = resp.json()
        return {"id": data.get("id", image_id), "url": data.get("url", ""), "type": "media_input"}


async def _higgsfield_poll(job_id: str, max_wait: int = 180, interval: int = 5) -> str | None:
    """Poll Higgsfield job until completed. Returns image URL or None."""
    jwt = os.environ.get("HIGGSFIELD_JWT", "").strip()
    headers = {"Authorization": f"Bearer {jwt}"}
    deadline = asyncio.get_event_loop().time() + max_wait
    async with httpx.AsyncClient(timeout=30) as client:
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(interval)
            try:
                resp = await client.get(f"{HIGGSFIELD_BASE}/jobs/{job_id}", headers=headers)
                data = resp.json()
                status = data.get("status", "")
                if status == "completed":
                    return data.get("results", {}).get("raw", {}).get("url")
                elif status in ("failed", "nsfw", "error"):
                    return None
            except Exception:
                pass
    return None


async def cmd_faceswap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["awaiting_faceswap"] = True
    await update.message.reply_text("📸 Envoie-moi une photo — je vais swapper le visage !")


async def handle_faceswap_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Triggered when the user sends a photo after /faceswap."""
    if not context.user_data.get("awaiting_faceswap"):
        return
    context.user_data["awaiting_faceswap"] = False

    jwt = os.environ.get("HIGGSFIELD_JWT", "").strip()
    if not jwt:
        await update.message.reply_text("❌ HIGGSFIELD_JWT non configuré.")
        return

    await update.message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
    await update.message.reply_text("⏳ Face swap en cours… (30-60 sec)")

    try:
        photo = update.message.photo[-1]
        tg_file = await context.bot.get_file(photo.file_id)
        tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        face_url = f"https://api.telegram.org/file/bot{tg_token}/{tg_file.file_path}"

        async with httpx.AsyncClient(timeout=30) as dl:
            img_resp = await dl.get(face_url)
            img_bytes = img_resp.content

        uploaded = await _higgsfield_upload(img_bytes, "face.jpg")
        face_image = {"id": uploaded["id"], "url": uploaded["url"], "type": "media_input"}

        ref_id = os.environ.get("HIGGSFIELD_REF_ID", "9c30dcd3-1519-40ba-a6a9-79316070fa65")
        ref_url = os.environ.get("REFERENCE_IMAGE_URL", "")
        target_image = {"id": ref_id, "url": ref_url, "type": "media_input"}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{HIGGSFIELD_BASE}/jobs/nano-banana",
                headers={"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"},
                json={
                    "params": {
                        "prompt": "Image 1 is the face reference. Naturally replace the face in image 2 with image 1. Same lighting and skin tone.",
                        "aspect_ratio": "4:5",
                        "resolution": "4k",
                        "batch_size": 1,
                        "width": 3712,
                        "height": 4608,
                        "input_images": [face_image, target_image],
                    }
                },
            )
            resp.raise_for_status()
            data = resp.json()
            job_id = data["job_sets"][0]["jobs"][0]["id"]

        result_url = await _higgsfield_poll(job_id)
        if not result_url:
            await update.message.reply_text("❌ La génération a échoué ou a pris trop de temps.")
            return

        async with httpx.AsyncClient(timeout=60) as client:
            img_resp = await client.get(result_url)
        from io import BytesIO
        await update.message.reply_photo(photo=BytesIO(img_resp.content))

    except Exception as e:
        await update.message.reply_text(f"❌ Erreur: {e}")


# ── /video – /video8 ───────────────────────────────────────────────────────────
async def _run_video(update: Update, cmd_key: str) -> None:
    wavespeed_api_key = os.environ.get("WAVESPEED_API_KEY", "").strip()
    if not wavespeed_api_key:
        await update.message.reply_text("❌ WAVESPEED_API_KEY non configuré.")
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

    await update.message.reply_text("🎬 Génération en cours… (30-90 sec)")

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
                "❌ La génération a échoué ou a dépassé le délai. Réessaie dans un moment."
            )
    except Exception as exc:
        logger.exception("Video generation error (%s): %s", cmd_key, exc)
        await update.message.reply_text("❌ Une erreur s'est produite. Réessaie.")


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


# ── /checklist ─────────────────────────────────────────────────────────────────
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
    # Photo handler — face swap (must come before text handler)
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

    logger.info("Suukalia Bot is starting — polling for updates...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
