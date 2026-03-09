#!/usr/bin/env python3
"""
Suukalia Team Bot — Elite OFM AI agent team + face swap.

Named agents (Phase 5):
  /marcus    — Marcus, Stratège OFM Senior (stratégie semaine)
  /sofia     — Sofia, Directrice Contenu & Copywriting [ig|twitter|threads|ppv]
  /alex      — Alex, Analyste Data & Performance [stats inline ou prompt]
  /maya      — Maya, Manager Communauté & Conversion [ppv]

Legacy agents (Phase 4, kept for compatibility):
  /strategie — Alias /marcus
  /poster    — Alias /sofia
  /stats     — Alias /alex
  /channel   — Alias /maya
  /faceswap  — Face swap via Higgsfield
"""

import asyncio
import datetime
import logging
import os
from io import BytesIO

import anthropic
import httpx
from dotenv import load_dotenv
from telegram import BotCommand, ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.error import NetworkError, TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agents import analyste_agent, channel_agent, poster_agent, strategie_agent
from agents import marcus_agent, sofia_agent, alex_agent, maya_agent

# ── Bootstrap ──────────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

MAX_MSG_LEN = 4096

# ── Keyboard ───────────────────────────────────────────────────────────────────
MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["/standup 🗓️"],
        ["/marcus 🎯",  "/sofia ✨"],
        ["/alex 📊",    "/maya 💫"],
        ["/strategie 📊", "/poster 📅"],
        ["/stats 📈",     "/channel 📢"],
        ["/faceswap 🔄"],
    ],
    resize_keyboard=True,
    input_field_placeholder="Choisis un agent…",
)

# ── Bot commands ───────────────────────────────────────────────────────────────
BOT_COMMANDS = [
    BotCommand("standup",   "Réunion équipe du jour — tous les agents se briefent"),
    BotCommand("marcus",    "Marcus — Stratège OFM Senior (stratégie semaine)"),
    BotCommand("sofia",     "Sofia — Contenu prêt à poster [ig|twitter|threads|ppv]"),
    BotCommand("alex",      "Alex — Analyse métriques data & performance"),
    BotCommand("maya",      "Maya — Post channel Telegram [ppv] (1300 abonnés)"),
    BotCommand("strategie", "Stratégie semaine @lalucigmzz version nurse"),
    BotCommand("poster",    "Contenu prêt à poster — /poster [ig|twitter|threads]"),
    BotCommand("stats",     "Analyse métriques + optimisation stratégie"),
    BotCommand("channel",   "Post channel Telegram (1300 abonnés → Fanvue)"),
    BotCommand("faceswap",  "Face swap via Higgsfield — envoie une photo"),
]

# ── Higgsfield ─────────────────────────────────────────────────────────────────
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


# ── Helpers ────────────────────────────────────────────────────────────────────
async def send_chunks(update: Update, text: str) -> None:
    """Send a long message split into ≤4096-char chunks."""
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
                await asyncio.sleep(0.3)
            while len(para) > MAX_MSG_LEN:
                await update.message.reply_text(para[:MAX_MSG_LEN])
                await asyncio.sleep(0.3)
                para = para[MAX_MSG_LEN:]
            chunk = para
    if chunk:
        await update.message.reply_text(chunk)


def _ai(context: ContextTypes.DEFAULT_TYPE) -> anthropic.AsyncAnthropic:
    return context.bot_data["ai_client"]


async def _safe_run(update: Update, coro) -> None:
    """Execute an AI coroutine and handle errors uniformly."""
    try:
        content = await coro
        await send_chunks(update, content)
    except anthropic.AuthenticationError:
        logger.error("Anthropic auth failed — check ANTHROPIC_API_KEY")
        await update.message.reply_text("❌ Erreur d'authentification. Contacte l'admin.")
    except anthropic.RateLimitError:
        logger.warning("Anthropic rate limit hit")
        await update.message.reply_text("⏳ Trop de requêtes. Patiente un moment et réessaie.")
    except anthropic.APIStatusError as exc:
        logger.error("Anthropic API %s: %s", exc.status_code, exc.message)
        await update.message.reply_text("❌ Erreur service IA. Réessaie dans un moment.")
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
        await update.message.reply_text("❌ Une erreur s'est produite. Réessaie.")


# ── /start ─────────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "✨ *Suukalia Elite Team Bot* ✨\n\n"
        "🗓️ /standup — réunion équipe du jour (tous les agents)\n\n"
        "🎯 /marcus — stratégie semaine OFM Senior\n"
        "✨ /sofia — contenu IG/Twitter/Threads/PPV\n"
        "📊 /alex — analyse métriques & data\n"
        "💫 /maya — post channel Telegram (1300 abonnés)\n"
        "🔄 /faceswap — face swap via Higgsfield\n\n"
        "Commandes legacy : /strategie · /poster · /stats · /channel\n\n"
        "Utilise les boutons ci-dessous 👇",
        reply_markup=MENU_KEYBOARD,
        parse_mode="Markdown",
    )


