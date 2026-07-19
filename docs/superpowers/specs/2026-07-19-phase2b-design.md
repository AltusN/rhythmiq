# Rhythmiq Frontend Phase 2b — Judges, Routine Profiles, Meet CRUD

Date: 2026-07-19
Status: approved, ready for implementation planning

## Context

Phase 1 (meet-day scoring) and Phase 2 (admin console over districts, clubs, coaches,
groups, gymnasts) are both merged to `main`. Phase 2b closes out the v1 scope defined in
`2026-07-16-frontend-v1-design.md` by adding the three resources Phase 2 deliberately
left out — judges, routine profiles, and meet create/edit — plus one fix to a shipped
screen.

The three remaining resources are exactly the ones whose forms are *not* plain
scalar-plus-FK shapes: judges are trivial, but routine profiles have a create-only
identity and an exactly-one-of owner rule, and meets have a status lifecycle that the
admin console's shared layer knows nothing about.

After Phase 2b, judges can be created from the UI for the first time. Today
`PanelSetupDialog` receives judges as a prop and they can only exist via `make seed`, so
this closes a real meet-day loop.

## Decisions

| Decision | Choice |
|---|---|
| Meet CRUD location | On `/` (meet list) and the `MeetShell` header — **not** `/admin/meets` |
| Admin sidebar scope | Reference data only; gains Judges and Routine profiles, never Meets |
| Routine profile owner picker | Radio `kind` + a single `competitorId` field, copying `EntryCreateForm` |
| Routine profile edit form | Separate component: read-only context line + the two mutable fields |
| Shared layer | Consumed unchanged — no edits to `src/features/admin/components/` |
| `OwnerPicker` extraction | Explicit non-goal (see Non-goals) |
| Gymnast group select | Filtered to the selected club's groups, disabled until a club is chosen |
| Backend changes | None — Phase 2b is frontend-only, like Phase 2 |
| Build split | Claude builds all of Phase 2b (explicit user choice, exception to tutor mode) |

### Why meets are not an admin resource

The spec's Phase 2 section originally listed meets as a sixth admin console resource.
That was reconsidered and rejected:

- Districts through gymnasts are reference data — set up once, rarely touched. A meet is
  the primary object of the app: it is what `/` lists and what every route nests under.
  Routing a user to `/admin/meets` to create the thing the home page exists to list is
  backwards.
- Meets do not behave like the other five. They have forward-only status transitions, a
  delete that 409s once `in_progress`/`completed`, a confirmation gate on `completed`
  because it freezes scores, and a row that navigates rather than merely edits.
  `ResourceTable` encodes "flat resource, uniform row actions"; forcing meets into it
  would mean parameterising the shared layer for a single caller.

`/` keeps its existing link-list presentation. It is the screen looked at most, and
converting it to a table to gain reuse would be a visual regression paying for an
abstraction meets do not fit.

## Screens

| Route | Screen | Change |
|---|---|---|
| `/` | Meet list | Gains `[+ New meet]` and per-row Edit/Delete buttons |
| `/meets/:meetId` | Meet shell header | Gains `[Edit details]` |
| `/admin/judges` | Judges CRUD | New |
| `/admin/routine-profiles` | Routine profiles CRUD | New |
| `/admin/gymnasts` | Gymnasts CRUD | Group select fixed (see §4) |

Sidebar order becomes: Districts → Clubs → Coaches → Groups → Gymnasts → Judges →
Routine profiles.

## 1. Judges — `/admin/judges`

A fifth straight consumption of the shared layer, closest in shape to the Districts
pilot.

- **Table columns:** first name, last name, country code, brevet.
- **Filters:** `country_code` as a genuine server round trip (`list_judges` accepts it),
  with `country_code` in the TanStack query key. Search stays client-side and out of the
  key, matching the Phase 2 convention.
- **Form:** mirrors `JudgeCreate` exactly — `first_name`/`last_name`
  `min(2).max(100)`, `country_code` optional and validated as exactly 3 alpha
  characters, `brevet` optional free text (`String`, nullable — not an enum).
- **Normalisation stays server-side.** `JudgeCreate.validate_country_code` uppercases;
  the client validates the shape but does not uppercase, and the form shows the saved
  value after the round trip. This follows the v1 spec's existing rule for abbreviation
  uppercasing.
- **No disabled-on-edit fields.** Judge has no parent FK and `JudgeUpdate` carries every
  field, making this the first admin resource with no immutability concern at all.

**Delete semantics (verified against `app/models.py`, 2026-07-19):** both
`JudgeScore.judge_id` and `PenaltyRecord.judge_id` are `ForeignKey(ondelete="RESTRICT")`.
A judge delete is therefore *rejected* with 409 once that judge has scored or issued a
penalty — nothing cascades. The confirm copy must not warn about destroying scores; it is
a plain `Delete judge "X Y"?`, and the 409 `detail` surfaces if dependents exist.

