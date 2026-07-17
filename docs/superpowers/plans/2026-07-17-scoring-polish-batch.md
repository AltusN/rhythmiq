# Scoring Polish Batch Implementation Plan

> **For agentic workers:** This plan is executed **interactively, in-session** — do
> NOT dispatch subagents. Tasks F1–F4 and 1–4 are implemented by **Altus** (tutor
> mode: Claude reviews, challenges, and suggests alternatives, but does not write the
> code). Tasks F5, F6, and 5 are implemented by **Claude**. Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** Clear the Phase 1 scoring screen's polish debt: the six fixes deferred by
the Phase 1 final review (Part A, Tasks F1–F6), then five UX improvements (Part B,
Tasks 1–5) — save feedback, keyboard focus, an age-group filter, panel display
polish, and an unsaved-changes guard.

**Architecture:** All changes live in `frontend/src/features/scoring/`. No backend
changes (`/meet-entries/` already filters by `age_group`; `Judge` already has
`first_name`/`last_name`). Each item is one commit with its tests, per the
test-after-each-module rule.

**Tech Stack:** React 19, React Hook Form, TanStack Query, Tailwind classes,
Vitest + Testing Library + MSW.

**Spec:** `docs/superpowers/specs/2026-07-17-scoring-polish-design.md`

## Global Constraints

- Branch: `feature/scoring-polish` off `main`. One commit per task, subject prefixed
  `feat:`/`fix:`.
- Commands run from `frontend/`: single file
  `npm test -- --run test/features/scoring/ScoringPage.test.tsx`; full suite
  `npm test -- --run`; typecheck+build `npm run build`.
- Test conventions: `renderApp(route)` from `test/utils.tsx`; MSW `server.use(...)`
  with the `api()` path helper and fixtures from `test/fixtures.ts`
  (see `test/features/scoring/ScoringPage.test.tsx` — its `mockBase()` helper is the
  starting point for every new ScoringPage-level test). Vitest globals are on
  (`test`, `expect`, `vi` need no import).
- The default test panel is `savePanel(5, { D: 1, E1: 2 })` — judge 1 (Naledi
  Dlamini) on D, judge 2 (Mina Kim) on E1; A and E2–E4 unassigned.
- No new dependencies.

## Setup

- [ ] `git checkout -b feature/scoring-polish` (from repo root, on a clean `main`)

---

## Part A — Deferred review fixes (from the Phase 1 final review)

These land first, as `fix:` commits, so Part B's UX work builds on corrected code.
Source: the deferred-polish list in the Phase 1 SDD ledger
(`.superpowers/sdd/progress.md`, gitignored).

### Task F1: Unparseable input — preview shows NaN (Altus)

**Files:**
- Modify: `frontend/src/features/scoring/ScoreForm.tsx`,
  `frontend/src/lib/score-math.ts` (comment only)
- Test: `frontend/test/features/scoring/ScoringPage.test.tsx`

**Interfaces:** `parseBox` (ScoreForm.tsx:43) currently returns `Number(t)`, which
is `NaN` for text like `"8,25"` — `computePreview` then renders `NaN` in the
preview strip. Change `parseBox` to return `undefined` for unparseable input. Safe
for saves too: submit is validation-gated (`validateBox` rejects non-numbers), so
only the live preview ever sees garbage — but `undefined` at submit time would mean
"cleared box → DELETE", which is why the validation gate matters; say so in a
comment if you find yourself needing to explain it.

- [ ] **Step 1: Write the failing tests** in `ScoringPage.test.tsx`:
  1. Type `8,25` into E1 → the preview strip never shows `NaN`
     (`expect(screen.queryByText(/NaN/)).toBeNull()`), and E still reads `0.00`.
  2. Test-gap minor while here: invalid input (`8.27`) + Save → **no POST fires**
     (register an MSW `http.post(api("/judge-scores/"), …)` spy handler and assert
     it was never called after the validation error appears), and the error shows
     the exact copy `Use 0.05 steps` (the existing test only matches `/0\.05/`).
- [ ] **Step 2: Run and verify test 1 fails** (preview shows NaN today).
- [ ] **Step 3: Implement** — `Number.isNaN` guard in `parseBox`. While in the
  area, add the review's requested comment to `computePreview` in
  `src/lib/score-math.ts`: the preview rounds per-panel like the server, but
  floating-point vs `Decimal` can drift the displayed total by ±0.01 in rare
  cases; the server's total is authoritative.
