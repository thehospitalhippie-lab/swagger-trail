#!/usr/bin/env python3
"""Turn a draft exported from Google Docs (markdown) into a publishable post.

Usage: python3 tools/convert.py <draft.md> <post_number> <stop> <title> <date YYYY-MM-DD>
Writes posts/<post_number>.md with front matter and only the reader-facing text.

Keeps: everything under "## Draft" up to the next "## " heading.
Drops: the working header, headline options, "SEO notes", "Editing flags", and
any line in [square-bracket placeholders] (those make the check fail instead).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def extract_draft(text: str) -> str:
    text = text.replace("\\+", "+").replace("\\#", "#").replace("\\!", "!")
    lines = text.splitlines()
    out, inside = [], False
    for line in lines:
        if re.match(r"^##\s+Draft\s*$", line):
            inside = True
            continue
        if inside and re.match(r"^##\s+\S", line):
            break
        if inside:
            out.append(line.rstrip())
    body = "\n".join(out).strip()
    # Drafts use ### / #### under "## Draft"; lift them one level for the page.
    body = re.sub(r"^(#{3,6})\s", lambda m: "#" * (len(m.group(1)) - 1) + " ", body, flags=re.M)
    # Google Docs adds two-space hard breaks inside lists; drop them.
    body = re.sub(r"  +$", "", body, flags=re.M)
    return body + "\n"


def main():
    if len(sys.argv) != 6:
        sys.exit(__doc__)
    src, num, stop, title, date = sys.argv[1:]
    body = extract_draft(Path(src).read_text(encoding="utf-8"))
    if len(body.split()) < 300:
        sys.exit(f"Draft section for {num} is missing or too short ({len(body.split())} words).")
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:70].strip("-")
    fm = (
        "---\n"
        f'number: "{num}"\n'
        f'stop: "{stop}"\n'
        f'title: "{title.replace(chr(34), chr(39))}"\n'
        f'date: "{date}"\n'
        f'slug: "{slug}"\n'
        "---\n\n"
    )
    out = ROOT / "posts" / f"{num}.md"
    out.write_text(fm + body, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(body.split())} words) slug={slug}")


if __name__ == "__main__":
    main()
