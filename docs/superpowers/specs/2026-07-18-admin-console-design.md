# Admin Console (Phase 2) — Design

Date: 2026-07-18
Status: approved, ready for planning

Phase 1 (meet-day scoring SPA) shipped in PR #4 and the scoring-polish batch in PR #5.
Phase 2 replaces `/docs` as the way reference data gets entered, starting with the
competitor chain: **District → Club → Coach → Group → Gymnast**.

## Decisions

| Decision | Choice |
|---|---|
| Scope | Districts, Clubs, Coaches, Groups, Gymnasts. Judges, RoutineProfiles and Meet create/edit deferred to Phase 2b |
| Abstraction | Two hand-written pilots first, then extract the shared layer from real duplication — not a config-driven layer designed up front |
| Pilot pair | District (simplest: 2 text fields, no FK) + Gymnast (hardest: 2 optional FKs, nullable date, nullable country code, club filter) |
| Create/edit UX | Modal dialog over the list; one form component serves both create and edit |
| Navigation | Admin sub-shell with a sidebar, resources in dependency order |
| Delete UX | Confirm dialog → DELETE → surface the API's 409 `detail`; no client-side prediction of dependents |
| Build split | Claude builds Phase 2 (user's explicit choice, extending the Phase 1 exception to tutor mode) |
| Backend changes | None |

Approaches considered and rejected: a config-driven generic table+form layer designed
up front (the v1 spec's sketch — rejected because the five resources diverge on
validation, nullability and immutability, which config objects handle badly); no shared
layer at all (5× boilerplate, 5 places to fix a shared bug); inline row editing (fastest
for bulk entry, but 5–6 fields per row and in-row error display are unworkable);
separate form routes (deep-linkable but loses list context for a 4-field edit);
drill-down district→club→gymnast hierarchy (matches the mental model but makes a flat
"every gymnast" view impossible and doubles the routes); client-side pre-checking of
delete dependents (re-implements `RESTRICT` semantics in TypeScript, where a backend FK
change would silently make the UI lie).

## Routes

```
/                          meet list          (existing)
/meets/:meetId/*           meet shell         (existing)
/admin                     redirect to /admin/districts
/admin/:resource           AdminShell + one resource page
```

`AdminShell` is a sibling of `MeetShell`: a sidebar listing the five resources in
dependency order (Districts → Clubs → Coaches → Groups → Gymnasts) with `<Outlet />` on
the right. `Layout.tsx` grows a two-link nav (Meets / Admin); today it is a single
"Rhythmiq" home link.

## Build order

Three stages, each independently mergeable.

### Stage A — two hand-written pilots

`features/admin/districts/DistrictsPage.tsx` and `features/admin/gymnasts/GymnastsPage.tsx`,
each self-contained in the Phase 1 idiom (TanStack Query list + React Hook Form + Zod +
`client.POST/PATCH/DELETE`, `ErrorBanner` for server errors). No shared abstraction yet —
the duplication is deliberate. Both fully tested.

Building the extremes rather than the two simplest resources means the layer meets its
worst case immediately. An abstraction extracted from two near-twins (District + Club,
both `name` + `abbreviation`) would not survive Gymnast's optional FKs and nullable date.

### Stage B — extract

Extract only what is demonstrably shared by the two pilots:

| Extracted | Responsibility |
|---|---|
| `ResourceTable` | renders `{header, render}[]` columns plus Edit/Delete action cells |
| `FormDialog` | `<dialog>` shell, focus trap, Escape/Cancel, pending state |
| `DeleteConfirm` | confirm → mutate → surface the 409 `detail` |
| `useResourceList` | list query + client-side search predicate |
| `FkSelect` | FK dropdown fed by a parent list query, with `— none —` for nullable FKs |

**The forms themselves stay hand-written per resource.** This is the load-bearing
boundary of the design: tables and dialogs are structurally identical across resources,
but forms are only superficially similar — they diverge on validation, nullability and
immutability. Each resource keeps its own ~40-line RHF form and composes the shared
shell around it. A config-driven field renderer is where this kind of layer rots.

### Stage C — roll out the rest

Clubs, Coaches and Groups on the extracted pieces. If a resource fights the abstraction,
that is a signal to fix the abstraction, not to add a flag to it.

## File shape after Stage C

```
src/features/admin/
  AdminShell.tsx
  components/   ResourceTable.tsx  FormDialog.tsx  DeleteConfirm.tsx  FkSelect.tsx
  hooks/        useResourceList.ts
  districts/    DistrictsPage.tsx  DistrictForm.tsx
  clubs/        ClubsPage.tsx      ClubForm.tsx
  coaches/      CoachesPage.tsx    CoachForm.tsx
  groups/       GroupsPage.tsx     GroupForm.tsx
  gymnasts/     GymnastsPage.tsx   GymnastForm.tsx
```

## Resource details

Field lists come from `app/models.py`; validation mirrors the DB constraints.

| Resource | Form fields | List filter | Notes |
|---|---|---|---|
| District | `name`, `abbreviation` (≤10) | none | both unique globally |
| Club | `district_id`, `name`, `abbreviation` (≤10) | `district_id` | name/abbreviation unique per district |
| Coach | `club_id`, `first_name`, `last_name`, `is_head_coach` | `club_id` | identity unique per club |
| Group | `club_id`, `name` | `club_id` | name unique per club |
| Gymnast | `club_id?`, `group_id?`, `first_name`, `last_name`, `date_of_birth?`, `country_code?` (≤3) | `club_id` | club and group are independent and both optional |

Group membership is managed through the Gymnast form's `group_id` field — there is no
separate membership screen.

## Data flow

Query keys mirror the API surface, with the filter in the key:

```ts
["districts"]
["clubs", { district_id }]
["coaches", { club_id }]
["groups", { club_id }]
["gymnasts", { club_id }]
```

Mutations invalidate their own resource key. They do **not** invalidate children: a
delete cannot succeed while dependents exist, so there is nothing stale to clean up. The
one real cross-resource dependency is the FK pickers — creating a club must make it
appear in the gymnast form's club dropdown. `FkSelect` reads the parent's own list key
(`["clubs", {}]`), so invalidating `["clubs"]` refreshes every picker using it. Using a
bespoke picker key instead is the usual source of "I created it but the dropdown doesn't
show it" bugs.

None of the list endpoints paginate, so search and sort are client-side over the full
list. No polling in admin — `refetchInterval` stays a scoring/standings concern.

Updates send only dirty fields (RHF `dirtyFields`), matching the backend's
`model_dump(exclude_unset=True)` contract. A form that PATCHes every field would send an
untouched nullable FK as explicit `null` and silently unassign a gymnast from their group.

## Error handling

| Failure | Surface |
|---|---|
| Zod validation (client) | inline under the field, before any request |
| 409 uniqueness on save | `ErrorBanner` inside the dialog; form stays open with values intact |
| 409 RESTRICT on delete | `ErrorBanner` on the list page, below the header |
| 404 / network | `ErrorBanner` on the list page |

Zod schemas mirror DB constraints only — field length, required vs nullable. Uniqueness,
RESTRICT and abbreviation-uppercasing stay server-side and surface as the API's `detail`,
consistent with Phase 1's "API rules surfaced, not duplicated" principle.

**One targeted fix to existing code:** `apiDetail()` (`src/api/client.ts:23`) currently
renders 422 bodies with `JSON.stringify`, dumping FastAPI's validation array as raw JSON.
Phase 1 never hit it; five admin forms will. It will format 422 arrays as `field: message`
lines, which improves every existing caller.

## Testing

Vitest + Testing Library + MSW under `frontend/test/`, mirroring `frontend/src/`.
Per resource page:

1. renders rows from a mocked list response
2. create → dialog → submit → asserted POST body → row appears
3. edit → dialog prefilled → PATCH sends only changed fields
4. delete → confirm → 409 → error banner shows the API's `detail`
5. search filters rows client-side

Plus unit tests for the extracted pieces after Stage B (`useResourceList` predicate,
`FkSelect` none-option handling). Gymnast additionally covers nullable FK → `null` in the
PATCH body, the case most likely to regress.

## Out of scope

Judges, RoutineProfiles, Meet create/edit (Phase 2b), pagination, bulk/CSV import, any
config-driven field renderer, and auth (unchanged from Phase 1: none).
