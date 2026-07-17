# Rhythmiq Frontend v1 — Meet-Day Scoring + Admin Console

**Date:** 2026-07-16
**Status:** Approved design, pending implementation plan

## Context

Rhythmiq's FastAPI backend is feature-complete for core meet management (12 CRUD
resources + read-only results router), but the only UI is `/docs`. The long-term
vision is a full product: admin console, meet-day scoring, public results, and
eventually judges entering their own scores live from assigned stations (D1, E2, …)
with view-all/edit-own permissions. This spec covers v1 in two phases, both operated
by a single trusted user: **Phase 1 — meet-day scoring** (a scorekeeper running a
meet), **Phase 2 — admin console** (full reference-data management, replacing `/docs`
for data entry).

## Decisions

| Decision | Choice |
|---|---|
| V1 scope | Phase 1: meet-day scoring (picker, entries, scoring, standings, status controls). Phase 2: admin console over all reference resources + meet create/edit |
| Build order | Scoring first — seed data covers reference data until Phase 2; admin reuses components the scoring screens create |
| Stack | React 19 + Vite + TypeScript (strict), npm |
| Libraries | TanStack Query, React Router, React Hook Form + Zod, Tailwind CSS, openapi-typescript + openapi-fetch |
| Auth | None in v1 — single trusted scorekeeper, same trust model as the API today |
| Live updates | Polling (TanStack Query `refetchInterval`, ~5s), no WebSockets |
| Backend changes | None, except a script to export `openapi.json` |
| Deployment | Out of scope — dev-mode only (uvicorn + Vite on one laptop) |
| Build split | Claude builds v1 directly (explicit user choice, exception to tutor mode); user studies it and takes over later phases |

Approaches considered and rejected: HTMX/Jinja (live fragment swaps fight in-progress
judge input; no typed contract), SvelteKit (nicer code, thinner ecosystem), Next.js
(SSR machinery redundant next to FastAPI), Refine/React-Admin (wraps the libraries
worth learning; no help for the scoring screen), minimal hand-rolled SPA (hand-rolled
fetching is where SPAs rot).

## Architecture

```
frontend/
  src/
    api/            # generated schema.d.ts + openapi-fetch client setup
    features/       # one folder per screen: meets/, entries/, scoring/, standings/, admin/
    components/     # shared UI (layout shell, form fields, tables, toasts)
    lib/            # query client, computed-score helpers
  vite.config.ts    # dev proxy: /api/* -> http://127.0.0.1:8000 (prefix stripped)
```

- **Dev workflow:** two processes — uvicorn on 8000, Vite on 5173. The Vite proxy
  forwards `/api/*` to FastAPI with the prefix stripped; the browser sees one origin,
  so no CORS configuration is needed and the backend is untouched.
- **Type generation:** `backend/scripts/export_openapi.py` dumps `app.openapi()` to
  JSON without a running server; `npm run generate` feeds it to `openapi-typescript`.
  The generated `schema.d.ts` is **committed** (same philosophy as committed Alembic
  migrations: generated artifacts are reviewable in diffs). A `make` target chains
  export + generate.
- **Data flow:** all server state through TanStack Query, keyed by URL params.
  Mutations invalidate the affected queries (a score save invalidates that routine's
  scores and the standings query). Form state belongs to React Hook Form and is never
  clobbered by background refetches.

## Screens

| Route | Screen | Phase |
|---|---|---|
| `/` | Meet list — pick a meet; status badge per meet | 1 |
| `/meets/:meetId` | Meet shell — header (name, dates, status controls), tabs | 1 |
| `/meets/:meetId/entries` | Entry list + create/delete entries | 1 |
| `/meets/:meetId/scoring` | Quick-entry scoring (the core screen) | 1 |
| `/meets/:meetId/standings` | Live standings | 1 |
| `/admin/:resource` | Generic list + create/edit/delete per resource (see Admin console) | 2 |

### Quick-entry scoring (core screen)

Layout validated via mockups (see `.superpowers/brainstorm/` session 2026-07-16):

- **Left panel:** competitor list for the meet, filtered by level + apparatus,
  searchable by name or bib. Already-scored entries show a check + total; the current
  competitor is highlighted. Selecting a competitor loads their routine for the
  selected apparatus.
- **Score boxes, in order:** `D-Body · D-App · Artistry | E1 · E2 · E3 · E4 · Penalty`.
  Always 4 E boxes regardless of how many E judges are assigned (unassigned-slot boxes
  render disabled with a hint). For levels 1–7 (`E_ONLY_LEVELS` in `scoring.py`) only
  the E boxes and Penalty render — no D or A.
- **Computed preview bar** under the boxes, same order (D, A, E, penalty, total),
  recomputed client-side as values are typed: E uses trimmed mean at ≥4 scores, plain
  average below (mirroring `scoring.py`); server-computed standings remain the source
  of truth.
- **Buttons:** "Save & next" (Enter) jumps to the next unscored competitor; plain
  "Save" stays. Tab moves between boxes; values snap to 0.05.

### Judge panel setup (per meet, one-time)

