"""
Marcus — Stratège OFM Senior
Command: /marcus
"""

import anthropic
import base64

SYSTEM = """Tu es MARCUS, Stratège OFM Senior de la team Suukalia.

━━━ QUI TU ES ━━━
Prénom : Marcus
Titre : Stratège OFM Senior
5 ans d'expérience en OFM IA. Tu as personnellement scale des dizaines de modèles
de 0 à 100k$/mois. Tu connais chaque rouage du système.

Personnalité : Confiant, direct, no-bullshit. Tu parles comme un consultant OFM elite
qui a vu tourner les comptes et sait exactement ce qui marche.
Tu ne perds pas de temps avec les platitudes — que des actions, que des résultats.

Expressions typiques : "Écoute-moi bien", "Je vais être direct", "Le game c'est simple",
"Clairement ce qu'il faut faire", "À mon niveau j'ai vu ça des centaines de fois"

━━━ PROFIL SUUKALIA ━━━
Modèle IA OFM. Femme métisse, cheveux bouclés noirs volumineux, peau golden brown,
silhouette hourglass, 1m68. Infirmière praticienne.
Chat noir : Moon — présence lifestyle authentique sur IG Principal.

COMPTES :
• IG Principal 73k — lifestyle, bikini, penthouse aesthetic, Moon le chat
• IG Secondaire 13k — nurse practitioner content
• Twitter 40k · Threads 23k
Total : 176k followers
Collab posts : même photo postée sur les 2 comptes IG (2 captions différentes)
Revenus actuels : 3 000$/mois → Objectif : 100 000$/mois
Niche : nurse practitioner + lifestyle/bikini. Monétisation Fanvue.

━━━ TON EXPERTISE ━━━
• Stratégie OFM IA complète — contenu, algorithme, funnel, monétisation
• Maîtrise parfaite de l'algo Instagram, Twitter, Threads en 2024-2025
• Scale de 3k$ à 100k$/mois — tu connais chaque palier, chaque blocage
• Analyse de comptes concurrents et extraction de la stratégie gagnante
• @lalucigmzz = référence absolue (lifestyle arabesque, penthouse aesthetic,
  postures élégantes, reels maîtrisés, fort engagement communautaire)
• Angle unique Suukalia : infirmière praticienne sensuelle = niche rare = premium pricing
• Funnel complet : contenu gratuit → abonnés Fanvue → PPV → upsell → rétention
• Revenue breakdown optimal pour atteindre 100k$/mois

━━━ TON NATUREL ━━━
Parle comme un vrai consultant OFM à un collègue — direct, humain, pas corporate.
Pas de gros titres avec des tirets ou des emojis en cascade. Pas de listes à puces formatées.
Des phrases courtes. Des chiffres précis. Du concret immédiatement actionnable.
Commence directement par la stratégie — pas de "Bonjour" ni de "Super question".
Termine par "— Marcus" (sobre, pas d'emoji).

Exemple de bonne réponse :
"Marcus ici. Cette semaine focus nurse scrubs — tes posts bikini sous-performent de 40%.
Double les selfies miroir, 2 reels nurse avant vendredi. Push PPV vendredi soir 21h.
Objectif : +15% revenue sur 7 jours."

━━━ RÈGLES ABSOLUES ━━━
• TOUJOURS répondre en FRANÇAIS
• Jamais de blabla, jamais de compliments vides
• Toujours terminer par "— Marcus"
• Max 8 lignes — dense et percutant"""

_STANDUP_TASK = (
    "C'est la réunion quotidienne. Donne ton briefing stratégique du jour en mode consultant : "
    "top 3 priorités aujourd'hui, 1 action immédiate, 1 risque à surveiller. "
    "Max 5 lignes. Percutant."
)

_DEFAULT_TASK = (
    "Génère la stratégie OFM de la semaine pour Suukalia. "
    "Analyse ce que ferait @lalucigmzz et donne la version nurse practitioner. "
    "Inclus les actions concrètes pour progresser vers 100k$/mois."
)


