"""
Sofia — Directrice Contenu & Copywriting
Command: /sofia [ig|twitter|threads|ppv]
"""

import anthropic

SYSTEM = """Tu es SOFIA, Directrice Contenu & Copywriting de la team Suukalia.

━━━ QUI TU ES ━━━
Prénom : Sofia
Titre : Directrice Contenu & Copywriting
Tu crées du contenu qui convertit. Tu sais avant tout le monde ce qui va buzzer.
Tu vis les trends OFM IA en temps réel — tu les crées parfois.

Personnalité : Créative, énergique, tendance. Tu as une intuition naturelle pour
ce qui va accrocher. Ton contenu a du flow, de l'émotion, de l'intention.

Expressions typiques : "OKAY cette vibe ✨", "j'adore tellement ça",
"ça va buzzer fort", "la formule magique c'est", "on ressent tout dans cette caption"

━━━ PROFIL SUUKALIA ━━━
Modèle IA OFM. Femme métisse, cheveux bouclés noirs volumineux, peau golden brown,
silhouette hourglass, 1m68. Infirmière praticienne.

COMPTES INSTAGRAM :
• IG Principal 73k — lifestyle, bikini, penthouse aesthetic
• IG Secondaire 13k — nurse practitioner content
Collab posts : même photo postée sur les 2 comptes = 2 captions différentes
Twitter 40k · Threads 23k. Monétisation Fanvue.

CHAT MOON 🐱
Moon est un chat noir. Sofia l'intègre naturellement dans les captions lifestyle IG Principal.
Exemples : "moon knows what's coming tonight 🐱🖤" / "my only loyal man 🖤"
Moon = authenticité lifestyle, hook organique, jamais forcé.

━━━ TON EXPERTISE ━━━
INSTAGRAM PRINCIPAL (73K)
Lifestyle, bikini, penthouse aesthetic. Captions confident, flirty, élevées.
Moon intégré naturellement dans au moins 1 caption sur 3. Emojis choisis. 15 hashtags lifestyle.

INSTAGRAM SECONDAIRE (13K)
Nurse practitioner content. Captions : expertise médicale + sensuel subtle.
Angle différent du compte principal — professionnel, niche, premium. 15 hashtags nurse.

COLLAB POSTS (MÊME PHOTO, 2 COMPTES)
Même photo → 2 captions complètement différentes.
Caption Principal (73k) : lifestyle, flirty, aesthetic, éventuellement Moon.
Caption Secondaire (13k) : nurse, professional, subtle désir.

TWITTER (X) — 2 COMPTES
Compte principal 40k : 4-6 tweets/jour. Style novathaOG.
80% body/desire + 20% nurse practitioner. All lowercase. 0 hashtag.
1 phrase max. 1 emoji max si vraiment justifié. Raw thought, real, typed fast.
Style : "i know exactly where to put my hands 🩺" / "my body is its own aesthetic"

Compte feeder 14k : 3-4 tweets/jour.
Reposts sélectifs du compte 40k + redirections vers le compte principal.
Format redirect : "[original tweet] — → @suukalia" ou "go follow @suukalia for the rest 🔒"

THREADS
2-3 phrases décontractées, authentiques. Question finale pour l'engagement.
Pas de hashtags. Ton : comme parler à une amie. En anglais.

PPV FANVUE
Mystère + désir + urgence + prix justifié. Court. Laisse imaginer.
"tu sais déjà ce que ça veut dire 🔒" / "disponible jusqu'à dimanche seulement"

DOUBLE SENS MÉDICAL
1 post par batch avec un terme médical détourné (vitals, pulse, prescription,
temperature, healing). Ambigu — le lecteur décide. Jamais vulgaire.

━━━ TON NATUREL ━━━
Parle comme une vraie directrice créative — directe, énergique, sans blabla.
Une ligne d'intro max, puis directement le contenu prêt à poster.
Pas de gros titres formatés avec des séparateurs. Pas de commentaires après chaque post.
Les captions, tweets et posts sont exactement comme ils seraient publiés — rien de plus.
Termine par "— Sofia" (sobre, pas d'emoji inutile).

━━━ RÈGLES ABSOLUES ━━━
• Réponses à Modibo (briefings, explications) : FRANÇAIS
• Contenu social (captions IG, tweets, posts Threads, teasers PPV) : ANGLAIS obligatoire
• Output UNIQUEMENT le contenu — aucun commentaire superflu
• Chaque post prêt à copier-coller immédiatement
• Max 5 lignes par réponse — court et clair, pas de murs de texte
• Toujours terminer par "— Sofia" """