# ── /standup — Daily team briefing ─────────────────────────────────────────────
async def cmd_standup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Call all 4 agents in parallel for a daily briefing."""
    await update.message.reply_chat_action(ChatAction.TYPING)
    await update.message.reply_text("🗓️ Réunion en cours… Marcus, Sofia, Alex et Maya se briefent (20-30 sec)")

    ai = _ai(context)
    try:
        marcus_out, sofia_out, alex_out, maya_out = await asyncio.gather(
            marcus_agent.run_standup(ai),
            sofia_agent.run_standup(ai),
            alex_agent.run_standup(ai),
            maya_agent.run_standup(ai),
        )
    except Exception as exc:
        logger.exception("Standup error: %s", exc)
        await update.message.reply_text("❌ Erreur standup. Réessaie.")
        return

    report = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🗓️  STANDUP SUUKALIA TEAM\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{marcus_out}\n\n"
        "─────────────────────────────\n\n"
        f"{sofia_out}\n\n"
        "─────────────────────────────\n\n"
        f"{alex_out}\n\n"
        "─────────────────────────────\n\n"
        f"{maya_out}"
    )
    await send_chunks(update, report)


# ── MARCUS — Stratège OFM Senior ───────────────────────────────────────────────
async def cmd_marcus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_chat_action(ChatAction.TYPING)
    await update.message.reply_text("🎯 Marcus analyse la situation… (15-20 sec)")
    task = " ".join(context.args) if context.args else ""
    await _safe_run(update, marcus_agent.run(task, _ai(context)))


# ── SOFIA — Directrice Contenu & Copywriting ───────────────────────────────────
async def cmd_sofia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_chat_action(ChatAction.TYPING)
    platform = (context.args[0] if context.args else "all").lower()
    valid = {"ig", "twitter", "threads", "ppv", "all"}
    if platform not in valid:
        await update.message.reply_text(
            "Usage: /sofia [ig|twitter|threads|ppv]\nSans argument = toutes les plateformes."
        )
        return
    await _safe_run(update, sofia_agent.run(platform, _ai(context)))


# ── ALEX — Analyste Data & Performance ─────────────────────────────────────────
async def cmd_alex(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    inline = " ".join(context.args) if context.args else ""
    if inline:
        await update.message.reply_chat_action(ChatAction.TYPING)
        await _safe_run(update, alex_agent.run(inline, _ai(context)))
    else:
        context.user_data["awaiting_alex"] = True
        await update.message.reply_text(
            "📊 Alex attend tes métriques.\n\n"
            "Exemple :\n"
            "• Reach: 45k | Engagement: 3.2%\n"
            "• Nouveaux followers: +230\n"
            "• Top post: reel nurse 87k vues\n\n"
            "_(ou envoie ce que tu as — Alex s'adapte)_",
            parse_mode="Markdown",
        )


async def handle_alex_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get("awaiting_alex"):
        return
    context.user_data["awaiting_alex"] = False
    await update.message.reply_chat_action(ChatAction.TYPING)
    await _safe_run(update, alex_agent.run(update.message.text, _ai(context)))


# ── MAYA — Manager Communauté & Conversion ─────────────────────────────────────
async def cmd_maya(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_chat_action(ChatAction.TYPING)

    force_ppv = bool(context.args and context.args[0].lower() == "ppv")
    today = datetime.datetime.now()
    is_ppv = today.weekday() in (4, 5)  # Friday=4, Saturday=5
    day_fr = {
        "Monday": "Lundi", "Tuesday": "Mardi", "Wednesday": "Mercredi",
        "Thursday": "Jeudi", "Friday": "Vendredi", "Saturday": "Samedi", "Sunday": "Dimanche",
    }.get(today.strftime("%A"), today.strftime("%A"))

    try:
        content = await maya_agent.run(
            is_ppv_day=is_ppv, day_name=day_fr, client=_ai(context), force_ppv=force_ppv
        )
    except Exception as exc:
        logger.exception("Maya agent error: %s", exc)
        await update.message.reply_text("❌ Erreur lors de la génération. Réessaie.")
        return

    await send_chunks(update, content)

    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()
    if channel_id:
        try:
            await context.bot.send_message(chat_id=channel_id, text=content)
            tag = "🔒 PPV teaser" if (is_ppv or force_ppv) else "📢 Post quotidien"
            await update.message.reply_text(f"✅ {tag} envoyé au channel !")
        except Exception as exc:
            logger.error("Failed to post to channel %s: %s", channel_id, exc)
            await update.message.reply_text(
                "⚠️ Contenu généré mais envoi au channel échoué. "
                "Vérifie que le bot est admin dans le channel."
            )
    else:
        await update.message.reply_text(
            "_(Configure `TELEGRAM_CHANNEL_ID` pour l'envoi automatique au channel.)_",
            parse_mode="Markdown",
        )


# ── AGENT 1 — STRATÈGE ─────────────────────────────────────────────────────────
async def cmd_strategie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_chat_action(ChatAction.TYPING)
    await update.message.reply_text("📊 Analyse en cours… (peut prendre 15-20 sec)")
    await _safe_run(update, strategie_agent.run(_ai(context)))


# ── AGENT 2 — POSTER ───────────────────────────────────────────────────────────
async def cmd_poster(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_chat_action(ChatAction.TYPING)
    # args: /poster ig | /poster twitter | /poster threads | /poster (= all)
    platform = (context.args[0] if context.args else "all").lower()
    valid = {"ig", "twitter", "threads", "all"}
    if platform not in valid:
        await update.message.reply_text(
            "Usage: /poster [ig|twitter|threads]\nSans argument = toutes les plateformes."
        )
        return
    await _safe_run(update, poster_agent.run(platform, _ai(context)))


# ── AGENT 3 — ANALYSTE ─────────────────────────────────────────────────────────
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /stats → asks for metrics, waits for next message.
    /stats [inline text] → analyzes immediately.
    """
    # Inline stats: /stats reach 50k, engagement 3.2%, +230 followers
    inline = " ".join(context.args) if context.args else ""
    if inline:
        await update.message.reply_chat_action(ChatAction.TYPING)
        await _safe_run(update, analyste_agent.run(inline, _ai(context)))
    else:
        context.user_data["awaiting_stats"] = True
        await update.message.reply_text(
            "📈 Envoie-moi tes métriques de la semaine.\n\n"
            "Exemple:\n"
            "• Reach: 45k | Engagement: 3.2%\n"
            "• Nouveaux followers: +230\n"
            "• Top post: reel nurse 87k vues\n"
            "• Stories: 28% completion rate\n\n"
            "_(ou envoie juste ce que tu as)_",
            parse_mode="Markdown",
        )


