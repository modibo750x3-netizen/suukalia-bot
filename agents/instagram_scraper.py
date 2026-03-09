"""
Instagram public profile scraper — uses instaloader (no auth required for public accounts).
Returns structured data for Marcus strategy analysis.
"""

import asyncio
import logging
import re
from collections import Counter
from datetime import timezone

logger = logging.getLogger(__name__)

# ── Username extraction ────────────────────────────────────────────────────────

def extract_username(raw: str) -> str:
    """Accept @handle, full URL, or bare username. Returns clean lowercase username."""
    s = raw.strip().rstrip("/")
    m = re.search(r'instagram\.com/([A-Za-z0-9._]+)', s)
    if m:
        return m.group(1).lower()
    return s.lstrip("@").lower()


# ── Core sync scraper (runs in thread pool) ────────────────────────────────────

def _scrape_sync(username: str, max_posts: int = 15) -> dict:
    import instaloader

    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
        request_timeout=30,
    )

    profile = instaloader.Profile.from_username(L.context, username)

    posts_data = []
    for post in profile.get_posts():
        if len(posts_data) >= max_posts:
            break
        hashtags = re.findall(r"#(\w+)", post.caption or "")
        posts_data.append({
            "date": post.date_utc.replace(tzinfo=timezone.utc),
            "type": post.typename,   # GraphImage | GraphSidecar | GraphVideo
            "likes": post.likes,
            "comments": post.comments,
            "caption": (post.caption or "")[:300],
            "hashtags": hashtags,
            "caption_len": len(post.caption or ""),
        })

    if not posts_data:
        return {
            "username": username,
            "followers": profile.followers,
            "following": profile.followees,
            "total_posts": profile.mediacount,
            "scraped": 0,
            "error": "no_posts",
        }

    total_likes    = sum(p["likes"] for p in posts_data)
    total_comments = sum(p["comments"] for p in posts_data)
    avg_likes      = total_likes // len(posts_data)
    avg_comments   = total_comments // len(posts_data)
    followers      = profile.followers
    eng_rate       = round((avg_likes + avg_comments) / followers * 100, 2) if followers else 0

    type_counts = Counter(p["type"] for p in posts_data)
    day_counts  = Counter(p["date"].strftime("%A") for p in posts_data)
    hour_counts = Counter(p["date"].hour for p in posts_data)

    all_tags = []
    for p in posts_data:
        all_tags.extend(p["hashtags"])
    top_hashtags = Counter(all_tags).most_common(15)

    top_posts = sorted(posts_data, key=lambda p: p["likes"] + p["comments"], reverse=True)[:3]

    if len(posts_data) >= 2:
        dates = sorted(p["date"] for p in posts_data)
        span_days = max((dates[-1] - dates[0]).days, 1)
        posts_per_week = round(len(posts_data) / (span_days / 7), 1)
    else:
        posts_per_week = 1.0

    return {
        "username": username,
        "followers": followers,
        "following": profile.followees,
        "total_posts": profile.mediacount,
        "scraped": len(posts_data),
        "avg_likes": avg_likes,
        "avg_comments": avg_comments,
        "engagement_rate": eng_rate,
        "posts_per_week": posts_per_week,
        "content_types": dict(type_counts),
        "best_days": day_counts.most_common(3),
        "best_hours": hour_counts.most_common(3),
        "top_hashtags": top_hashtags,
        "top_posts": top_posts,
        "recent_captions": [(p["caption"][:200]) for p in posts_data[:5]],
        "avg_caption_len": sum(p["caption_len"] for p in posts_data) // len(posts_data),
    }


async def scrape(username_or_url: str, max_posts: int = 15) -> dict:
    """Async wrapper — runs instaloader in a thread pool executor."""
    username = extract_username(username_or_url)
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _scrape_sync, username, max_posts)
    except Exception as exc:
        logger.warning("Instagram scrape failed for @%s: %s", username, exc)
        return {"username": username, "error": str(exc)}


# ── Data formatter ─────────────────────────────────────────────────────────────

_TYPE_LABELS = {
    "GraphImage":   "📸 Photos",
    "GraphSidecar": "🎠 Carousels",
    "GraphVideo":   "🎬 Reels/Vidéos",
}

def format_for_marcus(data: dict) -> str:
    """Format scraped data into a readable text block for Marcus."""
    u = data.get("username", "?")

    if data.get("error") or data.get("scraped", 0) == 0:
        return (
            f"⚠️ Données Instagram @{u} non disponibles ({data.get('error', 'aucun post')}).\n"
            "Marcus va analyser ce compte de mémoire."
        )

    content_mix = " · ".join(
        f"{_TYPE_LABELS.get(k, k)}: {v}"
        for k, v in data.get("content_types", {}).items()
    )
    best_days  = ", ".join(f"{d} ({n}x)" for d, n in data.get("best_days", []))
    best_hours = ", ".join(f"{h}h UTC ({n}x)" for h, n in data.get("best_hours", []))
    top_tags   = " ".join(f"#{t}" for t, _ in data.get("top_hashtags", [])[:12])

    top_posts_lines = []
    for i, p in enumerate(data.get("top_posts", []), 1):
        label = _TYPE_LABELS.get(p.get("type", ""), p.get("type", ""))
        cap = p["caption"][:130].replace("\n", " ")
        top_posts_lines.append(
            f"  #{i} {label} — {p['likes']:,}❤️  {p['comments']}💬\n"
            f"     \"{cap}...\""
        )
    top_posts_text = "\n".join(top_posts_lines)

    recent_caps = "\n".join(
        f"  • \"{c[:160].replace(chr(10), ' ')}\"" for c in data.get("recent_captions", [])[:4]
    )

    return (
        f"━━━ DATA INSTAGRAM @{u} ━━━\n"
        f"👥 {data.get('followers', '?'):,} followers · {data.get('following', '?'):,} following\n"
        f"📸 {data.get('total_posts', '?')} posts total · {data.get('scraped', '?')} analysés\n\n"
        f"📊 MÉTRIQUES\n"
        f"• Moy. likes : {data.get('avg_likes', '?'):,}\n"
        f"• Moy. commentaires : {data.get('avg_comments', '?'):,}\n"
        f"• Taux d'engagement : {data.get('engagement_rate', '?')}%\n"
        f"• Fréquence : ~{data.get('posts_per_week', '?')} posts/semaine\n\n"
        f"🎬 MIX CONTENU\n{content_mix}\n\n"
        f"📅 MEILLEURS JOURS\n{best_days}\n\n"
        f"🕐 MEILLEURES HEURES\n{best_hours}\n\n"
        f"🏆 TOP 3 POSTS (engagement)\n{top_posts_text}\n\n"
        f"#️⃣ HASHTAGS RÉCURRENTS\n{top_tags}\n\n"
        f"📝 STYLE CAPTIONS (moy. {data.get('avg_caption_len', '?')} chars)\n{recent_caps}"
    )
