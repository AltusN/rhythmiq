# Levels 1–3 Four-Judge Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct levels 1–3 from a single pre-aggregated mark to a four-judge panel whose four marks (each ≤ 13) are combined by trimmed mean — the same aggregation the 4–7 and 8+ bands already use.

**Architecture:** The backend scoring **math is already correct** — `compute_routine_score`'s `BAND_1_3` branch routes every `Panel.final` mark through `trimmed_mean`, which returns the lone mark when there is one and the trimmed mean when there are four. The only backend change is panel *metadata* (`judges_per_panel`) plus comments. All real work is in the frontend, where a single-`F`-slot / single-`final`-box assumption is threaded through panel storage, the math mirror, the box-key type, the score form, and their tests. No database migration, no `Level`/band change.

**Tech Stack:** FastAPI + SQLAlchemy (backend); React 19 + Vite + React Hook Form + Vitest/Testing Library (frontend).

## Global Constraints

- **No backend scoring-logic change.** `trimmed_mean` over `Panel.final` already delivers the required behaviour; only `BAND_1_3.judges_per_panel` and comments change.
- **No database migration.** Each judge's mark is still ≤ 13 (existing `Panel.final` per-mark CHECK holds); `JudgeScore` is unique on `(routine, judge, panel)`, so four judges writing `final` is already legal.
- **`TRIM_THRESHOLD` stays 4** (backend `scoring.py`, frontend `score-math.ts`). It already means: 3 marks → plain average, 4 marks → drop high+low and average the middle two. The minimum viable panel is **three** judges (`F4` optional, like `E4`/`A2`). No threshold logic is added.
- **Four per-judge slots `F1 F2 F3 F4`**, mirroring 4–7's `DB1/DB2/E1/E2`. A stored legacy `"F"` migrates to `"F1"` when `F1` is unset — mirror the existing `"A" → "A1"` migration in `loadPanel` exactly (legacy value read raw from storage, NOT kept in the live `PanelSlot` list).
- **Levels 1–3 marks are straight scores out of 13, never deductions.** No `deductionToScore`/`scoreToDeduction` conversion touches them (they are excluded because their box keys are not in `E_BOX_KEYS`). **[SUPERSEDED 2026-07-23 — see commit `c43d7fb`:** the user clarified 1–3 marks ARE deductions off 13; the form now converts via `finalDeductionToScore`/`finalScoreToDeduction` (`FINAL_MAX = 13`, `FINAL_BOX_KEYS`) and the DB stores the score out of 13.]
- **Medals & tie-break unchanged:** levels 1–3 keep cutoff medals on the all-around; no E component, so `tie_break_on_execution`/`tieBreakOnExecution` stays `false`.
- **Commit subjects must start with a type prefix** (`feat:`/`fix:`/`chore:`/`docs:`/`test:`).

## File Structure

- `backend/app/scoring.py` — `BAND_1_3.judges_per_panel` value + the two comments that assert "exactly one judge / nothing is averaged".
- `backend/test/test_scoring.py` — new band-1-3 trimmed-mean cases.
- `frontend/src/features/scoring/panel-storage.ts` — `PanelSlot`/`PANEL_SLOTS` gain `F1..F4` and drop `F`; `SLOTS_BY_BAND`/`REQUIRED_SLOTS`/`SLOT_CONFLICT_GROUPS`; `loadPanel` legacy-`F` migration.
- `frontend/src/lib/score-math.ts` — `PreviewInput.finalScore` → `finalScores`; `computePreview` `1-3` branch; comments.
- `frontend/src/features/scoring/save-diff.ts` — `BoxKey` `"final"` → `"final1".."final4"`.
- `frontend/src/features/scoring/ScoreForm.tsx` — `BOX_LABELS`, `BOX_MAX`, `EMPTY_VALUES`, `boxesFor`, preview wiring.
- `frontend/test/…` — `score-math.test.ts`, `panel-storage.test.ts`, `save-diff.test.ts`, `ScoringPage.test.tsx`, `PanelSetupDialog.test.tsx`.
- `CLAUDE.md` — scoring-bands paragraph + frontend slots line.