**Uniqueness:** `uq_judge_identity` is a `UniqueConstraint` on
(`first_name`, `last_name`, `country_code`). Two judges with the same name *and* the same
country collide with a 409 — but the same name under different countries is fine, and
because `country_code` is nullable, two same-named judges with no country set also
collide. Surfaced via `apiDetail` like every other unique violation; not reproduced
client-side.

## 2. Routine profiles — `/admin/routine-profiles`

- **Table columns:** owner, apparatus, level, music URL, choreography notes.
- **Owner names:** reuse `src/lib/useCompetitorNames.ts`, which already resolves the
  gymnast-or-group name pair for the scoring screen. Do not reimplement the lookup.
- **Filters:** `apparatus` and `level` as server round trips (both exist on
  `list_routine_profiles`), plus client-side search on owner name. The router's
  `gymnast_id`/`group_id` filters are deliberately **not** wired — an owner filter needs
  its own picker UI, and name search covers the same need at this scale.

### Create form

Copies the shipped `EntryCreateForm` pattern verbatim (`src/features/entries/EntryCreateForm.tsx`):

```
kind: z.enum(["gymnast", "group"])   // radio
competitorId: <single field>          // one FkSelect, swapped by kind
```

mapped at submit to `gymnast_id: kind === "gymnast" ? Number(competitorId) : null` and
the mirror for `group_id`.

The single `competitorId` field is the point: with one field rather than two, switching
kind cannot leave a stale value behind, so the exactly-one-of invariant is **structural
rather than validated**. The client never reproduces the backend's
`validate_gymnast_or_group` check because it cannot express the invalid state.

Remaining fields: `apparatus`, `level`, `music_url` (optional), `choreography_notes`
(optional, `max(500)` mirroring the backend `Field(max_length=500)`).

### Edit form

A **separate component**, not the create form with disabled fields.
`RoutineProfileUpdate` accepts only `music_url` and `choreography_notes`; owner,
apparatus and level together form the model's `UniqueConstraint` and are create-only.

```
Edit routine profile
------------------------------------
Ana Meyer · Ribbon · Level 3
(to change these, delete and recreate)
------------------------------------
Music URL [ ... ]
Notes     [ ... ]
```

Identity renders as a read-only context line, not as four inert controls. This is a
deliberate departure from the Phase 2 `disabled={!!initial}` convention: that convention
exists to stop a *mostly editable* form from silently dropping one field, whereas here
two-thirds of the form is immutable and greyed-out controls would misrepresent
"never editable here" as "temporarily disabled".

### Errors

Duplicate (owner, apparatus, level) returns 409 from the `UniqueConstraint`. Surfaced
through the existing `apiDetail` path like every other RESTRICT/unique rejection — the
API's `detail` is shown, not duplicated in client copy.

## 3. Meet create/edit — `/` and the meet shell header

Both entry points open the same `MeetForm` inside the existing `FormDialog`. `/` keeps
its link-list rendering; only the actions are new.

### Row layout on `/`

Each row in `MeetListPage` is currently a single `<Link>` wrapping the whole row. Edit
and Delete buttons cannot be nested inside it — a `<button>` inside an `<a>` is invalid
HTML and the click would propagate into navigation. The row is therefore restructured so
the `<Link>` covers only the meet name/details region, with Edit and Delete as siblings
in a trailing actions cell. Clicking the row's text still navigates into the meet, which
is the primary meet-day action and must not regress.

Delete lives on the row, not in the edit dialog, matching every admin screen.

- **Fields:** `name`, `location`, `start_date`, `end_date`, `district_id`,
  `medal_gold_min`, `medal_silver_min`.
- **Status is absent from both create and edit**, even though `MeetUpdate` accepts it.
  Status changes belong to the meet-shell controls, which enforce
  `ALLOWED_STATUS_TRANSITIONS` and the confirmation gate on `completed`. Putting status
  in this form would create a second, unguarded path around those controls. Create
  relies on the server's `draft` default.
- **Zod:** `name`/`location` `min(2).max(100)` mirroring `MeetCreate`; `start_date <=
  end_date`.

### Two inversions of Phase 2 convention

Both are deliberate and must be documented in code comments, or a future reader will
"fix" them back:

1. **The district select stays enabled on edit.** `MeetUpdate` genuinely includes
   `district_id` — meets and gymnasts are the two exceptions to the not-updatable-parent-FK
   rule. Applying `disabled={!!initial}` here would be wrong.