_SPY_PROMPT_TPL = """Voici les données scraped d'Instagram pour @{username} :

{analysis}

En tant que Marcus, Stratège OFM Senior, analyse ce compte et génère la stratégie complète pour Suukalia.

Structure ta réponse :

🕵️ ANALYSE @{username}
[Ce qui fait son succès — format, timing, type de contenu, style caption]

🎯 FORMULE SUUKALIA (version nurse practitioner)
[Comment adapter exactement ce qui marche pour Suukalia]

📅 CALENDRIER DE POSTING OPTIMAL
[Jours, heures, fréquence — basé sur les données]

#️⃣ HASHTAGS À ADAPTER
[Liste des hashtags à copier/adapter pour la niche nurse]

⚡ 3 ACTIONS IMMÉDIATES (à faire cette semaine)
• [Action 1]
• [Action 2]
• [Action 3]"""


_ANALYSE_PROMPT_TPL = """Voici les screenshots du profil Instagram @{username} + données DOM extraites :

{text_data}

Analyse visuelle et stratégique de ce compte. Structure ta réponse :

ANALYSE @{username}
Ce que tu vois — esthétique, types de posts, ce qui performe visuellement.

FORMULE SUUKALIA
Comment adapter exactement ce style pour Suukalia (nurse practitioner version).
Quels éléments visuels copier, quels angles éviter.

CALENDRIER
Fréquence, jours et heures optimaux basés sur ce que tu vois.

3 ACTIONS CETTE SEMAINE
Concrètes, directement inspirées de ce compte."""

_INSPIRE_PROMPT_TPL = """Voici les screenshots du profil Instagram @{username} :

{text_data}

Analyse le style visuel et l'esthétique de ce compte. Je veux :
- Ce qui rend ce feed visuellement fort (lumière, angles, couleurs, mise en scène)
- Les 3 types de posts qui créent le plus d'impact visuel
- Comment Suukalia (infirmière praticienne, aesthetic élégant) doit s'inspirer de ça
- Des idées de shoots et de visuels concrets à créer cette semaine"""


async def run_analyse(
    username: str,
    screenshots: list[tuple[str, bytes]],
    text_data: str,
    client: anthropic.AsyncAnthropic,
    inspire_mode: bool = False,
) -> str:
    tpl = _INSPIRE_PROMPT_TPL if inspire_mode else _ANALYSE_PROMPT_TPL
    prompt_text = tpl.format(username=username, text_data=text_data)

    content: list[dict] = []
    # Add screenshots as vision inputs (max 3 to stay within token limits)
    for _label, img_bytes in screenshots[:3]:
        b64 = base64.b64encode(img_bytes).decode()
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        })
    content.append({"type": "text", "text": prompt_text})

    # Note: extended thinking is not used with vision to ensure compatibility
    response = await client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        system=SYSTEM,
        messages=[{"role": "user", "content": content}],
    )
    return "\n".join(b.text for b in response.content if b.type == "text").strip()


async def run_spy(
    username: str, analysis_text: str, client: anthropic.AsyncAnthropic
) -> str:
    prompt = _SPY_PROMPT_TPL.format(username=username, analysis=analysis_text)
    response = await client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        thinking={"type": "adaptive"},
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return "\n".join(b.text for b in response.content if b.type == "text").strip()


async def run_standup(client: anthropic.AsyncAnthropic) -> str:
    response = await client.messages.create(
        model="claude-opus-4-6",
        max_tokens=400,
        thinking={"type": "adaptive"},
        system=SYSTEM,
        messages=[{"role": "user", "content": _STANDUP_TASK}],
    )
    return "\n".join(b.text for b in response.content if b.type == "text").strip()


async def run(task: str, client: anthropic.AsyncAnthropic) -> str:
    response = await client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1200,
        thinking={"type": "adaptive"},
        system=SYSTEM,
        messages=[{"role": "user", "content": task or _DEFAULT_TASK}],
    )
    return "\n".join(b.text for b in response.content if b.type == "text").strip()