---

## Task 1: Backend panel metadata + trimmed-mean tests

**Files:**
- Modify: `backend/app/scoring.py:52-61` (`BAND_1_3` + its comment) and `:179-181` (the `compute_routine_score` docstring bullet)
- Test: `backend/test/test_scoring.py`

**Interfaces:**
- Produces: `BAND_1_3.judges_per_panel == {Panel.final: 4}`. No signature change; `compute_routine_score` behaviour for four `final` marks is trimmed mean, for three is plain average, for one is that mark — all already delivered by `trimmed_mean`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/test/test_scoring.py`. Match the file's existing style for building a routine with judge scores (find an existing band-1-3 or band-4-7 test and mirror its fixture construction — likely a helper that attaches `JudgeScore(panel=Panel.final, value=…)` marks to a routine at `level_1`). The assertions:

```python
def test_band_1_3_trims_four_final_marks_to_the_middle_two(make_scored_routine):
    # [10, 11, 12, 13] -> drop 10 and 13 -> mean(11, 12) = 11.50
    routine = make_scored_routine(
        level=Level.level_1,
        marks={Panel.final: [Decimal("10"), Decimal("11"), Decimal("12"), Decimal("13")]},
    )
    result = compute_routine_score(routine)
    assert result.final_score == Decimal("11.50")
    assert result.total == Decimal("11.50")


def test_band_1_3_plain_averages_three_final_marks(make_scored_routine):
    # Three marks is a complete (minimum viable) panel: plain average, no trim.
    # [10, 11, 12] -> mean = 11.00
    routine = make_scored_routine(
        level=Level.level_1,
        marks={Panel.final: [Decimal("10"), Decimal("11"), Decimal("12")]},
    )
    assert compute_routine_score(routine).final_score == Decimal("11.00")


def test_band_1_3_single_final_mark_is_that_mark(make_scored_routine):
    # Backwards compatible: one mark still yields that mark.
    routine = make_scored_routine(
        level=Level.level_1, marks={Panel.final: [Decimal("12.5")]}
    )
    assert compute_routine_score(routine).final_score == Decimal("12.50")
