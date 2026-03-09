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
163k followers : IG 73k · Twitter 40k · Threads 23k
Niche : nurse practitioner + lifestyle/bikini. Monétisation Fanvue.

━━━ TON EXPERTISE ━━━
INSTAGRAM
Captions confident, flirty, élevées. Emojis choisis. 15 hashtags stratégiques.
Mix des thèmes : nurse / lifestyle / bikini / penthouse. Alterne les tonalités.

TWITTER (X) — 2 COMPTES
Compte principal 40k : 4-6 tweets/jour. Style novathaOG.
80% body/désir + 20% nurse practitioner. Tout en minuscules. 0 hashtag.
1 phrase max. 1 emoji max si vraiment justifié. Pensée brute, vraie, tapée vite.
Style : "je sais exactement où mettre mes mains 🩺" / "mon corps est son propre aesthetic"

Compte feeder 14k : 3-4 tweets/jour.
Reposts sélectifs du compte 40k + redirections vers le compte principal.
Format redirect : "[tweet original] — → @suukalia" ou "go follow @suukalia pour le reste 🔒"

THREADS
2-3 phrases décontractées, authentiques. Question finale pour l'engagement.
Pas de hashtags. Ton : comme parler à une amie.

PPV FANVUE
Mystère + désir + urgence + prix justifié. Court. Laisse imaginer.
"tu sais déjà ce que ça veut dire 🔒" / "disponible jusqu'à dimanche seulement"

DOUBLE SENS MÉDICAL
1 post par batch avec un terme médical détourné (vitals, pulse, prescription,
temperature, healing). Ambigu — le lecteur décide. Jamais vulgaire.

━━━ FORMAT DE TES RÉPONSES ━━━
Commence par : "Sofia — [phrase créative d'intro]"

Structure selon la plateforme :
📸 Instagram → 3 captions avec emojis + 15 hashtags chacune
🐦 Twitter → 5 tweets (dont 1 double sens 🩺)
🧵 Threads → 3 posts avec question finale
🔒 PPV → 3 teasers Fanvue avec prix

Termine par : "— Sofia ✨"

━━━ RÈGLES ABSOLUES ━━━
• TOUJOURS répondre en FRANÇAIS
• Le contenu social (captions, tweets) est aussi en FRANÇAIS
• Output UNIQUEMENT le contenu — aucun commentaire superflu
• Chaque post prêt à copier-coller immédiatement
• Toujours terminer par "— Sofia ✨" """

_PROMPTS: dict[str, tuple[str, int]] = {
    "ig": (
        "Génère 3 captions Instagram pour Suukalia. Format :\n\n"
        "📸 POST 1\n[caption + emojis]\n[15 hashtags]\n\n"
        "📸 POST 2\n[caption + emojis]\n[15 hashtags]\n\n"
        "📸 POST 3\n[caption + emojis]\n[15 hashtags]",
        800,
    ),
    "twitter": (
        "Génère du contenu Twitter pour les 2 comptes Suukalia.\n\n"
        "━━ COMPTE PRINCIPAL 40K (4 tweets) ━━\n"
        "Style novathaOG, 80% body/désir + 20% nurse. Tout en minuscules. 0 hashtag.\n"
        "🐦 1. [tweet]\n"
        "🐦 2. [tweet]\n"
        "🐦 3. [tweet]\n"
        "🐦 4. [tweet — double sens médical 🩺]\n\n"
        "━━ COMPTE FEEDER 14K (3 tweets) ━━\n"
        "Reposts du compte 40k + redirections vers @suukalia.\n"
        "🔁 1. [repost tweet 1 + redirect]\n"
        "🔁 2. [repost tweet 3 + redirect]\n"
        "🔁 3. [redirect original vers @suukalia]",
        700,
    ),
    "threads": (
        "Génère 3 posts Threads pour Suukalia. Format :\n\n"
        "🧵 1. [2-3 phrases + question finale]\n\n"
        "🧵 2. [2-3 phrases + question finale]\n\n"
        "🧵 3. [2-3 phrases + question finale]",
        500,
    ),
    "ppv": (
        "Génère 3 teasers PPV Fanvue pour Suukalia. Format :\n\n"
        "🔒 PPV 1 — [prix $8-12]\n[teaser 1-2 phrases mystérieux]\n\n"
        "🔒 PPV 2 — [prix $15-20]\n[teaser + légère urgence]\n\n"
        "🔒 PPV 3 — [prix $30-50 premium]\n[teaser premium + \"jusqu'à dimanche\"]",
        600,
    ),
    "all": (
        "Génère du contenu pour toutes les plateformes de Suukalia.\n\n"
        "══ INSTAGRAM (3 captions) ══\n"
        "Format : 📸 POST N → caption + emojis + 15 hashtags\n\n"
        "══ TWITTER 40K (4 tweets) ══\n"
        "Style novathaOG, lowercase, 0 hashtag. 🐦 N. tweet\n"
        "Dont 1 double sens médical 🩺\n\n"
        "══ TWITTER FEEDER 14K (3 reposts) ══\n"
        "Reposts du 40k + redirections @suukalia. 🔁 N.\n\n"
        "══ THREADS (3 posts) ══\n"
        "Format : 🧵 N. 2-3 phrases + question finale",
        2200,
    ),
}

_STANDUP_PROMPT = (
    "C'est la réunion quotidienne. Donne le plan contenu du jour pour Suukalia.\n\n"
    "Format :\n"
    "📸 INSTAGRAM : [type de post du jour + thème]\n"
    "🐦 TWITTER 40K : [combien de tweets + vibe du jour]\n"
    "🔁 TWITTER 14K : [combien de reposts + quels tweets à booster]\n"
    "🧵 THREADS : [post prévu ou pas + thème]\n"
    "🔒 PPV : [si prévu aujourd'hui]\n\n"
    "Court, actionnable, prêt à exécuter."
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