2. **Medal minima are validated cross-field on the client** (both-or-neither, and gold >
   silver). This is safe despite dirty-fields-only PATCH because the form holds both
   values in state even when only one is dirty, so Zod always sees the pair. The PATCH
   still sends only dirty fields; the router re-validates the incoming value against the
   stored counterpart via `_validate_partial_medal_cutoffs`, exactly as
   `_validate_partial_dates` does for dates.

### Delete

Rejected with 409 while `in_progress` or `completed` — a completed meet is the
historical record of who competed. Otherwise it cascades to entries and routines. The
confirm copy states the cascade plainly.

## 4. Gymnast group select — fixing a shipped screen

**The bug** (found by using the app, not by reading code): the gymnast form offers every
group regardless of club. `Group.club_id` is `nullable=False`, and
`routers/gymnast.py` rejects a mismatch on both write paths — line 44 on POST, line 117
on PATCH. So every cross-club group in that dropdown is *provably* invalid for the
gymnast being edited. There is no case where showing them helps, which makes filtering
correct rather than merely nicer.

Filtering is client-side against the already-fetched group list. Group counts are small
and `GymnastsPage` already loads them; a club-keyed server round trip would be
unnecessary surface.

Three behaviours make this safe rather than merely filtered:

1. **Group is disabled until a club is chosen**, with a hint ("Select a club to choose a
   group"). This treats club → group as the real hierarchy it is.
2. **Changing the club clears `group_id`**, so an invalid pair cannot be assembled from a
   sequence of individually-valid steps.
3. **On edit, the currently-assigned group is always present in the options even if it is
   an orphan**, visually flagged as belonging to another club. Without this, filtering
   would blank the select for any pre-existing cross-club gymnast and silently drop the
   assignment on save.

Behaviour 3 is the load-bearing one. It guards the failure mode this project has now hit
three times in three disguises — *the UI shows a state that is not the stored state, and
saving looks like it worked*: the `{}`-PATCH no-op on disabled parent FKs, the stale 409
surviving a filter change, and now the vanishing orphan group.

### Known accepted gap

The backend permits `club_id = None` with `group_id` set, because `routers/gymnast.py:37`
nests the consistency check inside `if payload.club_id is not None`. This is almost
certainly a backend oversight rather than a feature. Phase 2b **forbids that state in the
form** (behaviour 1) without changing the backend, keeping Phase 2b frontend-only. The
gap is recorded here so the divergence is a known decision rather than a discovered
surprise; closing it backend-side is deferred.

## Testing

Mirrors the conventions Phase 2 arrived at, several of which were learned from review
findings rather than chosen up front:

- MSW throughout; router-level tests exercise the real request/response pipeline.
- Request bodies asserted with whole-object `toEqual`, never `toMatchObject`, so an
  unexpected extra field fails the test.
- Each new screen gets a **client-side search test that genuinely fails if the search
  accessor is wrong** — the request-count test alone would pass even if the search box
  were inert. This was Important #2 of the Phase 2 final review.
- Every error-clearing test must be verified load-bearing (remove the clearing line and
  confirm the test fails), not merely passing. Phase 2 shipped at least one error-clearing
  test that would have passed without the code it claimed to cover.
- Section 4 needs a regression test for the orphan-group edit case specifically: load a
  gymnast whose group belongs to another club, save an unrelated field, assert
  `group_id` is unchanged in the PATCH body.

Playwright end-to-end tests remain deferred.

## Non-goals

- **No `OwnerPicker` extraction.** The radio + `competitorId` pattern is copied from
  `EntryCreateForm`, not shared with it. Stage B's extraction rule — extract from real,
  observed duplication, not anticipated duplication — is what made the shared layer
  survive three rollouts unchanged. Two call sites is thin, and extraction would refactor
  a shipped meet-day form whose tests are written against its current structure. If a
  third owner picker appears, extract then, with three real examples to generalise from.
- **No changes to `src/features/admin/components/`.** Sections 1–3 are a falsifiable
  prediction: if judges and routine profiles land without touching the shared layer, that
  is a fourth and fifth independent confirmation the Stage B boundaries were drawn
  correctly. If either one *forces* a change, that is real signal about where the
  abstraction leaks — record the outcome either way, since a forced change is the more
  informative result.
- No backend changes.
- No `FormDialog` focus trap (still deferred from Phase 2; role/aria-modal/Escape/backdrop
  already shipped).
- Itemized `PenaltyRecord` UI, auth, judge self-scoring, public results, CSV export, team
  scores, and production deployment all remain deferred per the v1 spec.

## Completion

Phase 2b closes the v1 frontend scope. Everything remaining in
`2026-07-16-frontend-v1-design.md`'s Deferred section is post-v1 and needs its own
brainstorm — most of it gated on backend auth.
