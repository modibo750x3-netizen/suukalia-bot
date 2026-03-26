#!/usr/bin/env python3
"""
Suukalia Team Bot — Elite OFM AI agent team + face swap.

Named agents (Phase 5):
  /marcus — Marcus, Stratège OFM Senior (stratégie semaine)
  /sofia — Sofia, Directrice Contenu & Copywriting [ig|twitter|threads|ppv]
  /alex — Alex, Analyste Data & Performance [stats inline ou prompt]
  /maya — Maya, Manager Communauté & Conversion [ppv]

  /faceswap — Face swap via Higgsfield
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

import re
import tempfile
import subprocess

import pytz
import replicate
import tweepy
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

from agents import analyste_agent, channel_agent, poster_agent, strategie_agent
from agents import marcus_agent, sofia_agent, alex_agent, maya_agent
from agents import instagram_scraper, browser_scraper

# ── Bootstrap ────────────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Timezone ────────────────────────────────────────────────────────────────────
CT = pytz.timezone("America/Chicago")  # Houston / Central Time
TWEET_HOURS_CT = [8, 12, 17, 21]       # 8h, 12h, 17h, 21h CT

MAX_MSG_LEN = 4096

# ── Keyboard ─────────────────────────────────────────────────────────────────────
MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["/standup 🗓️"],
        ["/marcus 🎯 Stratège OFM", "/sofia ✨ Contenu"],
        ["/alex 📊 Data & Stats", "/maya 💫 Channel PPV"],
    ],
    resize_keyboard=True,
    input_field_placeholder="Choisis un agent…",
)

# ── Bot commands ─────────────────────────────────────────────────────────────────
BOT_COMMANDS = [
    BotCommand("standup", "Réunion équipe du jour — tous les agents se briefent"),
    BotCommand("marcus", "Marcus — Stratège OFM Senior (stratégie semaine)"),
    BotCommand("sofia", "Sofia — Contenu [ig|ig_main|ig_nurse|collab|twitter|threads|ppv]"),
    BotCommand("alex", "Alex — Analyse métriques data & performance"),
    BotCommand("maya", "Maya — Post channel Telegram [ppv] (1300 abonnés)"),
    BotCommand("lipsync", "Lip-sync MuseTalk — corriger les lèvres d'une vidéo"),
]

# ── Higgsfield ───────────────────────────────────────────────────────────────────
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
        return {
            "id": data.get("id", image_id),
            "url": data.get("url", ""),
            "type": "media_input",
        }


async def _higgsfield_poll(job_id: str, max_wait: int = 180, interval: int = 5) -> str | None:
    """Poll Higgsfield job until completed. Returns image URL or None."""
    jwt = os.environ.get("HIGGSFIELD_JWT", "").strip()
    headers = {"Authorization": f"Bearer {jwt}"}
    deadline = asyncio.get_event_loop().time() + max_wait
    async with httpx.AsyncClient(timeout=30) as client:
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(interval)
            try:
                resp = await client.get(
                    f"{HIGGSFIELD_BASE}/jobs/{job_id}", headers=headers
                )
                data = resp.json()
                status = data.get("status", "")
                if status == "completed":
                    return data.get("results", {}).get("raw", {}).get("url")
                elif status in ("failed", "nsfw", "error"):
                    return None
            except Exception:
                pass
    return None

# ── Helpers ──────────────────────────────────────────────────────────────────────


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

# ── Twitter / X — Auto-scheduling via Tweepy ────────────────────────────────────


def _get_twitter_client_40k() -> tweepy.Client:
    """Client Tweepy pour le compte @suukalia 40k."""
    return tweepy.Client(
        consumer_key=os.environ["TWITTER_API_KEY"],
        consumer_secret=os.environ["TWITTER_API_SECRET"],
        access_token=os.environ["TWITTER_ACCESS_TOKEN"],
        access_token_secret=os.environ["TWITTER_ACCESS_TOKEN_SECRET"],
    )


def _parse_40k_tweets(content: str) -> list[str]:
    """Extraire les tweets 40k (lignes 🐦 N. ...) du contenu généré par Sofia."""
    tweets = []
    for line in content.split("\n"):
        m = re.match(r"^🐦\s*\d+\.\s*(.+)", line.strip())
        if m:
            tweet = m.group(1).strip()
            if len(tweet) <= 280:
                tweets.append(tweet)
    return tweets


def _next_ct_posting_times(hours: list[int]) -> list[datetime.datetime]:
    """Calcule les prochains créneaux CT pour chaque heure (saute si déjà passé aujourd'hui)."""
    now_ct = datetime.datetime.now(CT)
    times = []
    for h in hours:
        t = now_ct.replace(hour=h, minute=0, second=0, microsecond=0)
        if t <= now_ct:
            t += datetime.timedelta(days=1)
        times.append(t)
    return times


async def _post_scheduled_tweet(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job déclenché par job_queue — poste un tweet sur le 40k."""
    data = context.job.data
    tweet_text: str = data["tweet"]
    chat_id: int = data["chat_id"]
    try:
        client = _get_twitter_client_40k()
        resp = client.create_tweet(text=tweet_text)
        tweet_id = resp.data["id"]
        tweet_url = f"https://x.com/suukalia/status/{tweet_id}"
        logger.info("Scheduled tweet posted: %s", tweet_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ Tweet posté sur @suukalia !\n{tweet_url}\n\n_{tweet_text[:80]}..._",
            parse_mode="Markdown",
        )
    except Exception as exc:
        logger.error("Scheduled tweet failed: %s", exc)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Échec du tweet programmé : {exc}",
        )


async def callback_schedule_tweets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback du bouton 'Programmer les tweets' — planifie les 4 tweets sur job_queue."""
    query = update.callback_query
    await query.answer()

    tweets = context.user_data.get("pending_40k_tweets", [])
    if not tweets:
        await query.edit_message_text("❌ Aucun tweet en attente. Régénère avec /sofia twitter.")
        return

    hours = TWEET_HOURS_CT[: len(tweets)]
    posting_times = _next_ct_posting_times(hours)
    chat_id = query.message.chat_id

    scheduled_lines = []
    for tweet, post_time in zip(tweets, posting_times):
        context.job_queue.run_once(
            _post_scheduled_tweet,
            when=post_time,
            data={"tweet": tweet, "chat_id": chat_id},
            name=f"tweet_40k_{post_time.strftime('%H%M')}",
        )
        local_str = post_time.strftime("%H:%M CT")
        scheduled_lines.append(f"🕐 {local_str} — {tweet[:60]}…")

    summary = "✅ *Tweets programmés sur @suukalia 40k !*\n\n" + "\n".join(scheduled_lines)
    await query.edit_message_text(summary, parse_mode="Markdown")
    context.user_data.pop("pending_40k_tweets", None)

# ── /start ───────────────────────────────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "✨ *Suukalia Elite Team Bot* ✨\n\n"
        "🗓️ /standup — réunion équipe du jour (tous les agents)\n\n"
        "🎯 /marcus — stratégie semaine OFM Senior\n"
        "✨ /sofia — contenu [ig|ig_main|ig_nurse|collab|twitter|threads|ppv]\n"
        "📊 /alex — analyse métriques & data\n"
        "💫 /maya — post channel Telegram (1300 abonnés)\n"
        "🎙️ /lipsync — corriger les lèvres d'une vidéo (MuseTalk)\n\n"
        "Utilise les boutons ci-dessous 👇",
        reply_markup=MENU_KEYBOARD,
        parse_mode="Markdown",
    )

# ── /standup — Daily team briefing ───────────────────────────────────────────────


async def cmd_standup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Call all 4 agents in parallel for a daily briefing."""
    await update.message.reply_chat_action(ChatAction.TYPING)
    await update.message.reply_text(
        "🗓️ Réunion en cours… Marcus, Sofia, Alex et Maya se briefent (20-30 sec)"
    )

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
        "🗓️ STANDUP SUUKALIA TEAM\n"
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

# ── /spy — Instagram account spy ─────────────────────────────────────────────────


_DEFAULT_SPY_TARGET = "lalucigmzz"


async def cmd_spy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /spy @lalucigmzz — scrape public IG profile, then Marcus analyzes it.
    /spy — defaults to @lalucigmzz (main inspiration account).
    """
    raw = " ".join(context.args).strip() if context.args else ""
    username = instagram_scraper.extract_username(raw) if raw else _DEFAULT_SPY_TARGET

    await update.message.reply_chat_action(ChatAction.TYPING)
    await update.message.reply_text(
        f"🕵️ Espionnage de @{username} en cours… (30-60 sec)\n"
        "Scraping Instagram → Analyse Marcus"
    )

    # 1. Scrape Instagram
    data = await instagram_scraper.scrape(username, max_posts=15)
    analysis_text = instagram_scraper.format_for_marcus(data)

    # 2. Show raw data to user
    await send_chunks(update, analysis_text)

    # 3. Marcus strategy analysis
    await update.message.reply_chat_action(ChatAction.TYPING)
    await update.message.reply_text("🎯 Marcus analyse les données…")
    await _safe_run(update, marcus_agent.run_spy(username, analysis_text, _ai(context)))

# ── /analyse & /inspire — Browser visual scrape + Marcus Vision ──────────────────


async def _run_visual_scrape(
    update: Update, context: ContextTypes.DEFAULT_TYPE, inspire: bool
) -> None:
    raw = " ".join(context.args).strip() if context.args else ""
    username = (
        browser_scraper.extract_username_from_raw(raw) if raw else "lalucigmzz"
    )
    mode_label = "inspiration visuelle" if inspire else "analyse visuelle"

    await update.message.reply_chat_action(ChatAction.TYPING)
    await update.message.reply_text(
        f"📸 {mode_label.capitalize()} de @{username} en cours… (30-60 sec)\n"
        "Chromium → screenshots → analyse Marcus"
    )

    # 1. Browser scrape
    data = await browser_scraper.scrape_visual(username, max_posts=10)
    text_summary = browser_scraper.format_extracted(data)
    screenshots = data.get("screenshots", [])

    # 2. Show summary + login wall warning if needed
    await send_chunks(update, text_summary)

    if data.get("login_wall") and not os.environ.get("IG_SESSION_ID"):
        await update.message.reply_text(
            "ℹ️ Pour l'accès complet, configure IG_SESSION_ID dans les variables Railway.\n"
            "Marcus analyse quand même les screenshots disponibles."
        )

    if not screenshots:
        await update.message.reply_text(
            "❌ Aucun screenshot disponible. Vérifie que Playwright est installé."
        )
        return

    # 3. Marcus visual analysis
    await update.message.reply_chat_action(ChatAction.TYPING)
    await update.message.reply_text("🎯 Marcus analyse les visuels…")
    await _safe_run(
        update,
        marcus_agent.run_analyse(
            username, screenshots, text_summary, _ai(context), inspire_mode=inspire
        ),
    )


async def cmd_analyse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_visual_scrape(update, context, inspire=False)


async def cmd_inspire(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_visual_scrape(update, context, inspire=True)

# ── MARCUS — Stratège OFM Senior ─────────────────────────────────────────────────


async def cmd_marcus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_chat_action(ChatAction.TYPING)
    await update.message.reply_text("🎯 Marcus analyse la situation… (15-20 sec)")
    task = " ".join(context.args) if context.args else ""
    await _safe_run(update, marcus_agent.run(task, _ai(context)))

# ── SOFIA — Directrice Contenu & Copywriting ─────────────────────────────────────


async def cmd_sofia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_chat_action(ChatAction.TYPING)
    platform = (context.args[0] if context.args else "all").lower()
    valid = {"ig", "ig_main", "ig_nurse", "collab", "twitter", "threads", "ppv", "all"}

    if platform not in valid:
        await update.message.reply_text(
            "Usage: /sofia [ig|ig_main|ig_nurse|collab|twitter|threads|ppv]\n\n"
            "• ig — 2 captions par compte (principal 73k + secondaire 13k)\n"
            "• ig_main — 3 captions IG Principal 73k (lifestyle/Moon)\n"
            "• ig_nurse — 3 captions IG Secondaire 13k (nurse)\n"
            "• collab — même photo, 2 captions différentes\n"
            "• twitter / threads / ppv / all"
        )
        return

    content = await sofia_agent.run(platform, _ai(context))
    await send_chunks(update, content)

    if platform in ("twitter", "all"):
        tweets_40k = _parse_40k_tweets(content)
        if tweets_40k:
            context.user_data["pending_40k_tweets"] = tweets_40k
            hours_str = " · ".join(f"{h}h" for h in TWEET_HOURS_CT[: len(tweets_40k)])
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            f"🐦 Programmer {len(tweets_40k)} tweets — {hours_str} CT",
                            callback_data="schedule_tweets_40k",
                        )
                    ]
                ]
            )
            await update.message.reply_text(
                f"_{len(tweets_40k)} tweets prêts. Seront postés à {hours_str} (Houston CT)_",
                reply_markup=keyboard,
                parse_mode="Markdown",
            )

