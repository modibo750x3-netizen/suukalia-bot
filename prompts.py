"""
Suukalia Content Bot — System prompt and per-command prompts.
"""

# ── Suukalia Profile System Prompt ────────────────────────────────────────────
SYSTEM_PROMPT = """You are a creative content assistant for Suukalia, a professional content
creator and social media personality. Here is her full profile:

IDENTITY:
• Mixed-race woman with curly black hair, golden skin, and an hourglass figure (1m68)
• Certified nurse practitioner — her professional career and a core brand element
• Lives in a luxury penthouse featuring a pink neon "SUUKI" sign
• Signature aesthetic: black and pink bedroom, neon accents, warm golden lighting
• Nickname: "Suuki"

PLATFORMS & AUDIENCE:
• Instagram: bikini, lifestyle, nurse-aesthetic content
• Twitter/X: main account (40k+) + growth account (14k)
• Threads: casual, conversational, authentic content
• Fanvue: exclusive premium content and PPV drops

BRAND VOICE:
• Confident, sensual, and unapologetically self-assured
• Playfully mysterious and alluring
• The nurse duality: professional healer by day, goddess always
• Luxurious yet relatable — penthouse life but still real
• Short, punchy, memorable lines that stop the scroll

Always generate content that is:
✓ On-brand and platform-optimized
✓ Ready to copy-paste and post
✓ Bold enough to drive engagement
✓ Matching her unique nurse-meets-luxury aesthetic"""


