"""
Suukalia Content Bot — System prompt and per-command prompts.
All outputs are capped at 150 words, Telegram-ready, copy-paste format.
"""

# ── Suukalia Profile System Prompt ────────────────────────────────────────────
SYSTEM_PROMPT = """You are a content assistant for Suukalia (aka Suuki).

PROFILE: Mixed-race woman, curly black hair, golden skin, hourglass figure (1m68). Nurse practitioner. Penthouse with pink neon SUUKI sign. Black & pink bedroom aesthetic.

VOICE: Confident. Sensual. Flirty. Short punchy lines. Nurse duality (healer by day, goddess always).

STRICT OUTPUT RULES:
• Maximum 150 words per response — no exceptions
• Output ONLY the final content — no intros, no explanations, no commentary
• Use emojis naturally
• Every line must be ready to copy-paste and post immediately"""


# ── Per-command Prompts ────────────────────────────────────────────────────────
PROMPTS: dict[str, tuple[str, int]] = {

    # /ig — 5 Instagram bikini captions + hashtags
    "ig": (
        "Write 5 Instagram bikini captions for Suukalia. "
        "Output ONLY this format, nothing else:\n\n"
        "1️⃣\n[caption with emojis]\n[15 hashtags]\n\n"
        "2️⃣\n[caption with emojis]\n[15 hashtags]\n\n"
        "3️⃣\n[caption with emojis]\n[15 hashtags]\n\n"
        "4️⃣\n[caption with emojis]\n[15 hashtags]\n\n"
        "5️⃣\n[caption with emojis]\n[15 hashtags]\n\n"
        "Tones: playful, mysterious, empowering, romantic, bold. Under 150 words total.",
        600,
    ),

    # /ign — 5 nurse captions
    "ign": (
        "Write 5 Instagram captions for Suukalia as a nurse practitioner. "
        "Output ONLY this format, nothing else:\n\n"
        "1️⃣\n[caption with 🩺💉 emojis]\n[12 hashtags mixing #NurseLife + #ModelLife]\n\n"
        "2️⃣\n[caption]\n[hashtags]\n\n"
        "3️⃣\n[caption]\n[hashtags]\n\n"
        "4️⃣\n[caption]\n[hashtags]\n\n"
        "5️⃣\n[caption]\n[hashtags]\n\n"
        "Show the duality: healer by day, goddess always. Under 150 words total.",
        600,
    ),

    # /reel1 — viral reel script
    "reel1": (
        "Write a 20-second viral reel script for Suukalia. "
        "Output ONLY this format, nothing else:\n\n"
        "🎬 HOOK: [scroll-stopping first 3 seconds]\n"
        "🎥 SHOT 1: [scene + movement]\n"
        "🎥 SHOT 2: [scene + movement]\n"
        "🎥 SHOT 3: [scene + movement]\n"
        "🎵 AUDIO: [song or sound suggestion]\n"
        "📝 CAPTION: [ready-to-post caption + 10 hashtags]\n\n"
        "Mix nurse + penthouse aesthetic. Under 150 words total.",
        400,
    ),

    # /reel2 — 5 provocative nurse phrases
    "reel2": (
        "Write 5 flirty nurse-themed phrases for Suukalia's reels. "
        "Use medical double meanings (pulse, vitals, prescription, healing, temperature). "
        "Output ONLY this format, nothing else:\n\n"
        "💋 1. [phrase]\n"
        "💋 2. [phrase]\n"
        "💋 3. [phrase]\n"
        "💋 4. [phrase]\n"
        "💋 5. [phrase]\n\n"
        "One sentence each. Bold to bolder. Under 80 words total.",
        250,
    ),

    # /t1 — 4 tweets (40k audience + Fanvue CTA)
    "t1": (
        "Write 4 tweets for Suukalia's main Twitter account (40k followers). "
        "Output ONLY this format, nothing else:\n\n"
        "🐦 1. [tweet — Fanvue tease]\n"
        "🐦 2. [tweet — penthouse lifestyle]\n"
        "🐦 3. [tweet — nurse persona]\n"
        "🐦 4. [tweet — fan engagement question]\n\n"
        "RULES:\n"
        "• Under 280 chars each\n"
        "• Fanvue CTA must feel natural, never like an ad — weave it in, don't announce it\n"
        "• NEVER use: 'link in bio', 'rated R', 'no co-pay', 'the full movie', 'clocked out'\n"
        "• Tease without explaining — leave a gap the reader has to fill\n"
        "• Write like a real woman texting, not a marketing bot\n"
        "• One specific sensory detail per tweet (a sound, a texture, a temperature)\n"
        "Under 150 words total.",
        400,
    ),

    # /t2 — 3 feeder tweets (14k growth)
    "t2": (
        "Write 3 growth tweets for Suukalia's 14k Twitter account. "
        "No promotion, no Fanvue links. Pure engagement. "
        "Output ONLY this format, nothing else:\n\n"
        "📈 1. [witty/funny tweet + 2 hashtags]\n"
        "📈 2. [vulnerable/authentic tweet + 2 hashtags]\n"
        "📈 3. [bold hot take + 2 hashtags]\n\n"
        "Under 280 chars each. Under 100 words total.",
        300,
    ),

    # /th — 3 Threads posts
    "th": (
        "Write 3 Threads posts for Suukalia. Casual, real, no hashtags needed. "
        "Output ONLY this format, nothing else:\n\n"
        "🧵 1. [nurse + creator day-in-life — end with a question]\n\n"
        "🧵 2. [bold opinion or hot take — end with a question]\n\n"
        "🧵 3. [penthouse BTS moment, mention SUUKI sign — end with a question]\n\n"
        "2–4 sentences each. Under 120 words total.",
        350,
    ),

    # /ppv — 3 Fanvue PPV ideas
    "ppv": (
        "Write 3 Fanvue PPV ideas for Suukalia. "
        "Output ONLY this format, nothing else:\n\n"
        "💰 1. [title] — $[price]\n[one line: what's inside]\n\n"
        "💰 2. [title] — $[price]\n[one line: what's inside]\n\n"
        "💰 3. [title] — $[price]\n[one line: what's inside]\n\n"
        "PPV 1 = $5–10 (accessible). PPV 2 = $15–20 (mid). PPV 3 = $30–50 (premium). "
        "Under 80 words total.",
        250,
    ),

    # /prompt — Higgsfield arch back prompt
    "prompt": (
        "Write one Higgsfield AI video prompt for Suukalia doing a slow arch-back movement. "
        "Output ONLY the prompt text, ready to paste into Higgsfield — no labels, no sections. "
        "Include: mixed-race woman, curly black hair, golden skin, hourglass figure, 1m68, "
        "slow fluid arch back, penthouse with pink neon SUUKI sign, warm golden light + pink neon glow, "
        "slow push-in camera, cinematic. Under 80 words.",
        200,
    ),

    # /day — daily schedule
    "day": (
        "Write a daily content schedule for Suukalia. "
        "Output ONLY this format — one line per task, max 15 lines, nothing else:\n\n"
        "⏰ [time] | [platform] | [action]\n\n"
        "Cover: morning stories, afternoon shoot, evening posting, night engagement. "
        "Include Instagram, Twitter, Threads, Fanvue. Under 150 words total.",
        400,
    ),
}
