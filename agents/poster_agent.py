"""
Agent Poster — Ready-to-post content for IG, Twitter, Threads.
Command: /poster [ig|twitter|threads]  (default: all platforms)
"""

import anthropic

from .config import MODEL

SYSTEM = """Tu es l'Agent Poster de la team Suukalia (aka Suuki).

═══ PROFIL SUUKALIA ═══
Femme métisse, cheveux bouclés noirs, peau dorée, silhouette sablier (1m68).
Infirmière praticienne. Penthouse avec néon rose SUUKI. Fanvue monetization.
Style: nurse practitioner + lifestyle/bikini. Dualité soignante + goddess.

═══ VOIX PAR PLATEFORME ═══
INSTAGRAM → confident, flirty, élevé. Emojis purposeful. 15 hashtags. Mix nurse/lifestyle/bikini.
TWITTER   → all lowercase. 1 phrase max. 0 hashtag. Pensée brute et vraie. Max 1 emoji si justifié.
THREADS   → décontracté, 2-3 phrases, authentique, question finale. Pas de hashtags. Léger et relatable.

═══ NURSE DOUBLE SENS ═══
1 post par batch doit jouer sur un mot médical (vitals, pulse, prescription, healing, temperature).
Ambigu — le lecteur décide. Jamais vulgaire, toujours suggestif.

═══ RÈGLES STRICTES ═══
• Output UNIQUEMENT le contenu — aucune intro, label, explication
• Chaque post prêt à copier-coller immédiatement
• Varier les tons: mystérieux / empowerment / sensuel / relatable / nurse double-sens
• Pas de répétition entre les posts d'un même batch"""

_IG = (
    "Génère 3 captions Instagram pour Suukalia. Format exact:\n\n"
    "📸 POST 1\n[caption + emojis]\n[15 hashtags]\n\n"
    "📸 POST 2\n[caption + emojis]\n[15 hashtags]\n\n"
    "📸 POST 3\n[caption + emojis]\n[15 hashtags]"
)

_TWITTER = (
    "Génère 5 tweets pour Suukalia. Format exact:\n\n"
    "🐦 1. [tweet all lowercase]\n"
    "🐦 2. [tweet all lowercase]\n"
    "🐦 3. [tweet all lowercase]\n"
    "🐦 4. [tweet all lowercase]\n"
    "🐦 5. [tweet — nurse double sens 🩺]"
)

_THREADS = (
    "Génère 3 posts Threads pour Suukalia. Format exact:\n\n"
    "🧵 1. [2-3 phrases + question finale]\n\n"
    "🧵 2. [2-3 phrases + question finale]\n\n"
    "🧵 3. [2-3 phrases + question finale]"
)

_ALL = (
    f"Génère du contenu pour les 3 plateformes de Suukalia.\n\n"
    f"══ INSTAGRAM ══\n{_IG}\n\n"
    f"══ TWITTER ══\n{_TWITTER}\n\n"
    f"══ THREADS ══\n{_THREADS}"
)

_PROMPTS: dict[str, tuple[str, int]] = {
    "ig":      (_IG,     800),
    "twitter": (_TWITTER, 500),
    "threads": (_THREADS, 500),
    "all":     (_ALL,   2000),
}


async def run(platform: str, client: anthropic.AsyncAnthropic) -> str:
    key = platform.lower().strip()
    if key not in _PROMPTS:
        key = "all"
    prompt, max_tokens = _PROMPTS[key]
    response = await client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    result = "\n".join(b.text for b in response.content if b.type == "text").strip()
    return result or "(Aucune réponse générée)"
