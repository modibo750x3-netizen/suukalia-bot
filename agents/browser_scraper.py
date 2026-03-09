"""
Instagram visual scraper using Playwright.
Opens Chromium, navigates to a public IG profile, takes screenshots,
extracts DOM data (bio, post count, captions, likes/views if visible).

Requires: playwright install chromium --with-deps
Optional env vars (for authenticated access):
  IG_SESSION_ID  — value of the 'sessionid' cookie from your IG session
  IG_DS_USER_ID  — value of the 'ds_user_id' cookie
"""

import asyncio
import logging
import os
import re

logger = logging.getLogger(__name__)


def extract_username_from_raw(raw: str) -> str:
    """Accept @handle, full URL, or bare username. Returns clean lowercase username."""
    s = raw.strip().rstrip("/")
    m = re.search(r'instagram\.com/([A-Za-z0-9._]+)', s)
    if m:
        return m.group(1).lower()
    return s.lstrip("@").lower()


# ── Playwright scrape ──────────────────────────────────────────────────────────

async def scrape_visual(username: str, max_posts: int = 10) -> dict:
    """
    Open Instagram profile in headless Chromium, take screenshots,
    extract visible DOM data.  Returns dict with screenshots + text.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"username": username, "error": "playwright_not_installed", "screenshots": []}

    screenshots: list[tuple[str, bytes]] = []
    extracted: dict = {"username": username, "screenshots": []}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        ctx = await browser.new_context(
            viewport={"width": 390, "height": 844},   # iPhone 14 viewport
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ),
            locale="fr-FR",
        )

        # Inject optional IG session cookies for authenticated access
        session_id = os.environ.get("IG_SESSION_ID", "").strip()
        ds_user_id = os.environ.get("IG_DS_USER_ID", "").strip()
        if session_id:
            await ctx.add_cookies([
                {"name": "sessionid",  "value": session_id,  "domain": ".instagram.com", "path": "/"},
                {"name": "ds_user_id", "value": ds_user_id,  "domain": ".instagram.com", "path": "/"},
                {"name": "ig_did",     "value": "anonymous", "domain": ".instagram.com", "path": "/"},
            ])

        page = await ctx.new_page()

        # Suppress unnecessary requests (images, fonts) to speed things up
        await page.route("**/*.{woff,woff2,ttf,otf,eot}", lambda r: r.abort())

        try:
            await page.goto(
                f"https://www.instagram.com/{username}/",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            await asyncio.sleep(3)  # let lazy content load

            # Detect login wall
            current_url = page.url
            if "accounts/login" in current_url or "challenge" in current_url:
                extracted["login_wall"] = True
            else:
                extracted["login_wall"] = False

            # 1. Screenshot the profile header + post grid
            shot = await page.screenshot(full_page=False, type="png")
            screenshots.append(("profile_grid", shot))

            # 2. Scroll down a bit to reveal more posts
            await page.evaluate("window.scrollBy(0, 600)")
            await asyncio.sleep(1)
            shot2 = await page.screenshot(full_page=False, type="png")
            screenshots.append(("profile_grid_2", shot2))

            # 3. Extract DOM text data
            profile_info = await page.evaluate("""() => {
                const getText = (sel) => {
                    const el = document.querySelector(sel);
                    return el ? el.innerText.trim() : null;
                };
                const getAllText = (sel) => [...document.querySelectorAll(sel)]
                    .map(e => e.innerText.trim()).filter(Boolean);

                // Follower/following counts are in meta description or visible spans
                const meta = document.querySelector('meta[name="description"]');
                const metaContent = meta ? meta.content : '';

                // Try to find post links
                const postLinks = [...document.querySelectorAll('a[href*="/p/"]')]
                    .map(a => a.href)
                    .filter((v, i, arr) => arr.indexOf(v) === i)
                    .slice(0, 10);

                // Any visible text with like/view counts
                const allSpans = getAllText('span');

                return {
                    title: document.title,
                    metaDescription: metaContent,
                    postLinks: postLinks,
                    visibleText: allSpans.slice(0, 40),
                };
            }""")
            extracted["profile_info"] = profile_info

            # 4. Try to visit up to 3 individual posts and screenshot
            post_links = (profile_info or {}).get("postLinks", [])[:3]
            for i, link in enumerate(post_links):
                try:
                    await page.goto(link, wait_until="domcontentloaded", timeout=20_000)
                    await asyncio.sleep(2)
                    post_shot = await page.screenshot(full_page=False, type="png")
                    screenshots.append((f"post_{i+1}", post_shot))

                    # Extract post text
                    post_text = await page.evaluate("""() => {
                        const spans = [...document.querySelectorAll('span')].map(e => e.innerText.trim());
                        return spans.filter(s => s.length > 10).slice(0, 20);
                    }""")
                    extracted.setdefault("post_texts", []).append(post_text)
                except Exception as e:
                    logger.debug("Post screenshot failed for %s: %s", link, e)

        except Exception as exc:
            logger.warning("Browser scrape error for @%s: %s", username, exc)
            extracted["error"] = str(exc)
        finally:
            await browser.close()

    extracted["screenshots"] = screenshots
    return extracted


# ── Text summary builder ───────────────────────────────────────────────────────

def format_extracted(data: dict) -> str:
    """Build a text summary of the scraped DOM data."""
    u = data.get("username", "?")
    login_wall = data.get("login_wall")

    lines = [f"Profil visuel @{u} — données extraites du browser"]

    if login_wall:
        lines.append("⚠️ Instagram a affiché un mur de connexion. Données limitées.")
        lines.append("Configure IG_SESSION_ID pour l'accès complet.")
    elif data.get("error"):
        lines.append(f"⚠️ Erreur browser : {data['error']}")

    info = data.get("profile_info") or {}
    if info.get("metaDescription"):
        lines.append(f"Meta : {info['metaDescription'][:200]}")

    posts = data.get("post_texts", [])
    if posts:
        lines.append(f"\n{len(posts)} posts visitées. Extraits :")
        for i, texts in enumerate(posts, 1):
            sample = " | ".join(texts[:5])
            lines.append(f"  Post {i}: {sample[:200]}")

    n_shots = len(data.get("screenshots", []))
    lines.append(f"\n{n_shots} screenshot(s) pris — envoyés à Marcus pour analyse visuelle.")
    return "\n".join(lines)