async def handle_stats_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process metrics when user replies after /stats prompt."""
    if not context.user_data.get("awaiting_stats"):
        return
    context.user_data["awaiting_stats"] = False
    await update.message.reply_chat_action(ChatAction.TYPING)
    await _safe_run(
        update, analyste_agent.run(update.message.text, _ai(context))
    )


async def handle_text_replies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route text replies to the appropriate waiting agent (/alex or /stats)."""
    if context.user_data.get("awaiting_alex"):
        await handle_alex_reply(update, context)
    elif context.user_data.get("awaiting_stats"):
        await handle_stats_reply(update, context)


# ── AGENT 4 — CHANNEL MANAGER ──────────────────────────────────────────────────
async def cmd_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Generate channel content and optionally post it to the Telegram channel.
    Detects day of week automatically (PPV on Friday & Saturday).
    """
    await update.message.reply_chat_action(ChatAction.TYPING)

    today = datetime.datetime.now()
    is_ppv = today.weekday() in (4, 5)  # Friday=4, Saturday=5
    day_fr = {
        "Monday": "Lundi", "Tuesday": "Mardi", "Wednesday": "Mercredi",
        "Thursday": "Jeudi", "Friday": "Vendredi", "Saturday": "Samedi", "Sunday": "Dimanche",
    }.get(today.strftime("%A"), today.strftime("%A"))

    try:
        content = await channel_agent.run(is_ppv_day=is_ppv, day_name=day_fr, client=_ai(context))
    except Exception as exc:
        logger.exception("Channel agent error: %s", exc)
        await update.message.reply_text("❌ Erreur lors de la génération. Réessaie.")
        return

    # Show content in the bot chat
    await send_chunks(update, content)

    # If TELEGRAM_CHANNEL_ID is set, also post to the channel
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()
    if channel_id:
        try:
            await context.bot.send_message(chat_id=channel_id, text=content)
            tag = "🔒 PPV teaser" if is_ppv else "📢 Post quotidien"
            await update.message.reply_text(f"✅ {tag} envoyé au channel !")
        except Exception as exc:
            logger.error("Failed to post to channel %s: %s", channel_id, exc)
            await update.message.reply_text(
                "⚠️ Contenu généré mais envoi au channel échoué. "
                "Vérifie que le bot est admin dans le channel."
            )
    else:
        await update.message.reply_text(
            "_(Configure `TELEGRAM_CHANNEL_ID` pour l'envoi automatique au channel.)_",
            parse_mode="Markdown",
        )


# ── Scheduled auto-post to channel ────────────────────────────────────────────
async def _scheduled_channel_post(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job: auto-post daily content to the Telegram channel."""
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()
    if not channel_id:
        return
    ai_client: anthropic.AsyncAnthropic = context.bot_data["ai_client"]
    today = datetime.datetime.now()
    is_ppv = today.weekday() in (4, 5)
    day_fr = {
        "Monday": "Lundi", "Tuesday": "Mardi", "Wednesday": "Mercredi",
        "Thursday": "Jeudi", "Friday": "Vendredi", "Saturday": "Samedi", "Sunday": "Dimanche",
    }.get(today.strftime("%A"), today.strftime("%A"))
    try:
        content = await maya_agent.run(is_ppv_day=is_ppv, day_name=day_fr, client=ai_client)
        await context.bot.send_message(chat_id=channel_id, text=content)
        logger.info("Auto-posted to channel via Maya (%s, ppv=%s)", day_fr, is_ppv)
    except Exception as exc:
        logger.error("Scheduled channel post failed: %s", exc)


