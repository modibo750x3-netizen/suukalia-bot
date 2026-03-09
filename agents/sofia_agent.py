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

━━━ TON NATUREL ━━━
Parle comme une vraie directrice créative — directe, énergique, sans blabla.
Une ligne d'intro max, puis directement le contenu prêt à poster.
Pas de gros titres formatés avec des séparateurs. Pas de commentaires après chaque post.
Les captions, tweets et posts sont exactement comme ils seraient publiés — rien de plus.
Termine par "— Sofia" (sobre, pas d'emoji inutile).

━━━ RÈGLES ABSOLUES ━━━
• TOUJOURS répondre en FRANÇAIS
• Le contenu social (captions, tweets) est en FRANÇAIS
• Output UNIQUEMENT le contenu — aucun commentaire superflu
• Chaque post prêt à copier-coller immédiatement
• Toujours terminer par "— Sofia" """

_PROMPTS: dict[str, tuple[str, int]] = {
    "ig": (
        "Génère des captions Instagram pour les 2 comptes Suukalia.\n\n"
        "IG PRINCIPAL 73K — 2 captions lifestyle/bikini\n"
        "Format : caption + emojis + 15 hashtags lifestyle\n"
        "Intègre Moon naturellement dans au moins 1 caption.\n\n"
        "IG SECONDAIRE 13K — 2 captions nurse practitioner\n"
        "Format : caption + emojis + 15 hashtags nurse\n"
        "Angle : expertise médicale + lifestyle premium, différent du compte principal.",
        1000,
    ),
    "ig_main": (
        "Génère 3 captions pour l'IG Principal Suukalia (73k, lifestyle/bikini). Format :\n\n"
        "POST 1\n[caption + emojis + 15 hashtags — inclure Moon naturellement]\n\n"
        "POST 2\n[caption + emojis + 15 hashtags]\n\n"
        "POST 3\n[caption + emojis + 15 hashtags]",
        700,
    ),
    "ig_nurse": (
        "Génère 3 captions pour l'IG Secondaire Suukalia (13k, nurse practitioner). Format :\n\n"
        "POST 1\n[caption expertise nurse + emojis + 15 hashtags nurse]\n\n"
        "POST 2\n[caption + emojis + 15 hashtags nurse]\n\n"
        "POST 3\n[double sens médical subtil + emojis + 15 hashtags nurse]",
        700,
    ),
    "collab": (
        "Même photo postée sur les 2 comptes. Génère 2 captions complètement différentes.\n\n"
        "CAPTION IG PRINCIPAL 73K (lifestyle/bikini)\n"
        "[caption flirty/aesthetic + emojis, Moon si naturel + 15 hashtags lifestyle]\n\n"
        "CAPTION IG SECONDAIRE 13K (nurse practitioner)\n"
        "[caption nurse/professional + sensuel subtle + emojis + 15 hashtags nurse]",
        600,
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
        "══ IG PRINCIPAL 73K (2 captions lifestyle) ══\n"
        "caption + emojis + 15 hashtags. Moon dans au moins 1.\n\n"
        "══ IG SECONDAIRE 13K (2 captions nurse) ══\n"
        "caption nurse + emojis + 15 hashtags nurse.\n\n"
        "══ TWITTER 40K (4 tweets) ══\n"
        "Style novathaOG, lowercase, 0 hashtag. Dont 1 double sens médical 🩺\n\n"
        "══ TWITTER FEEDER 14K (3 reposts) ══\n"
        "Reposts du 40k + redirections @suukalia.\n\n"
        "══ THREADS (3 posts) ══\n"
        "2-3 phrases + question finale.",
        2400,
    ),
}

_STANDUP_PROMPT = (
    "C'est la réunion quotidienne. Donne le plan contenu du jour pour Suukalia.\n\n"
    "IG Principal 73k : type de post + thème (lifestyle/bikini/Moon)\n"
    "IG Secondaire 13k : post nurse prévu ou pas + angle\n"
    "Collab post aujourd'hui ? oui/non + idée si oui\n"
    "Twitter 40k : nb tweets + vibe du jour\n"
    "Twitter 14k : nb reposts\n"
    "Threads : post ou pas + thème\n"
    "PPV : si prévu aujourd'hui\n\n"
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