- [ ] **Step 4: Run tests, verify PASS.**
- [ ] **Step 5: Commit** —
  `git commit -m "fix: treat unparseable score input as empty in preview"`

### Task F2: Formatting & copy — "8.40" and bib-less deletes (Altus)

**Files:**
- Modify: `frontend/src/features/scoring/ScoreForm.tsx`,
  `frontend/src/features/entries/EntriesPage.tsx`
- Test: `frontend/test/features/scoring/ScoringPage.test.tsx`,
  `frontend/test/features/entries/EntriesPage.test.tsx`

**Behavior:**
1. Loaded score defaults render two decimals: `String(toNum(existing.value))`
   in `defaultValues` (ScoreForm.tsx:85-99) turns `"8.40"` into `"8.4"` — use
   `.toFixed(2)` instead, for boxes and the penalty (keep penalty's
   empty-when-zero behavior).
2. Delete-confirm copy (EntriesPage.tsx:93) says `bib null` for entries without a
   bib — fall back to the competitor's name (`nameFor` is already in scope there).

- [ ] **Step 1: Write the failing tests**:
  1. Mount with an existing score of `"8.40"` (see the "penalty box locks" test
     for loading routines+scores) → `expect(screen.getByLabelText("E1")).toHaveValue("8.40")`.
  2. Entries: entry with `bib_number: null` → confirm copy contains the name, not
     `null`. Test-gap minor while here: mock `window.confirm` to return **false**
     → no DELETE fires (spy handler, same pattern as F1's no-POST assertion).
- [ ] **Step 2: Run and verify they fail.**
- [ ] **Step 3: Implement** (both are one-liners).
- [ ] **Step 4: Run tests, verify PASS** — run both changed test files.
- [ ] **Step 5: Commit** —
  `git commit -m "fix: two-decimal score defaults and bib-less delete copy"`

### Task F3: useCompetitorNames swallows query errors (Altus)

**Files:**
- Modify: `frontend/src/lib/useCompetitorNames.ts`, plus its consumers
  (`grep -rn useCompetitorNames frontend/src` — ScoringPage and EntriesPage)
- Test: `frontend/test/features/scoring/ScoringPage.test.tsx`

**Interfaces:** the hook returns `{ nameFor, gymnasts, groups, isPending }` and
silently falls back to `Gymnast #id` labels when `/gymnasts/` or `/groups/` fail.
Add `error: Error | null` (first of `gymnastsQ.error ?? groupsQ.error ?? null`) to
the return; consumers render their existing `ErrorBanner` when it's set.

- [ ] **Step 1: Write the failing test**: 500 on `/gymnasts/` → an alert with the
  API detail appears on the scoring page (mirror the existing "failed routines
  query" test), instead of the list silently showing `Gymnast #7`.
- [ ] **Step 2: Run and verify it fails.**
- [ ] **Step 3: Implement** — hook + both consumers.
- [ ] **Step 4: Run tests, verify PASS.**
- [ ] **Step 5: Commit** — `git commit -m "fix: surface competitor-name query errors"`

### Task F4: Stale PanelSetupDialog error on reopen (Altus)

**Files:**
- Modify: `frontend/src/features/scoring/PanelSetupDialog.tsx`
- Test: `frontend/test/features/scoring/PanelSetupDialog.test.tsx`,
  `frontend/test/features/scoring/panel-storage.test.ts`

**Behavior:** the reopen-reseed block (PanelSetupDialog.tsx:21-24) resets `draft`
but not `error` — trigger the duplicate-E-judge error, close, reopen: the error is
still there. Clear it in the same `if (open)` branch.

- [ ] **Step 1: Write the failing tests**:
  1. Dialog: cause the duplicate-E error, close, reopen → no `role="alert"`.
  2. Test-gap minor while here (`panel-storage.test.ts`): `loadPanel` already
     guards unparseable JSON and non-objects, but **not shape** — `"[]"` passes
     the object check, and `'{"D":"x"}'` returns a string judge id that
     `boxesFor` treats as an assigned judge (truthy, `!== undefined`). Tests:
     both inputs → `{}` (or with junk entries dropped). Fix `loadPanel` to keep
     only known `PANEL_SLOTS` keys whose values are numbers.
- [ ] **Step 2: Run and verify the dialog test fails.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run tests, verify PASS.**
- [ ] **Step 5: Commit** — `git commit -m "fix: clear stale panel dialog error on reopen"`

### Task F5: Routine-create failure misattributed to the penalty box (Claude)

**Files:**
- Modify: `frontend/src/features/scoring/save-scores.ts`,
  `frontend/src/features/scoring/ScoreForm.tsx`
- Test: `frontend/test/features/scoring/ScoringPage.test.tsx`,
  `frontend/test/features/scoring/save-scores.test.ts`,
  `frontend/test/features/scoring/save-diff.test.ts`

**Interfaces:**
- Produces: `SaveScoresResult` gains `formError?: string` — set only when the lazy
  `POST /routines/` fails (no per-box attribution makes sense: nothing was
  saveable). `boxErrors` stays `{}` in that case. ScoreForm renders it via RHF's
  root error. **Task 5 (Part B) must count `formError` as unclean** in its
  `clean` check.

- [ ] **Step 1: Write the failing tests**:

```tsx
// ScoringPage.test.tsx
test("routine-create failure reports a form-level error, not a penalty error", async () => {
  mockBase();
  server.use(
    http.post(api("/routines/"), () =>
      HttpResponse.json({ detail: "meet is completed" }, { status: 409 }),
    ),
  );
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await userEvent.type(await screen.findByLabelText("E1"), "8.25");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("meet is completed");
  // the penalty box specifically must NOT carry the error
  expect(screen.getByLabelText("Penalty").parentElement?.textContent).not.toContain("meet is completed");
});
```

  Plus in `save-scores.test.ts`: `saveScores` with `routineId: undefined` and a
  failing POST resolves to `{ routineId: null, boxErrors: {}, formError: "…" }`.
  Plus the review's stranger-scores test-gap in `save-diff.test.ts`: an
  `existing` score whose `(judge_id, panel)` matches **no box** (a judge no longer
  on the panel) produces **no delete op** — assert `ops.deletes` is empty when
  `values` clears nothing.

- [ ] **Step 2: Run and verify they fail** (error currently lands under Penalty).
- [ ] **Step 3: Implement** — `save-scores.ts`:

```ts
export interface SaveScoresResult {
  routineId: number | null;
  boxErrors: Partial<Record<BoxKey | "penalty", string>>;
  formError?: string; // lazy routine creation failed; nothing was written
}

// in the routineId === undefined branch:
if (error || !data) {
  return { routineId: null, boxErrors: {}, formError: apiDetail(error) };
}
```

  `ScoreForm.tsx` — in `submit`, before the boxErrors loop:

```tsx
if (result.formError) {
  setError("root.server", { type: "server", message: result.formError });
}
// and the advance/clean condition becomes:
onSaved(
  result,
  next && !result.formError && Object.keys(result.boxErrors).length === 0,
);
```

  Render beneath the box row:

```tsx
{formState.errors.root?.server && (
  <p role="alert" className="mt-2 text-sm text-red-700">
    {formState.errors.root.server.message}
  </p>
)}
```

- [ ] **Step 4: Run tests, verify PASS** (all three test files).
- [ ] **Step 5: Commit** —
  `git commit -m "fix: report routine-create failure as form-level error"`

### Task F6: Silent refetch failure while the form is mounted (Claude)

**Files:**
- Modify: `frontend/src/features/scoring/ScoringPage.tsx`
- Test: `frontend/test/features/scoring/ScoringPage.test.tsx`

**Behavior:** `detailError` (ScoringPage.tsx:112) renders only in the `!showForm`
branch. Once the keep-mounted machinery holds the form open, a failing
routines/scores/penalty-records **refetch** (e.g. the post-save invalidation)
reports nothing. Render the same `ErrorBanner` above the form when `detailError`
is set while `showForm` is true — the form stays mounted (values intact), the
banner explains why data may be stale.

- [ ] **Step 1: Write the failing test**: clean save (POST handlers as in the
  existing lazy-create test), but `http.get(api("/judge-scores/"), …)` returns 500
  **after** the save (flip a `let failNow = false` flag in the handler; set it in
  the POST handler). Save → banner with the detail appears AND `E1` still shows
  its value (form did not unmount).
- [ ] **Step 2: Run and verify it fails** (no banner today).
- [ ] **Step 3: Implement** — inside the `showForm` branch's wrapper div, before
  the `<h2>`:

```tsx
{detailError && <ErrorBanner message={detailError.message} />}
```

- [ ] **Step 4: Run tests, verify PASS.**
- [ ] **Step 5: Commit** —
  `git commit -m "fix: show detail query errors while score form is mounted"`

---

## Part B — UX improvements

### Task 1: Save feedback — "Saved ✓" indicator (Altus)

**Files:**
- Modify: `frontend/src/features/scoring/ScoreForm.tsx`
- Test: `frontend/test/features/scoring/ScoringPage.test.tsx`

**Interfaces:**
- Consumes: `saveScores` result (`result.boxErrors`, already in `submit`).
- Produces: a visible text node matching `/Saved ✓/` after a fully clean save.
  **Task 5 depends on this exact text** to await save completion in its tests —
  keep the copy `Saved ✓`.

**Behavior (from spec):** after `saveScores` resolves with zero `boxErrors`, show
"Saved ✓" beside the Save buttons; it disappears after ~2 s or on the next edit,
whichever comes first. It must NOT appear when any box error came back. Component
state only — no toast layer.

- [ ] **Step 1: Write the failing tests** in `ScoringPage.test.tsx` (they exercise
  the full page, matching the existing tests' style). Cover:
  1. Clean save (reuse the MSW POST handlers from the existing
     "save lazily creates the routine and posts scores" test) → `Saved ✓` appears.
  2. Save that returns a 409 box error (see the "partial failure" test's handlers)
     → `Saved ✓` is NOT in the document after the error renders.
  3. After a clean save, typing in a box removes the indicator.

  *Hints:* assert absence with `screen.queryByText(/Saved ✓/)` → `.toBeNull()`.
  For the 2 s auto-clear you can either use real timers with
  `await waitFor(() => …toBeNull(), { timeout: 3000 })`, or skip asserting the
  timeout entirely and only test clear-on-edit — mixing `vi.useFakeTimers()` with
  `userEvent` requires `userEvent.setup({ advanceTimers: vi.advanceTimersByTime })`
  and is fiddly; your call, but don't let the timer test flake.
- [ ] **Step 2: Run and verify they fail** —
  `npm test -- --run test/features/scoring/ScoringPage.test.tsx`, new tests FAIL
  (indicator never found).
- [ ] **Step 3: Implement in `ScoreForm.tsx`.** *Hints:* a `useState<boolean>`
  (or timestamp) set in `submit` only when `!result.formError &&
  Object.keys(result.boxErrors).length === 0` (F5 added `formError` — a failed
  routine-create is not a save); a `setTimeout` to clear it (clean up the timer — a `useEffect` return or
  ref); clear it on edit (RHF `watch` has a subscription form:
  `useEffect(() => { const sub = watch(() => …); return () => sub.unsubscribe(); }, [watch])`
  — or simpler, clear it inside the existing render-level `watch()` comparison you
  design). Render next to the buttons inside the existing `{!meetLocked && …}` block.
- [ ] **Step 4: Run tests, verify PASS** (same command).
- [ ] **Step 5: Commit** —
  `git add frontend/src/features/scoring/ScoreForm.tsx frontend/test/features/scoring/ScoringPage.test.tsx`
  `git commit -m "feat: saved indicator on clean score save"`

---

### Task 2: Keyboard focus on form mount (Altus)

**Files:**
- Modify: `frontend/src/features/scoring/ScoreForm.tsx`
- Test: `frontend/test/features/scoring/ScoringPage.test.tsx`

**Interfaces:**
- Consumes: `visibleBoxes` (already computed) — first entry with
  `judgeId !== undefined` is the focus target; RHF's `setFocus(name)` (destructure
  from the existing `useForm` call).
- Produces: no new exports; behavior only.

**Behavior (from spec):** on mount, focus the first **visible, enabled** score box.
`ScoreForm` is keyed by `(entry, apparatus)` in `ScoringPage`, so every
competitor/apparatus switch remounts it — mount-time focus covers both "picked a
competitor" and "Save & next advanced". Skip when `meetLocked` (all boxes disabled).

- [ ] **Step 1: Write the failing tests** in `ScoringPage.test.tsx`:
  1. Default panel, senior entry → `screen.getByLabelText("D-Body")` has focus
     (`.toHaveFocus()`).
  2. E-only entry (`level: "level_5"`, like the existing E-only test) → `E1` has
     focus.
  3. Panel with **no D judge** (`savePanel(5, { E1: 2 })` inside the test, after
     `localStorage.clear()`) → D-Body is disabled and `E1` has focus.
- [ ] **Step 2: Run and verify they fail** (focus lands on `document.body`).
- [ ] **Step 3: Implement.** *Hints:* a mount-only `useEffect` calling
  `setFocus(firstFocusableKey)` where
  `firstFocusableKey = visibleBoxes.find((b) => b.judgeId !== undefined)?.key`;
  guard `meetLocked` and the all-slots-unassigned case (`undefined` target). An
  empty dep array is correct here for the same reason `defaultValues` uses one —
  the component remounts per `(entry, apparatus)`.
- [ ] **Step 4: Run tests, verify PASS.**
- [ ] **Step 5: Commit** — `git commit -m "feat: focus first score box on competitor switch"`

---

### Task 3: Age-group filter (Altus)

**Files:**
- Modify: `frontend/src/features/scoring/CompetitorList.tsx`,
  `frontend/src/features/scoring/ScoringPage.tsx`
- Test: `frontend/test/features/scoring/ScoringPage.test.tsx` (page-level; add a
  select-rendering case to `frontend/test/features/scoring/CompetitorList.test.tsx`
  if you touch its props' rendering logic)

**Interfaces:**
- Consumes: `AGE_GROUPS` from `src/lib/domain.ts` (`["u8","u10","u12","u14","o14"]`);
  server filter `?age_group=` on `/meet-entries/`.
- Produces: `CompetitorList` gains props `ageGroup: string` and
  `onAgeGroupChange: (a: string) => void` (mirroring `level`/`onLevelChange`).
  The select's accessible name is **"Age group filter"** — Task 5's code references
  the handler shape. Entries query key becomes
  `["entries", meet.id, level, ageGroup]` — the `["entries", meet.id]` prefix must
  stay first so existing invalidations keep matching.

**Behavior (from spec):** an age-group select next to the level select, flowing to
the entries query exactly as `level` does (server-side, `age_group: ageGroup ||
undefined`, `""` = "All age groups"); changing it resets the selected competitor to
`null`.

- [ ] **Step 1: Write the failing tests** in `ScoringPage.test.tsx`:
  1. Capture the request:
     `http.get(api("/meet-entries/"), ({ request }) => { seenAgeGroup = new URL(request.url).searchParams.get("age_group"); return HttpResponse.json([…]); })`
     — select `o14` via
     `userEvent.selectOptions(screen.getByLabelText("Age group filter"), "o14")`,
     then `waitFor(() => expect(seenAgeGroup).toBe("o14"))`.
  2. With a competitor selected, changing the age group clears the selection
     ("Pick a competitor to score." reappears).
- [ ] **Step 2: Run and verify they fail** (no "Age group filter" element).
- [ ] **Step 3: Implement.** CompetitorList: copy the level `<select>` block, using
  `AGE_GROUPS` and label "Age group filter" (age-group codes like `u8`/`o14` read
  fine raw — `labelize` is a no-op on them, use it or not). ScoringPage: `ageGroup`
  state, extend the query key + `query` params, reset `selectedEntryId` in the
  change handler like `onLevelChange` does.
- [ ] **Step 4: Run tests, verify PASS.**
- [ ] **Step 5: Commit** — `git commit -m "feat: age-group filter on scoring competitor list"`

---

### Task 4: Panel display polish (Altus)

**Files:**
- Modify: `frontend/src/features/scoring/ScoringPage.tsx`
- Test: `frontend/test/features/scoring/ScoringPage.test.tsx`

**Interfaces:**
- Consumes: `judgesQ.data` (judges have `first_name` + `last_name`);
  `isEOnlyLevel` from `src/lib/score-math.ts`; `panel` state; `setPanelOpen`.
- Produces: no new exports; behavior only.

**Behavior (from spec):**
1. `judgeName` returns `first_name last_name` (was `last_name` only).
2. Unassigned slots in the panel footer render in amber (`text-amber-600`) instead
   of plain text.
3. When the selected competitor's **required** slots include an unassigned one,
   a one-line hint above the form links to panel setup. Required = minimum viable
   panel: `D, A, E1, E2` for full levels; `E1, E2` for E-only levels. E3/E4 never
   trigger it.

- [ ] **Step 1: Write the failing tests** in `ScoringPage.test.tsx`:
  1. Footer shows `Naledi Dlamini` (not just `Dlamini`) for slot D.
  2. Default panel (`{ D: 1, E1: 2 }`), senior selected → hint visible (A and E2
     are required-but-unassigned); it exposes a button/link whose click opens the
     panel dialog (assert the dialog's judge selects appear).
  3. Full minimum panel (`savePanel(5, { D: 1, A: 1, E1: 2, E2: 1 })`) → no hint,
     even though E3/E4 are unassigned.
  4. E-only entry with `{ E1: 2, E2: 1 }` and no D/A → no hint.
- [ ] **Step 2: Run and verify they fail.**
- [ ] **Step 3: Implement.** *Hints:* a small helper in `ScoringPage.tsx` like
  `missingRequiredSlots(panel, level): string[]` keeps the JSX readable and is
  trivially testable through the page tests; reuse the existing
  `setPanelOpen(true)` button pattern for the hint's link. Amber: wrap the
  `judgeName(...)` output in a span with `text-amber-600` when the slot is
  `undefined`.
- [ ] **Step 4: Run tests, verify PASS.**
- [ ] **Step 5: Commit** —
  `git commit -m "feat: full judge names and unassigned-slot hint in panel display"`

---

### Task 5: Unsaved-changes guard (Claude)

**Files:**
- Modify: `frontend/src/features/scoring/ScoreForm.tsx`,
  `frontend/src/features/scoring/ScoringPage.tsx`
- Test: `frontend/test/features/scoring/ScoringPage.test.tsx`

**Interfaces:**
- Consumes: RHF `formState.isDirty` + `reset`; Task 1's `Saved ✓` indicator (to
  await save completion in tests); Task 3's `onAgeGroupChange` handler (gets
  guarded too).
- Produces: `ScoreForm` gains optional prop `onDirtyChange?: (dirty: boolean) => void`.

**Behavior (from spec):** `window.confirm("Discard unsaved scores?")` before a
competitor/level/apparatus/age-group switch while the form has unsaved edits;
declining aborts before any state changes. A fully clean save re-baselines the form
via `reset(values)` (partial failure stays dirty). Tab navigation and browser close
are scoped out.

- [ ] **Step 1: Write the failing tests** in `ScoringPage.test.tsx`:

```tsx
test("switching competitors with unsaved edits prompts; declining keeps the form", async () => {
  const second = makeEntry({ id: 22, meet_id: 5, gymnast_id: 7, group_id: null, level: "senior", bib_number: "13" });
  mockBase({ entries: [seniorEntry, second] });
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await userEvent.type(await screen.findByLabelText("E1"), "8.25");
  await userEvent.click(screen.getByRole("button", { name: /13 ·/ }));
  expect(confirmSpy).toHaveBeenCalledWith("Discard unsaved scores?");
  expect(screen.getByLabelText("E1")).toHaveValue("8.25"); // still bib 12's form

  confirmSpy.mockReturnValue(true);
  await userEvent.click(screen.getByRole("button", { name: /13 ·/ }));
  await waitFor(() => expect(screen.getByLabelText("E1")).toHaveValue(""));
  confirmSpy.mockRestore();
});

test("a clean save clears dirtiness, so switching does not prompt", async () => {
  const second = makeEntry({ id: 22, meet_id: 5, gymnast_id: 7, group_id: null, level: "senior", bib_number: "13" });
  mockBase({ entries: [seniorEntry, second] });
  server.use(
    http.post(api("/routines/"), () =>
      HttpResponse.json(makeRoutine({ id: 77, entry_id: 21 }), { status: 201 }),
    ),
    http.post(api("/judge-scores/"), () => HttpResponse.json({}, { status: 201 })),
  );
  const confirmSpy = vi.spyOn(window, "confirm");
  renderApp("/meets/5/scoring");
  await userEvent.click(await screen.findByRole("button", { name: /12 ·/ }));
  await userEvent.type(await screen.findByLabelText("E1"), "8.25");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await screen.findByText(/Saved ✓/); // Task 1's indicator marks completion
  await userEvent.click(screen.getByRole("button", { name: /13 ·/ }));
  expect(confirmSpy).not.toHaveBeenCalled();
  confirmSpy.mockRestore();
});
```

- [ ] **Step 2: Run and verify the first test fails** (no prompt appears; the
  switch goes through and E1 empties). The second test passes even before
  implementation — that's expected and fine: it pins the no-false-positive
  behavior (a clean save must never prompt) so a sloppy guard can't regress it.
- [ ] **Step 3: Implement `ScoreForm.tsx`** — add the prop, report dirtiness,
  re-baseline on clean save:

```tsx
// prop addition
onDirtyChange?: (dirty: boolean) => void;

// add `reset` to the existing useForm destructure (which by now also
// includes Task 2's `setFocus`) — don't drop anything already there

// report dirtiness upward (place after the useForm call)
const { isDirty } = formState;
useEffect(() => {
  onDirtyChange?.(isDirty);
}, [isDirty, onDirtyChange]);

// in submit, replace the formError/boxErrors/onSaved tail (as F5 left it) with:
const clean =
  !result.formError && Object.keys(result.boxErrors).length === 0;
if (clean) reset(values); // re-baseline to just-saved values, not to empty
if (result.formError) {
  setError("root.server", { type: "server", message: result.formError });
}
for (const [key, message] of Object.entries(result.boxErrors)) {
  setError(key as BoxKey | "penalty", { type: "server", message });
}
onSaved(result, next && clean);
```

  (Keep Task 1's saved-indicator call in the `clean` branch, adjacent to
  `reset(values)`. `useEffect` joins the existing `useMemo`/`useState` imports.)

- [ ] **Step 4: Implement `ScoringPage.tsx`** — track dirtiness, guard the four
  switch paths:

```tsx
const [formDirty, setFormDirty] = useState(false);
const confirmDiscard = () =>
  !formDirty || window.confirm("Discard unsaved scores?");

// CompetitorList handlers become:
onSelect={(entry) => {
  if (entry.id === selectedEntryId) return;
  if (!confirmDiscard()) return;
  setFormDirty(false);
  setSelectedEntryId(entry.id);
}}
onLevelChange={(l) => {
  if (!confirmDiscard()) return;
  setFormDirty(false);
  setLevel(l);
  setSelectedEntryId(null);
}}
onApparatusChange={(a) => {
  if (!confirmDiscard()) return;
  setFormDirty(false);
  setApparatus(a as Apparatus);
  setSelectedEntryId(null);
}}
onAgeGroupChange={(a) => {   // added in Task 3
  if (!confirmDiscard()) return;
  setFormDirty(false);
  setAgeGroup(a);
  setSelectedEntryId(null);
}}

// ScoreForm gains:
onDirtyChange={setFormDirty}
```

  The guard runs **before** any `set*` call, so the `readyFormKey` keep-mounted
  machinery never sees a half-committed switch. `setFormDirty(false)` on accepted
  switches avoids a stale `true` when no form mounts next (selection cleared).

- [ ] **Step 5: Run the new tests, verify PASS** —
  `npm test -- --run test/features/scoring/ScoringPage.test.tsx`
- [ ] **Step 6: Commit** —
  `git add frontend/src/features/scoring/ScoreForm.tsx frontend/src/features/scoring/ScoringPage.tsx frontend/test/features/scoring/ScoringPage.test.tsx`
  `git commit -m "feat: confirm before discarding unsaved score edits"`

---

### Task 6: Batch verification & wrap-up

- [ ] **Step 1: Full frontend suite + build** — from `frontend/`:
  `npm test -- --run && npm run build` → all tests PASS, build exits 0.
- [ ] **Step 2: Backend untouched** — from `backend/`: `.venv/bin/pytest -q` →
  same pass count as `main` (no backend files changed; `git diff main --stat`
  shows only `frontend/` + docs).
- [ ] **Step 3: Manual walkthrough** (backend + `npm run dev` running, seeded
  data): pick a competitor → boxes focused; type garbage (`8,25`) → preview shows
  `0.00`, never `NaN`; loaded scores read `8.40` not `8.4`; type a score, switch
  competitor → prompt; save → `Saved ✓`, switch → no prompt; complete the meet in
  another tab, then save → form-level error (not under Penalty); filter by age
  group; break the panel (remove A) → hint appears, link opens dialog.
- [ ] **Step 4:** Use superpowers:finishing-a-development-branch to merge/PR.
