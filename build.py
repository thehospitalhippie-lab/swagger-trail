#!/usr/bin/env python3
"""Build The Swagger Trail blog into docs/ (served by GitHub Pages).

Reads config.json and posts/*.md (front matter + markdown). Writes:
  docs/index.html            the trail: every published post, grouped by stop
  docs/<slug>/index.html     one page per post
  docs/feed.xml              RSS feed (newest first)
  docs/style.css             copied from static/
"""
import html
import json
import re
import shutil
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import markdown
import yaml

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config.json").read_text())
OUT = ROOT / "docs"
TZ = ZoneInfo("America/Chicago")

STOPS = [
    "Trailhead", "Stop 1 — Head", "Stop 2 — Shoulder", "Stop 3 — Heart",
    "Stop 4 — Arms", "Stop 5 — Belly", "Stop 6 — Hips",
    "Stop 7 — Legs & Stride", "Summit — Toes",
]


def url(path=""):
    return CFG["base_path"].rstrip("/") + "/" + path.lstrip("/")


def abs_url(path=""):
    return CFG["site_url"].rstrip("/") + url(path)


def load_posts():
    posts = []
    for f in sorted((ROOT / "posts").glob("*.md")):
        raw = f.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
        if not m:
            raise SystemExit(f"{f.name}: missing front matter")
        meta = yaml.safe_load(m.group(1))
        meta["body_md"] = m.group(2).strip()
        meta["html"] = markdown.markdown(meta["body_md"], extensions=["extra", "sane_lists", "smarty"])
        words = len(re.findall(r"\w+", meta["body_md"]))
        meta["minutes"] = max(1, round(words / 230))
        meta["dt"] = datetime.strptime(meta["date"], "%Y-%m-%d").replace(hour=8, tzinfo=TZ)
        meta["sort"] = tuple(int(x) for x in str(meta["number"]).split("."))
        posts.append(meta)
    posts.sort(key=lambda p: p["sort"])
    return posts


def page(title, body, description, canonical, og_type="website", extra_head=""):
    t = html.escape(title)
    d = html.escape(description)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="{html.escape(CFG['title'])}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{d}">
{extra_head}<link rel="alternate" type="application/rss+xml" title="{html.escape(CFG['title'])}" href="{url('feed.xml')}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Shrikhand&family=Work+Sans:ital,wght@0,400;0,600;0,700;1,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{url('style.css')}">
</head>
<body>
<header class="site">
  <a class="brand" href="{url()}">{html.escape(CFG['title'])}</a>
  <span class="from">{html.escape(CFG['tagline'])}</span>
</header>
<main>
{body}
</main>
<footer class="site">
  <p>{html.escape(CFG['footer'])}</p>
  <p><a href="{url('feed.xml')}">RSS</a> · <a href="{html.escape(CFG['trail_map_url'])}">The trail map</a></p>
</footer>
</body>
</html>
"""


def seo_head(p, desc, canonical):
    """Keywords, article tags and schema.org BlogPosting data from the doc's SEO notes."""
    kws = [str(k) for k in (p.get("keywords") or [])]
    head = f'<meta property="article:published_time" content="{p["dt"].isoformat()}">\n'
    head += f'<meta property="article:section" content="{html.escape(p["stop"])}">\n'
    if kws:
        head += f'<meta name="keywords" content="{html.escape(", ".join(kws))}">\n'
        head += "".join(f'<meta property="article:tag" content="{html.escape(k)}">\n' for k in kws)
    data = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": p["title"],
        "description": desc,
        "datePublished": p["dt"].isoformat(),
        "url": canonical,
        "mainEntityOfPage": canonical,
        "author": {"@type": "Person", "name": CFG.get("author", "The Hospital Hippie")},
        "isPartOf": {"@type": "Blog", "name": CFG["title"], "url": abs_url()},
        "wordCount": len(re.findall(r"\w+", p["body_md"])),
    }
    if kws:
        data["keywords"] = kws
    ld = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return head + f'<script type="application/ld+json">{ld}</script>\n'


