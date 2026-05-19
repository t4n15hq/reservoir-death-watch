# site/

Long-form writeup pages: methodology, launch blog post, per-reservoir CSV
download index. Per `docs/TDD.md` §6.2 this is intended to be an Astro
project hosted alongside the dashboard at the same domain. For Phase 3
the content lives here as portable Markdown so the Astro scaffold can
adopt it without rewrites.

## Files

- `src/content/methodology.md` — the long-form methodology, per
  `docs/PRD.md` §4 "what it shows / what it claims / what it does NOT".
- `src/content/launch-post.md` — the launch announcement, per
  `docs/PRD.md` §7 distribution plan. Drafted; not yet published.

## Phase 4 deliverables (per `docs/PHASES.md`)

- Astro project scaffold reading these markdown files.
- `/methodology` route rendering `methodology.md`.
- `/blog/launch` route rendering `launch-post.md`.
- `/data` route with per-reservoir CSV downloads.
- Twitter/X thread draft.
- Three journalist cold-email drafts.
- Hacker News submission ready.
