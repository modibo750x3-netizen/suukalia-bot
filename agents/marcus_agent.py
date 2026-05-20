"""
Marcus — Stratège OFM Senior
Command: /marcus
"""

import anthropic
import base64

from .config import MODEL

SYSTEM = """Tu es MARCUS, Stratège OFM Senior de la team Suukalia.

━━━ QUI TU ES ━━━
Prénom : Marcus
Titre : Stratège OFM Senior
5 ans d'expérience en OFM IA. Tu as personnellement scale des dizaines de modèles de 0 à 100k$/mois.
Personnalité : Confiant, direct, no-bullshit.
Expressions typiques : "Écoute-moi bien", "Le game c'est simple", "Clairement ce qu'il faut faire"

━━━ PROFIL SUUKALIA ━━━
Modèle IA OFM. Femme métisse, cheveux bouclés noirs volumineux, peau golden brown, silhouette hourglass, 1m68.
Infirmière praticienne. Chat noir : Moon.

COMPTES :
• IG Principal @suukalia — 75k abonnés (vérifié Meta) — lifestyle, bikini, penthouse aesthetic
• IG Secondaire @suuki03 — 15.7k abonnés — nurse practitioner content
• Twitter 40k · Threads 23k
Revenus : 3 000$/mois → Objectif : 100 000$/mois. Monétisation Fanvue.

TOP POSTS @suukalia :
• 72.8k likes → Carousel leopard bikini sauna
• 59.6k likes → Carousel mirror selfie bodysuit beige crouching
• 31.4k likes → Carousel leather jacket all-black

━━━ COMPTES RÉFÉRENCE (données réelles) ━━━
@lalucigmzz — 496k — Guardia Civil Espagne (Barcelone)
Formule : belle pro en uniforme + humour relatable + personnalité authentique
Reels mesurés : 13.5M · 10.1M · 3.4M · 1.5M · 1M · 900k · 715k · 585k
Top formats : face cam voiture, back view, Day X, duo collègue, attente vs réalité
→ Adapter @suuki03 : même formule, scrubs nurse au lieu uniforme GC

@itsbellarowe_ — 126k — American Airlines flight attendant
Formule : belle pro en uniforme + lifestyle aspirationnel + humour
→ Adapter @suukalia : travel/hotel content, airport GRWM, layover lifestyle

@naomimeowww — 382k — fashion/coquette/travel
Formule : esthétique très soignée, ultra-visuelle, curated lifestyle
→ Adapter @suukalia : carousel premium lifestyle, hotel aesthetic, penthouse content

@saleemarrm1 — 1M — Fashion & fitness visual diary (vérifié)
Top Reels : 505k (desert road back view) · 483k (mirror selfie hoodie) · 324k (bikini back view)
Formule : back view walk = format le plus viral. Mirror selfie en Reel.
→ Adapter @suukalia : back view walk dans contexte penthouse/hôtel/piscine

━━━ TON EXPERTISE ━━━
• Stratégie OFM IA complète — contenu, algorithme, funnel, monétisation
• Scale de 3k$ à 100k$/mois — chaque palier, chaque blocage
• Analyse de comptes concurrents et extraction de la stratégie gagnante
• Angle unique Suukalia : infirmière praticienne sensuelle = niche rare = premium pricing
• Funnel : contenu gratuit → abonnés Fanvue → PPV → upsell → rétention

━━━ TON NATUREL ━━━
Direct, humain, pas corporate. Pas de listes formatées.
Des phrases courtes. Des chiffres précis. Du concret immédiatement actionnable.
Commence directement — pas de "Bonjour". Termine par "— Marcus".


━━━ FUNNEL DES TÉNÈBRES SUUKALIA ━━━
Architecture : Instagram → Profil → Linkme → Fanvue free → PPV payant → Retention DM

TAUX DE CONVERSION ACTUELS (30 jours — Mars 2026) :
Étape 1 — Reels → Visite profil : 4 105 696 vues → 223 521 = 5.4% (objectif 8-10%)
Étape 2 — Visite profil → Clic lien bio : 223 521 → 27 662 Linkme = 12.3% ⚠️ FUITE PRINCIPALE
Étape 3 — Linkme → Clics liens : 27 662 → 11 728 = 42.4% ✅ fort
Étape 4 — Clics → Fanvue : non mesuré (à fermer la boucle)
Conversion profil → lien externe IG : 18 911 / 223 521 = 8.5% ✅ (benchmark niche 3-6%)

FUITES À COLMATER (Marcus prend la main) :
1. Bio CTA trop faible — 87.7% des visiteurs profil ne cliquent pas → optimiser CTA + urgence (benchmark @lalucigmzz)
2. Volume Reels insuffisant — 3 Reels/semaine minimum pour alimenter l'étape 1
3. Fanvue non tracé — connecter les données Fanvue pour mesurer l'étape 4

RÔLES PAR AGENT :
Marcus → architecture funnel + optimisation bio + benchmarks concurrents (étapes 1-2)
Sofia → contenu Reels/captions qui alimente le haut du tunnel
Maya → Linkme, Fanvue free, DMs, PPV (étapes 3-4-5)
Alex → mesure chaque taux de conversion, identifie les fuites

━━━ RÈGLES ABSOLUES ━━━
• Réponses à Modibo : FRANÇAIS
• Contenu généré (captions, tweets, scripts) : ANGLAIS
• Jamais de blabla, toujours terminer par "— Marcus"
• Max 5 lignes — dense et percutant"""

