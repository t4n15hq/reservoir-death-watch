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
**Status:** superseded by the 2026-05-18 CWC single-bulletin calibration below.

### 2026-05-18: Phase 0 CWC source access

**Context:** The official RSMS CWC PDF endpoint is visible in search/web previews, but direct `curl` from this environment receives 401 responses. A full automated latest-bulletin downloader may need cookies or a public mirror.
**Options considered:**
- Block Phase 0 until live PDF download is solved.
- Check in the official Phase 0 rows from `bulletin-09-04-2026-91.pdf` with source URL/line references, then keep parser support for local PDFs.
- Use CWC values from secondary sites. Rejected: CWC is the ground truth.
**Provisional answer:** Check in the official 09.04.2026 rows for KRS, Mettur, and Indira Sagar as Phase 0 calibration input, while keeping `parse_bulletin_pdf` and alias support ready for local PDFs. Flag output with `phase0_cwc_validation_incomplete` until six-month CWC history is loaded.
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

### 2026-05-18: Phase 0 volume before CWC calibration

**Context:** The first Earth Engine run can produce real surface-area observations before the CWC scraper/history is wired into area-volume calibration. The dashboard schema expects storage and percent-full fields, but the CWC-calibrated hypsometric curve does not exist yet.
**Options considered:**
- Leave volume fields empty: honest, but requires a schema break and makes the dashboard contract harder to exercise.
- Copy current CWC storage into estimated storage: misleading because it is not satellite-derived.
- Use an area-ratio proxy from current area / first-pass AOI area × full-pool capacity, with explicit flags.
**Provisional answer:** Use the area-ratio proxy only in Phase 0 output and flag every reservoir with `needs_cwc_calibration` and `volume_area_ratio_proxy`. The Phase 0 gate is not passed until CWC validation replaces this.
**Status:** open

---

## Resolved

(none yet)