Every `JudgeScore` row requires a `judge_id`, but quick-entry boxes don't name judges.
Resolution: a per-meet **panel setup** dialog maps slots `D, E1–E4, A` to judges
(dropdowns over the Judge resource). One D judge covers both D boxes — legal under
`uq_judge_score_routine_judge_panel` since the panels differ; separate DB/DA slots can
be added later without changing the scoring form. The mapping is stored in
`localStorage` for v1 (no backend change); it is the deliberate seed of the future
judge-stations model, at which point it moves server-side with auth.

### Entries screen

List (bib, competitor, level, age group) plus create and delete. No edit form: the API
forbids FK updates on `MeetEntry`, so correction = delete + recreate. The create form
enforces exactly-one-of gymnast/group and surfaces bib-uniqueness 409s inline.
Requires read access to gymnasts, groups, and clubs for the pickers.

### Standings screen

Per-apparatus / all-around toggle, level + age-group filters, auto-refresh every ~5s
(paused when the tab is hidden — TanStack Query default). Shows rank ties per
competition ranking (1,2,2,4), `routines_counted` for partial all-around totals, and a
"provisional" badge until `meet.status == completed`.

### Meet status controls

The meet header offers only transitions valid from the current status (mirroring
`ALLOWED_STATUS_TRANSITIONS` in `routers/meet.py` — e.g. draft shows Schedule/Cancel,
never Complete), with a confirmation dialog on `completed` since that freezes scores.

### Admin console (Phase 2)

All resource routers share the same CRUD shape, so the admin console is built as one
**generic layer** — a resource data-table (list + filters from the router's query
params) and a form dialog (create/edit) — driven by a per-resource config object
(columns, form fields, filters, immutable fields). Each resource is then declarative
config plus its quirks:

- **Resources:** districts, clubs, coaches, gymnasts, groups, judges, routine
  profiles, and meets (create + edit of name/location/dates/district/medal minima —
  status still changes only via the meet-shell controls). Group membership is managed
  via the gymnast form's `group_id` field, not a separate screen.
- **Navigation:** an Admin section in the app shell with a sidebar listing the
  resources, ordered by dependency (district → club → coach/group/gymnast → judge →
  routine profile → meet).
- **API rules surfaced, not duplicated:** RESTRICT-delete rejections (409 with
  dependents) and uniqueness violations show the API's `detail` as a toast/inline
  error; abbreviation uppercasing is left to the server (the form shows the saved
  value). RoutineProfile's create form enforces exactly-one-of gymnast/group and its
  edit form only offers `music_url`/`choreography_notes`, mirroring the API's
  updatable-field rules.
- **FK pickers:** dropdowns/comboboxes populated from the parent resource's list
  endpoint (e.g. club picker filtered by district), reusing the same pickers the
  Phase 1 entry-create form builds.

## Save semantics & error handling

- **Routine rows are created lazily by the scoring screen.** A `Routine` is one row
  per (entry, apparatus); nothing else in the v1 UI creates them. If the selected
  competitor has no routine for the selected apparatus yet, the first save POSTs one,
  then writes the scores against it. The competitor list treats "no routine" and
  "routine with no scores" identically (unscored).
- A quick-entry save is **up to 7 JudgeScore writes + a `Routine.penalty` PATCH**, not
  one call. The form diffs against loaded state: changed box → PATCH (existing row) or
  POST (new); cleared box → DELETE. On partial failure the failing box shows an inline
  error while successful writes stand; the user fixes and re-saves. Pragmatic, not
  atomic — acceptable for a single attended scorekeeper.
- Each box maps to exactly one `JudgeScore` row via (routine, judge-from-slot, panel)
  uniqueness, so create-vs-update-vs-delete per box is unambiguous.
- **Validation mirrors DB constraints in Zod:** 0.05 increments everywhere; E/A capped
  at 10, D panels uncapped (`ck_judge_score_panel_value_cap`); penalty ≥ 0. The API
  stays the enforcer; surviving 409/404s surface as toasts showing the API `detail`.
- **State-dependent UI:** completed meets render read-only with a notice (mirrors
  backend freeze). The Penalty box disables with an explanation when the routine has
  itemized `PenaltyRecord`s (direct PATCH would 409 — "itemization takes over").
  Itemized-penalty UI itself is deferred.

## Testing

Vitest + React Testing Library + MSW (network-level API fakes so components exercise
their real fetch paths). Test layout mirrors `src/`, as `test/` mirrors `app/` in the
backend. Tests are written per screen as it's built, not batched.

Priority order:
1. Computed-preview math — pinned to the same worked examples as `scoring.py`
   (trimmed mean at 4, average below, E-only levels).
2. Save-diff logic — which boxes become POST / PATCH / DELETE.
3. Form validation — 0.05 snapping, caps, penalty rules.
4. Screen flows — pick competitor → enter → save & next; standings polling render;
   status controls offering only legal transitions.
5. Phase 2: the generic table/form layer gets thorough tests once (rendering from
   config, create/edit/delete flows, 409 surfacing); per-resource tests then only
   cover that resource's quirks (immutable fields, exactly-one-of, FK pickers).

Playwright end-to-end tests deferred.

## Deferred (explicitly out of v1)

- Auth, judge identities/logins, and judge self-scoring stations (view-all/edit-own) —
  requires backend auth + a server-side judge→station assignment model.
- Itemized `PenaltyRecord` UI.
- Public results pages, CSV export, team scores.
- Production build/deployment and CORS configuration.
- WebSockets — revisit only if sub-second synchronized score reveal is ever needed.