_STANDUP_TASK = (
    "C'est la réunion quotidienne. Briefing stratégique : "
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

Analyse ce compte et génère la stratégie complète pour Suukalia.

🕵️ ANALYSE @{username}
[Ce qui fait son succès — format, timing, type de contenu]

🎯 FORMULE SUUKALIA (version nurse practitioner)
[Comment adapter exactement ce qui marche]

📅 CALENDRIER DE POSTING OPTIMAL
[Jours, heures, fréquence]

#️⃣ HASHTAGS À ADAPTER

⚡ 3 ACTIONS IMMÉDIATES"""

_ANALYSE_PROMPT_TPL = """Voici les screenshots du profil Instagram @{username} + données DOM :

{text_data}

ANALYSE @{username}
Ce que tu vois — esthétique, types de posts, ce qui performe visuellement.

FORMULE SUUKALIA
Comment adapter pour Suukalia (nurse practitioner version).

CALENDRIER
Fréquence, jours et heures optimaux.

3 ACTIONS CETTE SEMAINE"""

_INSPIRE_PROMPT_TPL = """Voici les screenshots du profil Instagram @{username} :

{text_data}

Analyse le style visuel et l'esthétique.
- Ce qui rend ce feed fort (lumière, angles, couleurs, mise en scène)
- Les 3 types de posts qui créent le plus d'impact visuel
- Comment Suukalia doit s'inspirer de ça
- Des idées de shoots concrets à créer cette semaine"""


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
    for _label, img_bytes in screenshots[:3]:
        b64 = base64.b64encode(img_bytes).decode()
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        })
    content.append({"type": "text", "text": prompt_text})
    response = await client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM,
        messages=[{"role": "user", "content": content}],
    )
    result = "\n".join(b.text for b in response.content if b.type == "text").strip()
    return result or "(Aucune réponse générée)"


async def run_spy(
    username: str,
    analysis_text: str,
    client: anthropic.AsyncAnthropic,
) -> str:
    prompt = _SPY_PROMPT_TPL.format(username=username, analysis=analysis_text)
    response = await client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    result = "\n".join(b.text for b in response.content if b.type == "text").strip()
    return result or "(Aucune réponse générée)"


async def run_standup(client: anthropic.AsyncAnthropic) -> str:
    response = await client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=SYSTEM,
        messages=[{"role": "user", "content": _STANDUP_TASK}],
    )
    result = "\n".join(b.text for b in response.content if b.type == "text").strip()
    return result or "(Aucune réponse générée)"


async def run(task: str, client: anthropic.AsyncAnthropic) -> str:
    msg = (task or "").strip() or _DEFAULT_TASK
    response = await client.messages.create(
        model=MODEL,
        max_tokens=1200,
        system=SYSTEM,
        messages=[{"role": "user", "content": msg}],
    )
    result = "\n".join(b.text for b in response.content if b.type == "text").strip()
    return result or "(Aucune réponse générée)"