# ── ALEX — Analyste Data & Performance ───────────────────────────────────────────


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

# ── MAYA — Manager Communauté & Conversion ───────────────────────────────────────


async def cmd_maya(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_chat_action(ChatAction.TYPING)

    force_ppv = bool(context.args and context.args[0].lower() == "ppv")
    today = datetime.datetime.now()
    is_ppv = today.weekday() in (4, 5)  # Friday=4, Saturday=5

    day_fr = {
        "Monday": "Lundi",
        "Tuesday": "Mardi",
        "Wednesday": "Mercredi",
        "Thursday": "Jeudi",
        "Friday": "Vendredi",
        "Saturday": "Samedi",
        "Sunday": "Dimanche",
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

# ── AGENT 1 — STRATÈGE ───────────────────────────────────────────────────────────


async def cmd_strategie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_chat_action(ChatAction.TYPING)
    await update.message.reply_text(
        "📊 Analyse en cours… (peut prendre 15-20 sec)"
    )
    await _safe_run(update, strategie_agent.run(_ai(context)))

# ── AGENT 2 — POSTER ─────────────────────────────────────────────────────────────


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

# ── AGENT 3 — ANALYSTE ───────────────────────────────────────────────────────────


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
    await _safe_run(update, analyste_agent.run(update.message.text, _ai(context)))


async def handle_text_replies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route text replies to the appropriate waiting agent (/alex or /stats)."""
    if context.user_data.get("awaiting_alex"):
        await handle_alex_reply(update, context)
    elif context.user_data.get("awaiting_stats"):
        await handle_stats_reply(update, context)

# ── AGENT 4 — CHANNEL MANAGER ────────────────────────────────────────────────────


async def cmd_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Generate channel content and optionally post it to the Telegram channel.
    Detects day of week automatically (PPV on Friday & Saturday).
    """
    await update.message.reply_chat_action(ChatAction.TYPING)

    today = datetime.datetime.now()
    is_ppv = today.weekday() in (4, 5)  # Friday=4, Saturday=5

    day_fr = {
        "Monday": "Lundi",
        "Tuesday": "Mardi",
        "Wednesday": "Mercredi",
        "Thursday": "Jeudi",
        "Friday": "Vendredi",
        "Saturday": "Samedi",
        "Sunday": "Dimanche",
    }.get(today.strftime("%A"), today.strftime("%A"))

    try:
        content = await channel_agent.run(
            is_ppv_day=is_ppv, day_name=day_fr, client=_ai(context)
        )
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

# ── Scheduled auto-post to channel ───────────────────────────────────────────────


async def _scheduled_channel_post(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job: auto-post daily content to the Telegram channel."""
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()
    if not channel_id:
        return

    ai_client: anthropic.AsyncAnthropic = context.bot_data["ai_client"]

    today = datetime.datetime.now()
    is_ppv = today.weekday() in (4, 5)

    day_fr = {
        "Monday": "Lundi",
        "Tuesday": "Mardi",
        "Wednesday": "Mercredi",
        "Thursday": "Jeudi",
        "Friday": "Vendredi",
        "Saturday": "Samedi",
        "Sunday": "Dimanche",
    }.get(today.strftime("%A"), today.strftime("%A"))

    try:
        content = await maya_agent.run(
            is_ppv_day=is_ppv, day_name=day_fr, client=ai_client
        )
        await context.bot.send_message(chat_id=channel_id, text=content)
        logger.info("Auto-posted to channel via Maya (%s, ppv=%s)", day_fr, is_ppv)
    except Exception as exc:
        logger.error("Scheduled channel post failed: %s", exc)

# ── /faceswap ───────────────────────────────────────────────────────────────────


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

        ref_id = os.environ.get(
            "HIGGSFIELD_REF_ID", "9c30dcd3-1519-40ba-a6a9-79316070fa65"
        )
        ref_url = os.environ.get("REFERENCE_IMAGE_URL", "")
        target_image = {"id": ref_id, "url": ref_url, "type": "media_input"}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{HIGGSFIELD_BASE}/jobs/nano-banana",
                headers={
                    "Authorization": f"Bearer {jwt}",
                    "Content-Type": "application/json",
                },
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
            await update.message.reply_text(
                "❌ La génération a échoué ou pris trop de temps."
            )
            return

        async with httpx.AsyncClient(timeout=60) as client:
            img_resp = await client.get(result_url)
            await update.message.reply_photo(photo=BytesIO(img_resp.content))

    except Exception as exc:
        logger.exception("Face swap error: %s", exc)
        await update.message.reply_text(f"❌ Erreur: {exc}")

# ── /lipsync — MuseTalk lip-sync via Replicate ──────────────────────────────


async def cmd_lipsync(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start lip-sync flow. Optional: /lipsync 5 to shift mouth openness."""
    bbox_shift = 0
    if context.args:
        try:
            bbox_shift = int(context.args[0])
        except ValueError:
            pass
    context.user_data["awaiting_lipsync"] = True
    context.user_data["lipsync_bbox_shift"] = bbox_shift
    shift_info = f" (bbox_shift={bbox_shift})" if bbox_shift else ""
    await update.message.reply_text(
        f"🎙️ Lip-sync MuseTalk{shift_info}\n\n"
        "Envoie-moi ta vidéo Kling — je vais corriger les lèvres !\n\n"
        "_(Astuce: /lipsync 5 → plus d'ouverture bouche, /lipsync -5 → moins)_",
        parse_mode="Markdown",
    )


async def handle_lipsync_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process video for lip-sync when awaiting."""
    if not context.user_data.get("awaiting_lipsync"):
        return

    context.user_data["awaiting_lipsync"] = False
    bbox_shift = context.user_data.pop("lipsync_bbox_shift", 0)

    replicate_token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
    if not replicate_token:
        await update.message.reply_text("❌ REPLICATE_API_TOKEN non configuré.")
        return

    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("❌ Envoie une vidéo (pas une photo).")
        context.user_data["awaiting_lipsync"] = True
        return

    await update.message.reply_chat_action(ChatAction.UPLOAD_VIDEO)
    await update.message.reply_text(
        "⏳ Lip-sync en cours… MuseTalk traite ta vidéo (~5-8 min)\n"
        "Je t'envoie le résultat dès que c'est prêt."
    )

    try:
        # 1. Download video from Telegram
        tg_file = await context.bot.get_file(video.file_id)
        tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        video_url = f"https://api.telegram.org/file/bot{tg_token}/{tg_file.file_path}"

        async with httpx.AsyncClient(timeout=60) as dl:
            vid_resp = await dl.get(video_url)
            video_bytes = vid_resp.content

        # 2. Extract audio from video using ffmpeg
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf:
            vf.write(video_bytes)
            video_path = vf.name

        audio_path = video_path.replace(".mp4", ".wav")
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
             "-ar", "16000", "-ac", "1", audio_path],
            capture_output=True, timeout=60,
        )
        if proc.returncode != 0:
            await update.message.reply_text("❌ Impossible d'extraire l'audio de la vidéo.")
            return

        # 3. Send to MuseTalk on Replicate
        client = replicate.Client(api_token=replicate_token)
        with open(video_path, "rb") as vf, open(audio_path, "rb") as af:
            output = client.run(
                "douwantech/musetalk",
                input={
                    "video_input": vf,
                    "audio_input": af,
                    "bbox_shift": bbox_shift,
                    "fps": 25,
                },
            )

        # 4. Download result and send back
        result_url = str(output)
        async with httpx.AsyncClient(timeout=120) as dl:
            result_resp = await dl.get(result_url)
            result_bytes = result_resp.content

        await update.message.reply_video(
            video=BytesIO(result_bytes),
            caption="✅ Lip-sync terminé ! Lèvres corrigées par MuseTalk.",
        )

    except Exception as exc:
        logger.exception("Lipsync error: %s", exc)
        await update.message.reply_text(f"❌ Erreur lip-sync: {exc}")
    finally:
        # Cleanup temp files
        for p in [video_path, audio_path]:
            try:
                os.unlink(p)
            except OSError:
                pass


# ── Global error handler ─────────────────────────────────────────────────────────


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    if isinstance(err, NetworkError):
        logger.warning("Network error: %s", err)
    elif isinstance(err, TelegramError):
        logger.error("Telegram error: %s", err)
    else:
        logger.exception("Unhandled exception: %s", err)

# ── Startup hook ─────────────────────────────────────────────────────────────────


async def post_init(app: Application) -> None:
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Bot commands registered with Telegram")

# ── Entry point ──────────────────────────────────────────────────────────────────


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
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("standup", cmd_standup))
    app.add_handler(CommandHandler("spy", cmd_spy))
    app.add_handler(CommandHandler("analyse", cmd_analyse))
    app.add_handler(CommandHandler("inspire", cmd_inspire))
    app.add_handler(CommandHandler("marcus", cmd_marcus))
    app.add_handler(CommandHandler("sofia", cmd_sofia))
    app.add_handler(CommandHandler("alex", cmd_alex))
    app.add_handler(CommandHandler("maya", cmd_maya))

    # Commands — legacy aliases
    app.add_handler(CommandHandler("strategie", cmd_strategie))
    app.add_handler(CommandHandler("poster", cmd_poster))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("channel", cmd_channel))
    app.add_handler(CommandHandler("faceswap", cmd_faceswap))
    app.add_handler(CommandHandler("lipsync", cmd_lipsync))

    # Photo handler for face swap
    app.add_handler(MessageHandler(filters.PHOTO, handle_faceswap_photo))

    # Video handler for lip-sync
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_lipsync_video))

    # Callback handler for tweet scheduling
    app.add_handler(
        CallbackQueryHandler(callback_schedule_tweets, pattern="^schedule_tweets_40k$")
    )

    # Text handler for /alex and /stats replies (must be last)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_replies))

    # Scheduled auto-post to Telegram channel (daily at 9am UTC)
    post_hour = int(os.environ.get("CHANNEL_POST_HOUR", "9"))
    post_minute = int(os.environ.get("CHANNEL_POST_MINUTE", "0"))
    app.job_queue.run_daily(
        _scheduled_channel_post,
        time=datetime.time(
            hour=post_hour, minute=post_minute, tzinfo=datetime.timezone.utc
        ),
        name="daily_channel_post",
    )
    logger.info("Scheduled daily channel post at %02d:%02d UTC", post_hour, post_minute)

    logger.info("Suukalia Team Bot starting — polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
