# Suukalia Content Bot 🌸

A Telegram bot that generates AI-powered social media content for **Suukalia** — nurse practitioner, content creator, and luxury lifestyle personality.

Built with **python-telegram-bot** + **Anthropic Claude API** (claude-opus-4-6).

---

## Commands

| Command | Output |
|---------|--------|
| `/ig` | 5 Instagram bikini captions + hashtags |
| `/ign` | 5 nurse practitioner captions |
| `/reel1` | Viral reel script (15–30 sec, full breakdown) |
| `/reel2` | 5 provocative nurse-themed phrases |
| `/t1` | 4 tweets for 40k audience + Fanvue CTA |
| `/t2` | 3 feeder tweets for 14k growth account |
| `/th` | 3 Threads posts |
| `/ppv` | 3 Fanvue PPV content ideas |
| `/prompt` | Higgsfield AI arch-back video prompt |
| `/day` | Full daily content plan |

---

## Project Structure

```
suukalia-bot/
├── bot.py            # Main entry point — Telegram handlers + Claude calls
├── prompts.py        # System prompt + all per-command prompts
├── requirements.txt  # Python dependencies
├── Procfile          # Railway / Heroku process declaration
├── runtime.txt       # Python version pin
├── .env.example      # Environment variable template
├── .gitignore
└── README.md
```

---

## Local Development

### 1. Prerequisites

- Python 3.12+
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- An Anthropic API key (from [console.anthropic.com](https://console.anthropic.com))

### 2. Clone & install

```bash
git clone <your-repo-url>
cd suukalia-bot
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your keys:
#   TELEGRAM_BOT_TOKEN=...
#   ANTHROPIC_API_KEY=...
```

### 4. Run locally

```bash
python bot.py
```

Open Telegram, find your bot, and send `/start`.

---

## Deploy to Railway.app

### Step 1 — Create a Railway account

Go to [railway.app](https://railway.app) and sign up (free tier available).

### Step 2 — Create a new project

1. Click **New Project**
2. Select **Deploy from GitHub repo** (connect your GitHub account if needed)
3. Select this repository

### Step 3 — Set environment variables

In your Railway project dashboard:

1. Click on your service → **Variables** tab
2. Add the following variables:

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | Your token from @BotFather |
| `ANTHROPIC_API_KEY` | Your key from console.anthropic.com |

> ⚠️ Never put real keys in the code or `.env` file committed to git.

### Step 4 — Configure the service type

The bot runs as a **worker** (no HTTP server needed):

1. Go to **Settings** tab of your service
2. Under **Deploy**, confirm the start command is `python bot.py`
   - Or set it manually if needed

Railway auto-detects the `Procfile` with `worker: python bot.py`.

### Step 5 — Deploy

1. Push your code to GitHub — Railway auto-deploys on every push
2. Or click **Deploy** in the dashboard

### Step 6 — Verify

In the Railway **Logs** tab you should see:

```
Suukalia Bot is starting — polling for updates...
```

Go to Telegram, message your bot `/start` — it's live! 🎉

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | From [@BotFather](https://t.me/BotFather) |
| `ANTHROPIC_API_KEY` | ✅ | From [console.anthropic.com](https://console.anthropic.com) |

---

## Getting a Telegram Bot Token

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Follow the prompts (choose a name and username)
4. Copy the token BotFather gives you → paste into Railway as `TELEGRAM_BOT_TOKEN`

---

## Tech Stack

| Component | Library |
|-----------|---------|
| Telegram integration | `python-telegram-bot==21.6` |
| AI content generation | `anthropic>=0.50.0` (Claude Opus 4.6) |
| Environment management | `python-dotenv` |
| Deployment | Railway.app (worker dyno) |

---

## Notes

- The bot uses **Claude Opus 4.6 with adaptive thinking** for highest quality content.
- Responses are automatically split into multiple messages if they exceed Telegram's 4000-character limit.
- A `ChatAction.TYPING` indicator is shown while content generates.
- The bot uses **long-polling** (no webhook required) — ideal for Railway worker dynos.