def build_map(posts):
    """docs/map/index.html: the whole head-to-toe trail, public. Published stops link; the rest show their date."""
    from datetime import date, timedelta
    data = json.loads((ROOT / "trail.json").read_text(encoding="utf-8"))
    start = date.fromisoformat(data["start"])
    live = {str(p["number"]): p for p in posts}
    sections, done = "", 0
    for stop in STOPS:
        items = ""
        for t in [t for t in data["posts"] if t["stop"] == stop]:
            k = t["order"]
            when = start + timedelta(days=7 * ((k - 1) // 2) + (0 if k % 2 else 2))
            p = live.get(t["number"])
            if p:
                done += 1
                items += (f'<li class="walked"><a href="{url(p["slug"] + "/")}"><span class="num">{t["number"]}</span>'
                          f'<span class="t">{html.escape(t["title"])}</span></a>'
                          f'<span class="meta">Walked {p["dt"]:%b %-d, %Y} · {p["minutes"]} min read</span></li>')
            else:
                items += (f'<li class="ahead"><span class="row"><span class="num">{t["number"]}</span>'
                          f'<span class="t">{html.escape(t["title"])}</span></span>'
                          f'<span class="meta">Coming {when:%a, %b %-d}</span></li>')
        sections += (f'<section class="stop"><h2><span class="dot" aria-hidden="true"></span>{html.escape(stop)}</h2>'
                     f'<ol class="posts trail">{items}</ol></section>')
    total = len(data["posts"])
    body = f"""<section class="hero">
<p class="kicker">The Swagger Trail map · head to toe</p>
<h1>Nine stops. Forty posts. One walk.</h1>
<p class="lede">Start at your head, end at your toes. A new stop opens every Tuesday and Thursday.</p>
<p class="latest">{done} of {total} posts walked so far.</p>
<div class="progress" role="img" aria-label="{done} of {total} posts published"><span style="width:{100 * done / total:.1f}%"></span></div>
</section>
{sections}
<p class="back"><a href="{url()}">Back to the trail home</a></p>"""
    d = OUT / "map"; d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(page(f"The Trail Map · {CFG['title']}",
        body, "The whole Swagger Trail, head to toe: nine stops, forty posts from American Swagger, two a week.",
        abs_url("map/")), encoding="utf-8")


def post_card(p):
    return (f'<li><a href="{url(p["slug"] + "/")}"><span class="num">{p["number"]}</span>'
            f'<span class="t">{html.escape(p["title"])}</span></a>'
            f'<span class="meta">{p["dt"]:%b %-d, %Y} · {p["minutes"]} min</span></li>')


def build():
    posts = load_posts()
    if OUT.exists():
        for child in OUT.iterdir():
            if child.name in ("CNAME", ".nojekyll"):
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    OUT.mkdir(exist_ok=True)
    (OUT / ".nojekyll").write_text("")
    shutil.copy(ROOT / "static" / "style.css", OUT / "style.css")

    # Post pages
    for i, p in enumerate(posts):
        prev_p = posts[i - 1] if i > 0 else None
        next_p = posts[i + 1] if i + 1 < len(posts) else None
        nav = '<nav class="pager">'
        nav += (f'<a class="prev" href="{url(prev_p["slug"] + "/")}">← {html.escape(prev_p["title"])}</a>'
                if prev_p else "<span></span>")
        nav += (f'<a class="next" href="{url(next_p["slug"] + "/")}">{html.escape(next_p["title"])} →</a>'
                if next_p else '<span class="soon">Next stop drops soon. <a href="'
                + url("feed.xml") + '">Follow the trail</a>.</span>')
        nav += "</nav>"
        body = f"""<article class="post">
<p class="kicker"><span class="pill">{html.escape(p['stop'])}</span> Post {p['number']} · {p['dt']:%B %-d, %Y} · {p['minutes']} min read</p>
<h1>{html.escape(p['title'])}</h1>
<div class="prose">
{p['html']}
</div>
</article>
{nav}
<p class="back"><a href="{url()}">See the whole trail</a></p>"""
        desc = p.get("description") or (
            re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", p["html"]))[:155].rsplit(" ", 1)[0] + "…")
        canonical = abs_url(p["slug"] + "/")
        d = OUT / p["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            page(f"{p['title']} · {CFG['title']}", body, desc, canonical, "article", seo_head(p, desc, canonical)),
            encoding="utf-8")
        p["desc"] = desc

    # Index: grouped by stop, in trail order
    groups = ""
    for stop in STOPS:
        here = [p for p in posts if p["stop"] == stop]
        if here:
            groups += (f'<section class="stop"><h2>{html.escape(stop)}</h2><ol class="posts">'
                       + "".join(post_card(p) for p in here) + "</ol></section>")
    latest = posts[-1] if posts else None
    hero_latest = (f'<p class="latest">Newest: <a href="{url(latest["slug"] + "/")}">'
                   f'{html.escape(latest["title"])}</a></p>') if latest else \
        '<p class="latest">The first stop drops soon.</p>'
    index_body = f"""<section class="hero">
<p class="kicker">From the book <em>American Swagger</em> · Q Word Out Loud</p>
<h1>{html.escape(CFG['hero'])}</h1>
<p class="lede">{html.escape(CFG['lede'])}</p>
{hero_latest}
<p><a class="button" href="{html.escape(CFG['trail_map_url'])}">Open the head-to-toe trail map</a></p>
</section>
{groups}"""
    (OUT / "index.html").write_text(
        page(CFG["title"], index_body, CFG["lede"], abs_url()), encoding="utf-8")

    build_map(posts)

    # RSS
    items = ""
    for p in reversed(posts):
        link = abs_url(p["slug"] + "/")
        items += (f"<item><title>{html.escape(p['title'])}</title><link>{link}</link>"
                  f"<guid isPermaLink=\"true\">{link}</guid>"
                  f"<pubDate>{format_datetime(p['dt'])}</pubDate>"
                  f"<description>{html.escape(p['html'])}</description></item>")
    rss = (f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
           f"<title>{html.escape(CFG['title'])}</title><link>{abs_url()}</link>"
           f"<description>{html.escape(CFG['lede'])}</description><language>en-us</language>"
           f"{items}</channel></rss>")
    (OUT / "feed.xml").write_text(rss, encoding="utf-8")

    # Sitemap + robots, so search engines find each new stop
    urls = [(abs_url(), posts[-1]["date"] if posts else None), (abs_url("map/"), posts[-1]["date"] if posts else None)] + [(abs_url(p["slug"] + "/"), p["date"]) for p in posts]
    sm = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    for loc, last in urls:
        sm += f"<url><loc>{loc}</loc>" + (f"<lastmod>{last}</lastmod>" if last else "") + "</url>"
    (OUT / "sitemap.xml").write_text(sm + "</urlset>", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {abs_url('sitemap.xml')}\n", encoding="utf-8")
    print(f"built {len(posts)} post(s) into docs/")


if __name__ == "__main__":
    build()