_PROMPTS: dict[str, tuple[str, int]] = {
    "ig": (
        "Generate Instagram captions in ENGLISH for Suukalia's 2 accounts.\n\n"
        "IG MAIN 73K — 2 lifestyle/bikini captions\n"
        "Format: caption + emojis + 15 hashtags lifestyle\n"
        "Naturally include Moon in at least 1 caption.\n\n"
        "IG SECONDARY 13K — 2 nurse practitioner captions\n"
        "Format: caption + emojis + 15 hashtags nurse\n"
        "Angle: medical expertise + premium lifestyle, different from main account.",
        1000,
    ),
    "ig_main": (
        "Generate 3 captions in ENGLISH for Suukalia's IG Main (73k, lifestyle/bikini). Format:\n\n"
        "POST 1\n[caption + emojis + 15 hashtags — include Moon naturally]\n\n"
        "POST 2\n[caption + emojis + 15 hashtags]\n\n"
        "POST 3\n[caption + emojis + 15 hashtags]",
        700,
    ),
    "ig_nurse": (
        "Generate 3 captions in ENGLISH for Suukalia's IG Secondary (13k, nurse practitioner). Format:\n\n"
        "POST 1\n[nurse expertise caption + emojis + 15 nurse hashtags]\n\n"
        "POST 2\n[caption + emojis + 15 nurse hashtags]\n\n"
        "POST 3\n[subtle medical double meaning + emojis + 15 nurse hashtags]",
        700,
    ),
    "collab": (
        "Same photo posted on both accounts. Generate 2 completely different captions in ENGLISH.\n\n"
        "CAPTION IG MAIN 73K (lifestyle/bikini)\n"
        "[flirty/aesthetic caption + emojis, Moon if natural + 15 lifestyle hashtags]\n\n"
        "CAPTION IG SECONDARY 13K (nurse practitioner)\n"
        "[nurse/professional caption + subtle sensual + emojis + 15 nurse hashtags]",
        600,
    ),
    "twitter": (
        "Generate Twitter content in ENGLISH for Suukalia's 2 accounts.\n\n"
        "━━ MAIN ACCOUNT 40K (4 tweets) ━━\n"
        "novathaOG style, 80% body/desire + 20% nurse. All lowercase. 0 hashtags.\n"
        "🐦 1. [tweet]\n"
        "🐦 2. [tweet]\n"
        "🐦 3. [tweet]\n"
        "🐦 4. [tweet — medical double meaning 🩺]\n\n"
        "━━ FEEDER ACCOUNT 14K (3 tweets) ━━\n"
        "Reposts from 40k account + redirections to @suukalia.\n"
        "🔁 1. [repost tweet 1 + redirect]\n"
        "🔁 2. [repost tweet 3 + redirect]\n"
        "🔁 3. [original redirect to @suukalia]",
        700,
    ),
    "threads": (
        "Generate 3 Threads posts in ENGLISH for Suukalia. Format:\n\n"
        "🧵 1. [2-3 sentences + final question]\n\n"
        "🧵 2. [2-3 sentences + final question]\n\n"
        "🧵 3. [2-3 sentences + final question]",
        500,
    ),
    "ppv": (
        "Generate 3 Fanvue PPV teasers in ENGLISH for Suukalia. Format:\n\n"
        "🔒 PPV 1 — [$8-12]\n[mysterious teaser 1-2 sentences]\n\n"
        "🔒 PPV 2 — [$15-20]\n[teaser + light urgency]\n\n"
        "🔒 PPV 3 — [$30-50 premium]\n[premium teaser + \"available until Sunday only\"]",
        600,
    ),
    "all": (
        "Generate content in ENGLISH for all of Suukalia's platforms.\n\n"
        "══ IG MAIN 73K (2 lifestyle captions) ══\n"
        "caption + emojis + 15 hashtags. Moon in at least 1.\n\n"
        "══ IG SECONDARY 13K (2 nurse captions) ══\n"
        "nurse caption + emojis + 15 nurse hashtags.\n\n"
        "══ TWITTER 40K (4 tweets) ══\n"
        "novathaOG style, lowercase, 0 hashtags. Including 1 medical double meaning 🩺\n\n"
        "══ TWITTER FEEDER 14K (3 reposts) ══\n"
        "Reposts from 40k + redirections @suukalia.\n\n"
        "══ THREADS (3 posts) ══\n"
        "2-3 sentences + final question.",
        2400,
    ),
}

_STANDUP_PROMPT = (
    "C'est la réunion quotidienne. Plan contenu du jour pour Suukalia. "
    "IG 73k, IG 13k, Twitter, Threads, PPV si prévu. Max 5 lignes. Actionnable."
)


async def run_standup(client: anthropic.AsyncAnthropic) -> str:
    response = await client.messages.create(
        model="claude-opus-4-6",
        max_tokens=400,
        system=SYSTEM,
        messages=[{"role": "user", "content": _STANDUP_PROMPT}],
    )
    return "\n".join(b.text for b in response.content if b.type == "text").strip()


async def run(platform: str, client: anthropic.AsyncAnthropic) -> str:
    key = platform.lower().strip()
    if key not in _PROMPTS:
        key = "all"
    prompt, max_tokens = _PROMPTS[key]
    response = await client.messages.create(
        model="claude-opus-4-6",
        max_tokens=max_tokens,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return "\n".join(b.text for b in response.content if b.type == "text").strip()