# ── /faceswap ─────────────────────────────────────────────────────────────────
async def cmd_faceswap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["awaiting_faceswap"] = True
    await update.message.reply_text("📸 Envoie-moi une photo — je vais swapper le visage !")


async def handle_faceswap_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
                        "prompt": (
                            "Image 1 is the face reference. "
                            "Naturally replace the face in image 2 with image 1. "
                            "Same lighting and skin tone."
                        ),
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
            await update.message.reply_text("❌ La génération a échoué ou pris trop de temps.")
            return

        async with httpx.AsyncClient(timeout=60) as client:
            img_resp = await client.get(result_url)
        await update.message.reply_photo(photo=BytesIO(img_resp.content))

    except Exception as exc:
        logger.exception("Face swap error: %s", exc)
        await update.message.reply_text(f"❌ Erreur: {exc}")


# ── Global error handler ───────────────────────────────────────────────────────
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    if isinstance(err, NetworkError):
        logger.warning("Network error: %s", err)
    elif isinstance(err, TelegramError):
        logger.error("Telegram error: %s", err)
    else:
        logger.exception("Unhandled exception: %s", err)


# ── Startup hook ───────────────────────────────────────────────────────────────
async def post_init(app: Application) -> None:
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Bot commands registered with Telegram")


# ── Entry point ────────────────────────────────────────────────────────────────
def main() -> None:
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if not telegram_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    if not anthropic_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    ai_client = anthropic.AsyncAnthropic(api_key=anthropic_key)

    app = Application.builder().token(telegram_token).post_init(post_init).build()
    app.bot_data["ai_client"] = ai_client

    app.add_error_handler(error_handler)

    # Commands — named elite agents
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_start))
    app.add_handler(CommandHandler("standup",   cmd_standup))
    app.add_handler(CommandHandler("marcus",    cmd_marcus))
    app.add_handler(CommandHandler("sofia",     cmd_sofia))
    app.add_handler(CommandHandler("alex",      cmd_alex))
    app.add_handler(CommandHandler("maya",      cmd_maya))
    # Commands — legacy aliases
    app.add_handler(CommandHandler("strategie", cmd_strategie))
    app.add_handler(CommandHandler("poster",    cmd_poster))
    app.add_handler(CommandHandler("stats",     cmd_stats))
    app.add_handler(CommandHandler("channel",   cmd_channel))
    app.add_handler(CommandHandler("faceswap",  cmd_faceswap))

    # Photo handler for face swap
    app.add_handler(MessageHandler(filters.PHOTO, handle_faceswap_photo))

    # Text handler for /alex and /stats replies (must be last)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_replies))

    # Scheduled auto-post to Telegram channel (daily at 9am UTC)
    post_hour = int(os.environ.get("CHANNEL_POST_HOUR", "9"))
    post_minute = int(os.environ.get("CHANNEL_POST_MINUTE", "0"))
    app.job_queue.run_daily(
        _scheduled_channel_post,
        time=datetime.time(hour=post_hour, minute=post_minute, tzinfo=datetime.timezone.utc),
        name="daily_channel_post",
    )
    logger.info(
        "Scheduled daily channel post at %02d:%02d UTC", post_hour, post_minute
    )

    logger.info("Suukalia Team Bot starting — polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
