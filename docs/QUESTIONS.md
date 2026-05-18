# Open Questions

Agents write to this file when they hit a fork the docs don't cover. Tanishq reviews and resolves.

**Format:**

```
## YYYY-MM-DD: Short question title

**Context:** What forked.
**Options considered:** A, B, C with quick pros/cons.
**Provisional answer:** What I went with. (Marks the work as proceeding under this assumption.)
**Status:** open | resolved | superseded
```

When `status: resolved`, append the resolution and move the question to the bottom under a `## Resolved` heading.

---

## Open

### 2026-05-18: Domain name

**Context:** Need a public URL before Phase 4 (writeup distribution).
**Options:**
- `reservoirs.tanishq.dev` — uses existing personal subdomain pattern
- `indiawater.live` — better SEO, more memorable, but needs separate registration and renewal
- `reservoirwatch.in` — .in feels right for India focus

**Provisional answer:** `reservoirs.tanishq.dev` for Phase 1–3 (no domain shopping needed). Decide on a vanity domain before Phase 4.
**Status:** open

---

### 2026-05-18: Repo visibility

**Context:** Public from day 0 or private until Phase 3?
**Options:**
- Public from day 0: legitimacy when sharing, accountability for code quality, possible early collaborators
- Private until Phase 3: cleaner first commits, less pressure during the messy middle

**Provisional answer:** Private until Phase 1 backtests pass; public after.
**Status:** open

---

### 2026-05-18: Astro vs separate dashboard/site

**Context:** Should the interactive dashboard and the writeup site live as one Astro project (with islands) or two separate projects?
**Options:**
- One Astro project, dashboard as islands: simpler deploy, single domain, single repo
- Two projects (Astro for site, Vite for dashboard): cleaner separation, dashboard can iterate faster

**Provisional answer:** One Astro project with islands. Simpler.
**Status:** open

---

## Resolved

(none yet)
