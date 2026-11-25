#!/usr/bin/env python3
"""Turn a draft exported from Google Docs (markdown) into a publishable post.

Usage: python3 tools/convert.py <draft.md> <post_number> <stop> <title> <date YYYY-MM-DD>
Writes posts/<post_number>.md with front matter and only the reader-facing text.

Reader-facing text:
  - everything under "## Draft" up to the next "## " heading, or, when a doc has
    no "## Draft" heading, everything after the "# Post ..." title up to the
    first "## " heading (skipping a "Publishes ..." line and headline options).
SEO (from the doc's "## SEO notes" section, never shown on the page):
  - "Meta description: ..."  -> description (search snippet + social previews)
  - "Primary keyword", "Secondary", "Branded term", "Keywords" -> keywords
Working notes ("Headline options", "SEO notes", "Editing flags") never publish.
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


MAP_URL = "https://thehospitalhippie-lab.github.io/swagger-trail/map/"


def clean(text: str) -> str:
    # The private Claude canvas map is replaced by the public map on the blog.
    text = text.replace("https://claude.ai/artifact/77uRe1nS3kwACLhxJFzA1Q", MAP_URL)
    return text.replace("\\+", "+").replace("\\#", "#").replace("\\!", "!").replace("\\-", "-")


def section(lines, heading_rx):
    out, inside = [], False
    for line in lines:
        if re.match(heading_rx, line):
            inside = True
            continue
        if inside and re.match(r"^##\s+\S", line):
            break
        if inside:
            out.append(line)
    return out if inside else None


def extract_draft(text: str) -> str:
    lines = clean(text).splitlines()
    out = section(lines, r"^##\s+Draft\s*$")
    if out is None:
        # No "## Draft" heading: take what follows the title, up to the first "## ".
        out, started, skipping_headlines = [], False, False
        for line in lines:
            if not started:
                if re.match(r"^#\s+\S", line):
                    started = True
                continue
            if re.match(r"^##\s+\S", line):
                break
            if re.match(r"^Publishes\s", line):
                continue
            if re.match(r"^\**Headline options\**\s*$", line.strip()):
                skipping_headlines = True
                continue
            if skipping_headlines:
                if line.strip() == "" or re.match(r"^\s*\d+\.\s", line):
                    continue
                skipping_headlines = False
            out.append(line)
    body = "\n".join(l.rstrip() for l in out).strip()
    # Drafts use ### / #### under the post title; lift them one level for the page.
    body = re.sub(r"^(#{3,6})\s", lambda m: "#" * (len(m.group(1)) - 1) + " ", body, flags=re.M)
    # Google Docs adds two-space hard breaks inside lists; drop them.
    body = re.sub(r"  +$", "", body, flags=re.M)
    return body + "\n"


def strip_md(s: str) -> str:
    s = re.sub(r"[*_`]", "", s)
    return re.sub(r"\s+", " ", s).strip().strip('"“”').strip()


def phrases(value: str):
    """Keyword phrases from a note line: the *italic* bits, else text before a dash/period."""
    found = [strip_md(p) for p in re.findall(r"\*([^*]+)\*", value)]
    found = [p.rstrip(".,;") for p in found if p.strip(" .")]
    if not found:
        head = re.split(r"\s[—–-]\s|\.\s|;", strip_md(value))[0]
        found = [p.strip() for p in head.split(",") if p.strip()]
    return found


def extract_seo(text: str):
    lines = section(clean(text).splitlines(), r"^##\s+SEO notes?\s*$") or []
    description, keywords = None, []
    for line in lines:
        m = re.match(r"^\s*[-*]\s+(?:\*\*)?([^:*]+?)(?:\*\*)?:\s*(.+)$", line)
        if not m:
            continue
        label, value = m.group(1).strip().lower(), m.group(2).strip()
        if label.startswith("meta description"):
            italic = re.findall(r"\*([^*]+)\*", value)
            description = strip_md(max(italic, key=len) if italic else value)
        elif any(k in label for k in ("keyword", "secondary", "branded term")):
            for p in phrases(value):
                if p.lower() not in (k.lower() for k in keywords):
                    keywords.append(p)
    return description, keywords


def main():
    if len(sys.argv) != 6:
        sys.exit(__doc__)
    src, num, stop, title, date = sys.argv[1:]
    raw = Path(src).read_text(encoding="utf-8")
    body = extract_draft(raw)
    if len(body.split()) < 300:
        sys.exit(f"Draft section for {num} is missing or too short ({len(body.split())} words).")
    description, keywords = extract_seo(raw)
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:70].strip("-")
    meta = {"number": str(num), "stop": stop, "title": title, "date": date, "slug": slug}
    if description:
        meta["description"] = description
    if keywords:
        meta["keywords"] = keywords
    fm = "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=1000) + "---\n\n"
    out = ROOT / "posts" / f"{num}.md"
    out.write_text(fm + body, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(body.split())} words) slug={slug}")
    print(f"seo: description={'yes' if description else 'MISSING'} ({len(description or '')} chars), "
          f"keywords={keywords or 'none'}")


if __name__ == "__main__":
    main()