# ── Per-command Prompts ────────────────────────────────────────────────────────
PROMPTS: dict[str, tuple[str, int]] = {

    # /ig — 5 Instagram bikini captions + hashtags
    "ig": (
        "Generate 5 Instagram captions for Suukalia's bikini photos.\n\n"
        "Requirements for each caption:\n"
        "• Confident, flirty, and elegant — matches her golden-skin, curves aesthetic\n"
        "• Expressive emojis woven naturally into the text\n"
        "• End with 15–20 targeted hashtags on a separate line\n"
        "• Variety of tones: one PLAYFUL, one MYSTERIOUS, one EMPOWERING, one ROMANTIC, one BOLD\n"
        "• Subtly reference golden skin, curves, beach/pool/sun energy\n\n"
        "Format:\n"
        "📸 Caption 1 — [PLAYFUL]\n"
        "[caption text]\n"
        "[hashtags]\n\n"
        "📸 Caption 2 — [MYSTERIOUS]\n"
        "... and so on for all 5.",
        2500,
    ),

    # /ign — 5 nurse captions
    "ign": (
        "Generate 5 Instagram captions for Suukalia in her nurse practitioner role.\n\n"
        "Requirements:\n"
        "• Blend professional healthcare identity with her confident model persona\n"
        "• Empowering, layered, and intriguing — celebrate her dual identity\n"
        "• Emojis: stethoscope 🩺, syringe 💉, heart 💙, star ⭐\n"
        "• 10–15 hashtags mixing #NursePractitioner #NurseLife + #ContentCreator #ModelLife\n"
        "• Tone spectrum: 1 empowering, 1 playful/ironic, 1 seductive, 1 motivational, 1 mysterious\n"
        "• Show the duality: healer by day, goddess always\n\n"
        "Format:\n"
        "👩‍⚕️ Caption 1 — [EMPOWERING]\n"
        "[caption]\n"
        "[hashtags]\n\n"
        "Repeat for all 5 captions.",
        2500,
    ),

    # /reel1 — viral reel script
    "reel1": (
        "Write a complete viral Instagram/TikTok reel script for Suukalia (15–30 seconds).\n\n"
        "Structure it with these clearly labeled sections:\n\n"
        "🎬 HOOK (0–3 sec)\n"
        "Describe the scroll-stopping opening shot or action.\n\n"
        "🎥 SCENE BREAKDOWN\n"
        "Shot-by-shot guide: setting, outfit, movement, facial expression, camera angle.\n"
        "Reference her penthouse, pink neon SUUKI sign, or nurse elements.\n\n"
        "🎙️ VOICEOVER / TEXT OVERLAYS\n"
        "Exact words she says or text shown on screen.\n\n"
        "🎵 AUDIO SUGGESTION\n"
        "Trending sound, music vibe, or specific song recommendation.\n\n"
        "⏱️ TIMING\n"
        "Breakdown by seconds.\n\n"
        "📝 POST CAPTION + HASHTAGS\n"
        "Ready-to-post caption with 20 hashtags.\n\n"
        "Make it cinematic, aspirational, and highly shareable. "
        "Mix her nurse life aesthetic with her penthouse/model world.",
        3000,
    ),

    # /reel2 — 5 provocative nurse phrases
    "reel2": (
        "Create 5 provocative, clever nurse-themed phrases for Suukalia's content.\n\n"
        "Requirements:\n"
        "• Play on her nurse role with double meanings (medical → flirty)\n"
        "• Use medical vocabulary cleverly: healing, prescriptions, vitals, care, "
        "diagnosis, treatment, pulse, temperature, charts\n"
        "• Short and punchy — 1 to 2 sentences maximum\n"
        "• Works as: reel voiceover, story text overlay, or caption opener\n"
        "• Progress from suggestive (#1) to bold (#5)\n\n"
        "Format:\n"
        "💋 Phrase 1\n"
        "[the phrase]\n"
        "Use: [brief suggestion on how to use it]\n\n"
        "Repeat for all 5. Make them unforgettable.",
        1500,
    ),

    # /t1 — 4 tweets (40k audience + Fanvue CTA)
    "t1": (
        "Write 4 Twitter/X posts for Suukalia's main account (40k+ audience).\n\n"
        "Requirements:\n"
        "• Under 280 characters each (include character count)\n"
        "• Each tweet includes a CTA pointing to her Fanvue page\n"
        "• Brand voice: confident, flirty, mysterious\n"
        "• One tweet per theme:\n"
        "  Tweet 1: Teasing exclusive Fanvue content drop\n"
        "  Tweet 2: Penthouse / luxury lifestyle moment\n"
        "  Tweet 3: Nurse practitioner persona (clever or ironic)\n"
        "  Tweet 4: Fan engagement / reply-bait question\n"
        "• Include relevant emojis\n\n"
        "Format:\n"
        "🐦 Tweet 1 — [FANVUE TEASE]\n"
        "[tweet text]\n"
        "[X chars]\n\n"
        "Repeat for all 4.",
        1800,
    ),

    # /t2 — 3 feeder tweets (14k growth)
    "t2": (
        "Write 3 'feeder' tweets for Suukalia's growth account (14k followers).\n"
        "Goal: attract new followers — these are NOT promotional.\n\n"
        "Requirements:\n"
        "• Highly engaging, shareable, and relatable to a broad audience\n"
        "• Zero Fanvue links or direct selling\n"
        "• Formats:\n"
        "  Tweet 1: Witty / funny (broad appeal)\n"
        "  Tweet 2: Vulnerable / authentic moment\n"
        "  Tweet 3: Bold opinion or aspirational hot take\n"
        "• Include 2–3 discovery hashtags per tweet\n"
        "• Under 280 characters each\n\n"
        "Format:\n"
        "📈 Tweet 1 — [WITTY/FUNNY]\n"
        "[tweet text]\n"
        "Strategy note: [1-line explanation of why this works for growth]\n\n"
        "Repeat for all 3.",
        1500,
    ),

    # /th — 3 Threads posts
    "th": (
        "Write 3 Threads posts for Suukalia. Threads = casual, conversational, authentic.\n\n"
        "One post per theme:\n"
        "Post 1: A day-in-the-life as a nurse practitioner AND content creator\n"
        "Post 2: A bold opinion or hot take (lifestyle, relationships, or her industry)\n"
        "Post 3: Behind-the-scenes penthouse moment "
        "(mention the pink neon SUUKI sign or her black/pink bedroom)\n\n"
        "Requirements:\n"
        "• 60–150 words each\n"
        "• End each post with a question to spark replies\n"
        "• Show personality: humor, vulnerability, or unapologetic confidence\n"
        "• No hashtags required\n\n"
        "Format:\n"
        "🧵 Post 1 — DAY IN THE LIFE\n"
        "[post text]\n\n"
        "Repeat for all 3.",
        2000,
    ),

    # /ppv — 3 Fanvue PPV ideas
    "ppv": (
        "Create 3 Fanvue PPV (Pay-Per-View) content ideas for Suukalia.\n\n"
        "For each PPV, provide:\n"
        "📌 TITLE: catchy, intriguing name\n"
        "📝 DESCRIPTION: what the PPV includes (2–3 sentences, enough to excite)\n"
        "💰 PRICE: suggested price point ($5–$50)\n"
        "📣 TEASER CAPTION: 2–3 sentences to sell it on Twitter/Instagram Stories\n"
        "🎨 AESTHETIC: which visual theme to feature "
        "(nurse uniform, penthouse neon, bikini, black-pink bedroom)\n"
        "⏰ BEST DROP TIME: when to post and how to build hype\n\n"
        "Progress from accessible (PPV 1, $5–10) to mid-tier (PPV 2) to premium (PPV 3, $30–50).\n"
        "Make the titles and descriptions irresistible.",
        2500,
    ),

    # /prompt — Higgsfield arch back prompt
    "prompt": (
        "Write a detailed Higgsfield AI video generation prompt for Suukalia "
        "performing a slow, cinematic arch-back movement.\n\n"
        "Include all sections:\n\n"
        "👤 SUBJECT\n"
        "Describe in detail: mixed-race woman, curly black hair, golden warm skin, "
        "hourglass silhouette, 1m68 height. Be hyper-specific for AI accuracy.\n\n"
        "🎬 MOVEMENT DESCRIPTION\n"
        "Slow, fluid, deliberate arch back — describe the body motion, pace, and sensuality.\n\n"
        "📍 SETTING\n"
        "Choose the strongest option: penthouse with glowing pink neon SUUKI sign, "
        "black and pink bedroom, or luxury bathroom. Describe the environment in detail.\n\n"
        "💡 LIGHTING\n"
        "Warm golden-hour light + pink neon accent glow. Describe direction and softness.\n\n"
        "🎥 CAMERA MOVEMENT\n"
        "Specify: slow push-in, gentle orbit, or locked-off. Include focal length feel.\n\n"
        "👗 OUTFIT\n"
        "Specific clothing that complements the movement and setting.\n\n"
        "🌟 MOOD KEYWORDS\n"
        "6–8 cinematic atmosphere descriptors.\n\n"
        "⚙️ HIGGSFIELD TECHNICAL PARAMS\n"
        "Style tokens, motion intensity, any platform-specific syntax.\n\n"
        "Output the final prompt as one clean, ready-to-paste block at the end.",
        2000,
    ),

    # /day — full daily content plan
    "day": (
        "Create a complete, actionable daily content strategy for Suukalia.\n\n"
        "Structure:\n\n"
        "🌅 MORNING BLOCK (6:00–12:00)\n"
        "• Wake-up story ideas\n"
        "• Morning routine content (nurse or lifestyle)\n"
        "• Engagement tasks (reply to comments/DMs, like posts)\n\n"
        "☀️ AFTERNOON BLOCK (12:00–17:00)\n"
        "• Main content creation window\n"
        "• Photo/video shoot concepts + locations in her space\n"
        "• Specific posts to create for each platform\n\n"
        "🌆 EVENING BLOCK (17:00–22:00)\n"
        "• Optimal posting times per platform with exact schedule\n"
        "• PPV drop or teaser strategy\n"
        "• Fan interaction tactics\n\n"
        "🌙 NIGHT BLOCK (22:00–02:00)\n"
        "• Late-night content ideas (her most engaging time slot)\n"
        "• Final story/post of the day\n\n"
        "📋 DAILY CHECKLIST\n"
        "[ ] Instagram feed post\n"
        "[ ] Instagram stories (5–7 frames)\n"
        "[ ] Twitter/X posts (3–5)\n"
        "[ ] Threads post (1–2)\n"
        "[ ] Fanvue upload\n"
        "[ ] PPV teaser\n"
        "[ ] Engagement (30 min minimum)\n\n"
        "🎯 CONTENT PILLARS FOR TODAY\n"
        "Assign specific themes and aesthetics to each block.\n\n"
        "💡 3 PRO TIPS\n"
        "Specific, tactical advice tailored to her brand for maximum reach today.\n\n"
        "Make every item actionable and specific — no vague advice.",
        3500,
    ),
}