```

If `test_scoring.py` has no `make_scored_routine`-style fixture/helper, build the routine inline the way the nearest existing test does (a `Routine` with an `entry` at `level_1` and a list of `JudgeScore` objects on `Panel.final`); the three assertions above are the contract. Also confirm the exact imports (`Decimal`, `Level`, `Panel`, `compute_routine_score`) are already used in the file and reuse them.

- [ ] **Step 2: Run the tests to verify they fail (or already pass) and understand why**

Run: `cd backend && source .venv/bin/activate && pytest test/test_scoring.py -k "band_1_3 and (four or three or single)" -v`
Expected: the four-mark and three-mark tests are the interesting ones. Because the math is already correct, they may **already pass** against current code — that is expected and fine (they are regression tests locking in behaviour the metadata change must not break). The single-mark test must pass. If any fails, stop and investigate before Step 3.

- [ ] **Step 3: Change the panel metadata and rewrite the misleading comments**

In `backend/app/scoring.py`, replace the `BAND_1_3` comment and definition (lines 52-61):

```python
# Levels 1-3 are judged by a PANEL OF FOUR judges, each handing the scorer one finished
# mark out of 13 (they fold D and E together on paper). The routine's score is the
# trimmed mean of those four marks -- the same aggregation the 4-7 and 8+ bands apply to
# their panels. A minimum viable panel is three marks (plain-averaged, since
# TRIM_THRESHOLD is 4); a fourth mark is optional and switches to the trimmed mean.
BAND_1_3 = ScoringProfile(
    band="1-3",
    panels=frozenset({Panel.final}),
    judges_per_panel=MappingProxyType({Panel.final: 4}),
    medal_mode=MedalMode.cutoff,
    tie_break_on_execution=False,
)
```

Then fix the `compute_routine_score` docstring bullet (lines 179-181) that still says the mark is pre-aggregated by one judge:

```python
    - Levels 1-3: a panel of up to four `final` marks (each out of 13) is combined by
      `trimmed_mean` -- one mark returns itself, three plain-average, four trim to the
      middle two -- less penalty. D/A/E are forced to 0 so a stale mark on another panel
      (direct ORM writes bypass the API's panel gate) cannot leak into the total.
```

Leave the code in the `if profile is BAND_1_3:` branch unchanged — it already calls `rounded(...)` → `trimmed_mean`.

- [ ] **Step 4: Run the scoring tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest test/test_scoring.py -v`
Expected: PASS — including `test_every_level_is_explicitly_banded` and any existing band-1-3 test. The metadata change does not alter math, so nothing else moves.

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: PASS (no regressions — `judges_per_panel` is UI metadata, not enforced at the API).

- [ ] **Step 6: Commit**

```bash
cd /home/altus/workspace/rhythmiq
git add backend/app/scoring.py backend/test/test_scoring.py
git commit -m "fix: levels 1-3 are a four-judge trimmed-mean panel (backend metadata)"
```

---

## Task 2: Frontend four-judge panel (F1–F4)

This is ONE task because the pieces are coupled by TypeScript: changing `BoxKey` breaks `ScoreForm`'s exhaustive `Record<BoxKey, …>` maps, and changing `PreviewInput.finalScore` breaks its call site — none compile in isolation. The task ends with `npm run build` and the full frontend suite green. Within the task, expect intermediate red (that is normal); do NOT commit until Step 12 is green.

**Files:**
- Modify: `frontend/src/features/scoring/panel-storage.ts`, `frontend/src/lib/score-math.ts:107-146`, `frontend/src/features/scoring/save-diff.ts:3-13`, `frontend/src/features/scoring/ScoreForm.tsx` (`BOX_LABELS` 27-38, `BOX_MAX` 43-51, `EMPTY_VALUES` 55-67, `boxesFor` 74-96, preview 211-229)
- Test: `frontend/test/lib/score-math.test.ts`, `frontend/test/features/scoring/panel-storage.test.ts`, `frontend/test/features/scoring/save-diff.test.ts`, `frontend/test/features/scoring/ScoringPage.test.tsx`, `frontend/test/features/scoring/PanelSetupDialog.test.tsx`

**Interfaces:**
- Consumes: nothing from Task 1 (independent).
- Produces: `PanelSlot` union gains `"F1" | "F2" | "F3" | "F4"` and loses `"F"`; `SLOTS_BY_BAND["1-3"] = ["F1","F2","F3","F4"]`; `REQUIRED_SLOTS["1-3"] = ["F1","F2","F3"]`; `PreviewInput.finalScores?: number[]` (no `finalScore`); `BoxKey` gains `"final1".."final4"` and loses `"final"`; `boxesFor(panel, "1-3")` returns four boxes keyed `final1..final4` on panel `"final"` bound to judges `F1..F4`.

- [ ] **Step 1: Update `panel-storage.ts` (slots, required, conflicts, legacy-F migration)**

Replace the `PanelSlot` type (11-21), `PANEL_SLOTS` (23-34), `SLOTS_BY_BAND`/`REQUIRED_SLOTS`/`SLOT_CONFLICT_GROUPS` (37-59), and add the legacy-`F` migration in `loadPanel` (after the `A → A1` block at 80-85). Also update the file's top comment about `"A"` to mention `"F"` too:

```typescript
/**
 * Judge slots across all three scoring bands. "D" is the 8+ difficulty judge and covers
 * both D-Body and D-App (one judge, two marks, two panels — legal because JudgeScore is
 * unique on (routine, judge, panel)). Levels 4-7 instead have TWO body judges, DB1/DB2,
 * and no apparatus difficulty at all — the asymmetry is deliberate, see the spec.
 *
 * loadPanel migrates a stored legacy "A" (the 8+ band's old single artistry slot) to
 * "A1", and a legacy "F" (the levels 1-3 band's old single final slot) to "F1".
 */
export type PanelSlot =
  | "F1"
  | "F2"
  | "F3"
  | "F4"
  | "D"
  | "DB1"
  | "DB2"
  | "A1"
  | "A2"
  | "E1"
  | "E2"
  | "E3"
  | "E4";

export const PANEL_SLOTS: PanelSlot[] = [
  "F1",
  "F2",
  "F3",
  "F4",
  "D",
  "DB1",
  "DB2",
  "A1",
  "A2",
  "E1",
  "E2",
  "E3",
  "E4",
];

/** Which slots each band actually uses — drives the setup dialog's grouping. */
export const SLOTS_BY_BAND: Record<Band, PanelSlot[]> = {
  "1-3": ["F1", "F2", "F3", "F4"],
  "4-7": ["DB1", "DB2", "E1", "E2"],
  "8+": ["D", "A1", "A2", "E1", "E2", "E3", "E4"],
};

/** The minimum viable panel per band; F4/E3/E4 and A2 legitimately stay empty. */
export const REQUIRED_SLOTS: Record<Band, PanelSlot[]> = {
  "1-3": ["F1", "F2", "F3"],
  "4-7": ["DB1", "DB2", "E1", "E2"],
  "8+": ["D", "A1", "E1", "E2"],
};

/**
 * Slots that write to the same API panel, and therefore may not share a judge — a
 * second mark from the same judge on the same panel violates
 * uq_judge_score_routine_judge_panel and the save would fail at the API.
 */
export const SLOT_CONFLICT_GROUPS: PanelSlot[][] = [
  ["F1", "F2", "F3", "F4"],
  ["DB1", "DB2"],
  ["A1", "A2"],
  ["E1", "E2", "E3", "E4"],
];
```

In `loadPanel`, immediately after the existing `A → A1` block (lines 80-85), add the mirror for `F` (raw read from storage, since `"F"` is no longer a `PanelSlot`):

```typescript
    // Panels saved before levels 1-3 became a four-judge panel used a single "F" slot.
    // Read it as F1 rather than dropping it, so a meet in progress keeps its panel.
    // An explicit F1 wins — it is the newer of the two. Mirrors the "A" → "A1" case.
    if (panel.F1 === undefined && typeof stored.F === "number") {
      panel.F1 = stored.F;
    }
```

- [ ] **Step 2: Update `score-math.ts` (`PreviewInput` + `computePreview` 1-3 branch)**

In `frontend/src/lib/score-math.ts`, change `PreviewInput` (line 113) and the `1-3` branch of `computePreview` (lines 134-137):

```typescript
  finalScores?: number[];
```

```typescript
  if (input.band === "1-3") {
    // A panel of up to four marks (each out of 13), combined by the SAME trimmedMean the
    // other bands use: one mark returns itself, three plain-average, four trim to the
    // middle two. The result IS the routine's score, less penalty.
    const final = trimmedMean(input.finalScores ?? []);
    return { d: 0, a: 0, e: 0, final, penalty, total: final - penalty };
  }
```

- [ ] **Step 3: Update `save-diff.ts` (`BoxKey`)**

In `frontend/src/features/scoring/save-diff.ts`, replace `"final"` in the `BoxKey` union (lines 3-13) with the four keys:

```typescript
export type BoxKey =
  | "final1"
  | "final2"
  | "final3"
  | "final4"
  | "dBody1"
  | "dBody2"
  | "dApp"
  | "a1"
  | "a2"
  | "e1"
  | "e2"
  | "e3"
  | "e4";
```

- [ ] **Step 4: Update `ScoreForm.tsx` (labels, caps, empty values, boxesFor, preview)**

In `frontend/src/features/scoring/ScoreForm.tsx`:

`BOX_LABELS` (27-38) — replace `final: "Final"` with four entries (the map is `Record<BoxKey, string>`, so it must be exhaustive):

```typescript
const BOX_LABELS: Record<BoxKey, string> = {
  final1: "Final 1",
  final2: "Final 2",
  final3: "Final 3",
  final4: "Final 4",
  dBody1: "D-Body 1",
  dBody2: "D-Body 2",
  dApp: "D-App",
  a1: "Artistry 1",
  a2: "Artistry 2",
  e1: "E1",
  e2: "E2",
  e3: "E3",
  e4: "E4",
};
```

`BOX_MAX` (43-51) — replace `final: 13` with the four boxes at 13 each:

```typescript
const BOX_MAX: Partial<Record<BoxKey | "penalty", number>> = {
  final1: 13,
  final2: 13,
  final3: 13,
  final4: 13,
  a1: 10,
  a2: 10,
  e1: 10,
  e2: 10,
  e3: 10,
  e4: 10,
};
```

`EMPTY_VALUES` (55-67) — replace `final: ""` with the four keys (`FormValues` is `Record<BoxKey | "penalty", string>`, exhaustive):

```typescript
const EMPTY_VALUES: FormValues = {
  final1: "",
  final2: "",
  final3: "",
  final4: "",
  dBody1: "",
  dBody2: "",
  dApp: "",
  a1: "",
  a2: "",
  e1: "",
  e2: "",
  e3: "",
  e4: "",
  penalty: "",
};
```

`boxesFor` 1-3 branch (75-77) — return four boxes bound to `F1..F4`:

```typescript
  if (band === "1-3") {
    return [
      { key: "final1", panel: "final" as Panel, judgeId: panel.F1 },
      { key: "final2", panel: "final" as Panel, judgeId: panel.F2 },
      { key: "final3", panel: "final" as Panel, judgeId: panel.F3 },
      { key: "final4", panel: "final" as Panel, judgeId: panel.F4 },
    ];
  }
```

Preview call (line 227) — replace `finalScore: parseBox(watched.final)` with the four box values collected as `finalScores`:

```typescript
    finalScores: [
      parseBox(watched.final1),
      parseBox(watched.final2),
      parseBox(watched.final3),
      parseBox(watched.final4),
    ].filter((v): v is number => v !== undefined),
```

Leave the `defaultValues` loop (154-176), `submit` (231+), `boxInput`, and the `Final: {fmt(preview.final)}` render line (332) unchanged — they iterate `boxes`/read `preview.final` generically. The four `final` boxes are correctly excluded from the E deduction round trip because their keys are not in `E_BOX_KEYS`.

- [ ] **Step 5: Update `score-math.test.ts` (trimmed mean at 1-3)**

In `frontend/test/lib/score-math.test.ts`, replace the two `computePreview({ band: "1-3", finalScore: … })` cases (around lines 84-97) and add the trimmed-mean case. Keep the `profile.panels` assertion at line 26 unchanged (`["final"]` is the API panel, not a box key):

```typescript
  it("records the trimmed final mark at levels 1-3", () => {
    // One mark returns itself.
    expect(computePreview({ band: "1-3", finalScores: [11.75] })).toEqual({
      d: 0,
      a: 0,
      e: 0,
      final: 11.75,
      penalty: 0,
      total: 11.75,
    });
  });

  it("trims four final marks to the middle two at levels 1-3", () => {
    // [10, 11, 12, 13] -> drop 10 and 13 -> mean(11, 12) = 11.5
    expect(computePreview({ band: "1-3", finalScores: [10, 11, 12, 13] }).final).toBeCloseTo(
      11.5,
    );
  });

  it("plain-averages three final marks at levels 1-3", () => {
    // [10, 11, 12] -> 11 (below TRIM_THRESHOLD, no trim)
    expect(computePreview({ band: "1-3", finalScores: [10, 11, 12] }).final).toBeCloseTo(11);
  });

  it("subtracts penalty from the final mark at levels 1-3", () => {
    expect(
      computePreview({ band: "1-3", finalScores: [12], penalty: 0.3 }).total,
    ).toBeCloseTo(11.7);
  });
```

If there is a test asserting `computePreview` with no `1-3` scores yields `final: 0` (around line 110), leave its expectation (`preview.final` is 0 when `finalScores` is omitted, since `trimmedMean([])` is 0).

- [ ] **Step 6: Update `panel-storage.test.ts` (slot order, SLOTS/REQUIRED, conflict, legacy F)**

In `frontend/test/features/scoring/panel-storage.test.ts`:

The slot-order test (around line 31) currently expects `"F"` first — change to the four F slots. Verify against the new `PANEL_SLOTS` order:

```typescript
it("orders slots F1-F4, D, DB1, DB2, A1, A2, E1-E4", () => {
  expect(PANEL_SLOTS).toEqual([
    "F1", "F2", "F3", "F4", "D", "DB1", "DB2", "A1", "A2", "E1", "E2", "E3", "E4",
  ]);
});
```

The `SLOTS_BY_BAND`/`REQUIRED_SLOTS` assertions (69, 76) — update the 1-3 expectations:

```typescript
  expect(SLOTS_BY_BAND["1-3"]).toEqual(["F1", "F2", "F3", "F4"]);
```

```typescript
  expect(REQUIRED_SLOTS["1-3"]).toEqual(["F1", "F2", "F3"]);
```

The load test at line 62-65 that stores `{ F: 1, DB1: 2, … }` and expects the same back: `F` now migrates to `F1`, so update the expectation:

```typescript
  expect(loadPanel(7)).toEqual({ F1: 1, DB1: 2, DB2: 3, A1: 4, A2: 5 });
```

Add two tests mirroring the existing `A → A1` pair (near line 46-53):

```typescript
it("migrates a legacy F slot to F1", () => {
  localStorage.setItem("rhythmiq.panel.8", JSON.stringify({ F: 9 }));
  expect(loadPanel(8)).toEqual({ F1: 9 });
});

it("does not let a legacy F overwrite an explicit F1", () => {
  localStorage.setItem("rhythmiq.panel.9", JSON.stringify({ F: 9, F1: 3 }));
  expect(loadPanel(9)).toEqual({ F1: 3 });
});
```

If `SLOT_CONFLICT_GROUPS` is imported/asserted anywhere in this file, add `["F1","F2","F3","F4"]` to the expected groups; if it is not currently tested, add a focused assertion:

```typescript
it("groups F1-F4 as conflicting (all write the final panel)", () => {
  expect(SLOT_CONFLICT_GROUPS).toContainEqual(["F1", "F2", "F3", "F4"]);
});
```

(Import `SLOT_CONFLICT_GROUPS` at the top of the file if not already imported.)

- [ ] **Step 7: Update `save-diff.test.ts` (the `"final"` boxKey)**

In `frontend/test/features/scoring/save-diff.test.ts`, the reconcile test around lines 84-87 uses `{ key: "final", … }`. Change the two `"final"` box-key literals to `"final1"` (the panel value `"final"` stays — it is the API panel, not the box key):

```typescript
    const finalBoxes: BoxDef[] = [{ key: "final1", panel: "final", judgeId: 3 }];
    const marks: ExistingScore[] = [{ id: 155, judge_id: 1, panel: "final", value: 10.1 }];
    expect(reconcileBoxesWithHistory(finalBoxes, marks)).toEqual([
      { key: "final1", panel: "final", judgeId: 1 },
```

- [ ] **Step 8: Update `ScoringPage.test.tsx` (F→F1 seeds, Final labels, minimum-viable panel)**

In `frontend/test/features/scoring/ScoringPage.test.tsx`:

Panel seeds that set `F: 1` (e.g. line 35) — change to `F1: 1` (the live slot; a raw `F` would still migrate, but tests should use the current slot). If a test needs the 1-3 form to show marks, seed the required three: `{ F1: 1, F2: 2, F3: 3 }`.

The minimum-viable-panel test (around lines 366-373) — update the seed and the awaited label:

```typescript
test("level 1-3 competitors need only three Final slots, not D/A/E3/E4", async () => {
  savePanel(5, { F1: 1, F2: 2, F3: 3 });
  // …existing render setup…
  // Band 1-3 renders Final boxes -- no E1 to wait on.
  await screen.findByLabelText("Final 1");
  expect(screen.getByLabelText("Final 2")).toBeInTheDocument();
  expect(screen.getByLabelText("Final 3")).toBeInTheDocument();
  expect(screen.queryByLabelText("E1")).not.toBeInTheDocument();
  // …rest of existing assertions, replacing any getByLabelText("Final") with "Final 1"…
});
```

Search the whole file for `getByLabelText("Final")` / `findByLabelText("Final")` and any remaining `F:`/`{ F` panel seeds; update each to the `Final 1`…/`F1`… equivalents. Preserve every other assertion.

- [ ] **Step 9: Update `PanelSetupDialog.test.tsx` (F→F1..F4 labels)**

In `frontend/test/features/scoring/PanelSetupDialog.test.tsx`, the assertion at line 129 `getByLabelText("F")` — replace with the four F slot labels the 1-3 setup now renders:

```typescript
  expect(screen.getByLabelText("F1")).toBeInTheDocument();
  expect(screen.getByLabelText("F2")).toBeInTheDocument();
  expect(screen.getByLabelText("F3")).toBeInTheDocument();
  expect(screen.getByLabelText("F4")).toBeInTheDocument();
```

If that test exercises the 1-3 band's setup by selecting a level/band, confirm the dialog renders `F1..F4` from `SLOTS_BY_BAND["1-3"]`; if the test instead lists slots for a different band, only change the `"F"` reference. Do not weaken any other assertion.

- [ ] **Step 10: Typecheck + build**

Run: `cd frontend && npm run build`
Expected: PASS. If TypeScript flags a missing/extra `BoxKey` in `BOX_LABELS`/`EMPTY_VALUES`, or a stale `panel.F`/`watched.final`/`finalScore` reference, fix it — those errors are the type system enforcing completeness of this change. Grep for stragglers if needed: `grep -rn "\.F\b\|watched.final\b\|finalScore\|\"final\"\|'final'" frontend/src/features/scoring frontend/src/lib` should show only the API panel value `"final"` (in `score-math.ts` `panels` and `save-diff`/`ScoreForm` `panel: "final"`), never a box key `final` or slot `F`.

- [ ] **Step 11: Run the full frontend suite**

Run: `cd frontend && npm test -- --run`
Expected: PASS. If a test outside the five above fails, it hardcoded the single-`F`/single-`final` assumption — read it, confirm the failure is the expected label/slot change (not a real regression), and update it the same mechanical way. Do not change production behaviour to satisfy a stale test.

- [ ] **Step 12: Commit**

```bash
cd /home/altus/workspace/rhythmiq
git add frontend/src/features/scoring/panel-storage.ts frontend/src/lib/score-math.ts \
  frontend/src/features/scoring/save-diff.ts frontend/src/features/scoring/ScoreForm.tsx \
  frontend/test/lib/score-math.test.ts frontend/test/features/scoring/panel-storage.test.ts \
  frontend/test/features/scoring/save-diff.test.ts \
  frontend/test/features/scoring/ScoringPage.test.tsx \
  frontend/test/features/scoring/PanelSetupDialog.test.tsx
git commit -m "feat: levels 1-3 score form is a four-judge panel (F1-F4)"
```

---

## Task 3: Documentation

**Files:**
- Modify: `CLAUDE.md` — the scoring-bands paragraph and the frontend slots line.

**Interfaces:** none.

- [ ] **Step 1: Update the scoring-bands paragraph**

In `CLAUDE.md`, find the sentence in the **Scoring bands** bullet that reads:

> Levels 1–3 record a single pre-aggregated mark on `Panel.final` (max 13, no averaging, no tie-break); levels 4–7 use two `difficulty_body` judges…

Replace the levels 1–3 clause so it describes the four-judge panel:

> Levels 1–3 are judged by a panel of up to four judges, each recording one mark on `Panel.final` (max 13); the routine's score is the trimmed mean of those marks (three plain-average, four trim to the middle two), still no tie-break; levels 4–7 use two `difficulty_body` judges…

- [ ] **Step 2: Update the frontend slots line**

Find the frontend line listing the judge slots:

> Slots are band-dependent: `F` (levels 1–3), `DB1`/`DB2` (4–7), `D`/`A1`/`A2` (8+), and `E1`–`E4`; a stored legacy `A` is read as `A1`.

Replace it with:

> Slots are band-dependent: `F1`–`F4` (levels 1–3), `DB1`/`DB2` (4–7), `D`/`A1`/`A2` (8+), and `E1`–`E4`; a stored legacy `A` is read as `A1` and a stored legacy `F` as `F1`.

- [ ] **Step 3: Commit**

```bash
cd /home/altus/workspace/rhythmiq
git add CLAUDE.md
git commit -m "docs: levels 1-3 four-judge panel in CLAUDE.md"
```

---

## Self-Review

**Spec coverage** (against `docs/superpowers/specs/2026-07-23-level-1-3-four-judge-panel-design.md`):

| Spec item | Task |
|---|---|
| `BAND_1_3.judges_per_panel` `{final: 1}` → `{final: 4}` | Task 1 Step 3 |
| Rewrite the "exactly one judge / nothing is averaged" comments | Task 1 Step 3 |
| Backend band-1-3 test: four marks trim (`[10,11,12,13]→11.50`), three plain-average (`[10,11,12]→11.00`) | Task 1 Step 1 |
| No migration, no schema change | Global Constraints (none added) |
| Medals/tie-break unchanged (`tie_break_on_execution` false) | Global Constraints (untouched) |
| `PanelSlot`/`PANEL_SLOTS` add `F1..F4`, `F` legacy-only | Task 2 Step 1 |
| `SLOTS_BY_BAND["1-3"]` = `["F1","F2","F3","F4"]` | Task 2 Step 1 |
| `REQUIRED_SLOTS["1-3"]` = `["F1","F2","F3"]` (F4 optional) | Task 2 Step 1 |
| `SLOT_CONFLICT_GROUPS` gains `["F1","F2","F3","F4"]` | Task 2 Step 1 |
| `loadPanel` migrates legacy `"F"` → `"F1"` when `F1` unset | Task 2 Step 1 |
| `PreviewInput.finalScore` → `finalScores?: number[]` | Task 2 Step 2 |
| `computePreview` `1-3`: `final = trimmedMean(finalScores)` | Task 2 Step 2 |
| `boxesFor("1-3")` returns four boxes `final1..final4` / panel `final` / judges `F1..F4` | Task 2 Step 4 |
| Default form state gains `final1..final4` | Task 2 Step 4 (`EMPTY_VALUES`) |
| `Final:` preview feeds four box values as `finalScores` | Task 2 Step 4 |
| `BoxKey` `"final"` → `"final1".."final4"` (design under-specified; required for four distinct boxes) | Task 2 Step 3 |
| Update `score-math` worked examples (trimmed mean at 1-3) | Task 2 Step 5 |
| Update `panel-storage` tests (conflict group + legacy `F`) | Task 2 Step 6 |
| Update `ScoreForm`/scoring-page box-count expectations for 1-3 | Task 2 Steps 8-9 |
| `CLAUDE.md` scoring-bands paragraph + slots line | Task 3 |

Two items the design did not spell out but the code requires, both folded into Task 2: `save-diff.ts`'s `BoxKey` must gain `final1..final4` (each of four boxes needs a distinct form/diff key, exactly like `e1..e4`), and `save-diff.test.ts` + `ScoringPage.test.tsx` + `PanelSetupDialog.test.tsx` hardcode the old single-`F`/single-`final` labels and must be updated or the suite fails. The design's testing section named only three test files; the extra two are enumerated in Task 2 Steps 7 and 9.

**Placeholder scan:** every code step shows the code; every run step states the command and expected result. The only judgement calls left to the implementer (finding the nearest existing `test_scoring.py` routine-builder in Task 1 Step 1; locating stray `getByLabelText("Final")` in Task 2 Step 8) are framed with the exact contract to satisfy, not left open.

**Type consistency:** `finalScores` (not `finalScore`) is used in `score-math.ts`, `ScoreForm.tsx`, and every test. `final1..final4` is used consistently as `BoxKey` (save-diff), `BOX_LABELS`/`BOX_MAX`/`EMPTY_VALUES` keys, and `boxesFor` box keys. `F1..F4` is used consistently as `PanelSlot`, in `SLOTS_BY_BAND`/`REQUIRED_SLOTS`/`SLOT_CONFLICT_GROUPS`, and as the `judgeId` source in `boxesFor`. The API panel value stays `"final"` everywhere (never renamed).
