#!/usr/bin/env python3
"""Refuse to publish anything that still carries working notes or placeholders.

Exit code 1 (and a list of problems) if any post in posts/ or page in docs/ has:
- a [bracketed placeholder] such as [Add ...], [Insert ...], [Embed ...], [YOUR ...]
- working-note sections: "Headline options", "SEO notes", "Editing flags", "Publishes "
- an internal link that points at a page that wasn't built
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BAD = [
    (re.compile(r"\[(?:Add|Insert|Embed|YOUR|TODO|TK)[^\]]*\]", re.I), "placeholder"),
    (re.compile(r"Headline options|SEO notes|Editing flags|Meta description:", re.I), "working note"),
    (re.compile(r"^Publishes (Mon|Tue|Wed|Thu|Fri|Sat|Sun)", re.M), "working header"),
]
problems = []
for f in sorted((ROOT / "posts").glob("*.md")):
    text = f.read_text(encoding="utf-8")
    for rx, label in BAD:
        for m in rx.finditer(text):
            problems.append(f"{f.name}: {label}: {m.group(0)[:60]}")

import json
base = json.loads((ROOT / "config.json").read_text())["base_path"].rstrip("/")
docs = ROOT / "docs"
for page in docs.rglob("*.html"):
    for href in re.findall(r'href="([^"]+)"', page.read_text(encoding="utf-8")):
        if href.startswith(base + "/"):
            rel = href[len(base) + 1:]
            target = docs / rel
            if rel == "" or rel.endswith("/"):
                target = target / "index.html"
            if not target.exists():
                problems.append(f"{page.relative_to(ROOT)}: broken link {href}")

# SEO notes are advisory: warn, never block.
import yaml
for f in sorted((ROOT / "posts").glob("*.md")):
    m = re.match(r"^---\n(.*?)\n---\n", f.read_text(encoding="utf-8"), re.S)
    meta = yaml.safe_load(m.group(1)) if m else {}
    if not meta.get("description"):
        print(f"note: {f.name} has no meta description in its SEO notes (an excerpt is used instead)")
    elif len(meta["description"]) > 160:
        print(f"note: {f.name} meta description is {len(meta['description'])} chars; Google shows about 155")

if problems:
    print("CHECK FAILED")
    print("\n".join(problems))
    sys.exit(1)
print("check passed")
