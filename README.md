# The Swagger Trail

The blog edition of *American Swagger*: a head-to-toe walk, two stops a week. Served by GitHub Pages from `docs/`.

- `posts/` — published posts (markdown with front matter), added by the publishing task
- `tools/convert.py` — turns a Google Docs draft export into a post (keeps only the `## Draft` section)
- `tools/check.py` — blocks publishing if a post still has placeholders or working notes
- `build.py` — builds `docs/` (home page, post pages, RSS)

The queue lives in the Google Sheet "00 · The Swagger Trail — Publishing Queue". Only rows marked Ready get published, in order.
