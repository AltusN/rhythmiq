# Levels 1–3: four-judge panel (correction)

**Date:** 2026-07-23
**Status:** Design agreed, awaiting spec review
**Supersedes:** the "levels 1–3 = one pre-aggregated mark" premise in
`2026-07-20-level-banded-scoring-design.md` (that band's *math* is unaffected; only the
panel size and its framing change).

## Problem

The shipped level-banded scoring model treats levels 1–3 as a single finished mark out of
13 on `Panel.final` — "from the scorer's point of view there is exactly one judge, so
nothing is averaged." That is wrong. Levels 1–3 are judged by a **panel of four judges**,
each of whom submits one finished mark out of 13. The routine's score is the **trimmed
mean** of those four marks (drop the highest and lowest, average the remaining two) — the
same aggregation the 4–7 and 8+ bands already apply to their multi-judge panels.

## Scope of the correction

The surprising result of reading the code: the **backend scoring math is already
correct**. `compute_routine_score`'s `BAND_1_3` branch routes every `Panel.final` mark
through `trimmed_mean`, which returns the single mark when there is one and the trimmed
mean when there are four. The defect is entirely in **panel metadata, the frontend, and
documentation** — the pieces that assumed a single judge.

### Unchanged (verified)

- **Backend scoring math** (`app/scoring.py compute_routine_score`): no logic change.
  `trimmed_mean` over `Panel.final` already delivers the required behaviour.
- **Database schema**: no migration. Each judge's mark is still ≤ 13, so the existing
  `Panel.final` per-mark CHECK (≤ 13) is correct. `JudgeScore` is unique on
  `(routine, judge, panel)`, so four judges writing `final` is already legal.
- **Medals & tie-break**: levels 1–3 keep cutoff medals on the all-around; there is still
  no E component, so `tie_break_on_execution` stays `false`.
- **The E round trip**: untouched — levels 1–3 marks are straight scores, never
  deductions.
  > **SUPERSEDED 2026-07-23:** the user later clarified that levels 1–3 judges DO enter
  > deductions. Shipped: the form converts off a base of 13 (`finalDeductionToScore` /
  > `finalScoreToDeduction`, `FINAL_MAX = 13`) and the DB stores the score out of 13 —
  > the same round trip as E, base 13 not 10. See CLAUDE.md's scoring notes.

### Decisions

- **Four judges, one mark each**, on `Panel.final`, each ≤ 13.
- **Aggregation: trimmed mean.** Reuses `trimmed_mean` / `trimmedMean` as-is.
- **Minimum viable panel is three judges.** A routine with 3 marks is complete; with 4 it
  is fuller. This requires **no threshold logic**: `TRIM_THRESHOLD = 4` already means 3
  marks plain-average and 4 marks trim. `F4` is optional, like `E4`/`A2` today.
- **Per-judge slots `F1 F2 F3 F4`**, mirroring 4–7's `DB1/DB2/E1/E2`. A stored legacy
  `"F"` migrates to `"F1"`, mirroring the existing `"A" → "A1"` migration.

## Changes by file

### Backend

- `app/scoring.py`:
  - `BAND_1_3.judges_per_panel`: `{Panel.final: 1}` → `{Panel.final: 4}`.
  - Rewrite the `BAND_1_3` and `compute_routine_score` comments that assert "exactly one
    judge / nothing is averaged" — it now trims four marks. The code stays as-is.
- `test/` (scoring): add a band-1-3 test proving four marks trim to the middle two
  (e.g. `[10, 11, 12, 13] → 11.50`) and that three marks plain-average
  (e.g. `[10, 11, 12] → 11.00`).

### Frontend

- `src/features/scoring/panel-storage.ts`:
  - `PanelSlot` / `PANEL_SLOTS`: add `F1 F2 F3 F4` (keep `F` only as a legacy-read alias
    handled in `loadPanel`; it is not offered as a live slot).
  - `SLOTS_BY_BAND["1-3"]` → `["F1","F2","F3","F4"]`.
  - `REQUIRED_SLOTS["1-3"]` → `["F1","F2","F3"]` (F4 optional).
  - `SLOT_CONFLICT_GROUPS`: add `["F1","F2","F3","F4"]` (all write `Panel.final`, must be
    distinct judges).
  - `loadPanel`: migrate a stored legacy `"F"` to `"F1"` when `F1` is unset.
- `src/lib/score-math.ts`:
  - `PreviewInput.finalScore?: number` → `finalScores?: number[]`.
  - `computePreview` `1-3` branch: `final = trimmedMean(finalScores)`.
  - Update the "the entered mark IS the score" / "single mark" comments.
- `src/features/scoring/ScoreForm.tsx`:
  - `boxesFor("1-3")` returns four boxes (`final1..final4`, panel `final`, judges
    `F1..F4`).
  - Default form state gains `final1..final4`.
  - The `Final:` preview line feeds the four box values into `computePreview` as
    `finalScores`.
- `frontend/test/`: update `score-math` worked examples (trimmed mean at 1–3),
  `panel-storage` (new conflict group + legacy `"F"` migration), and `ScoreForm`
  box-count expectations for the 1–3 band.

### Docs

- `CLAUDE.md`:
  - Scoring-bands paragraph: "single pre-aggregated mark on `Panel.final` (max 13, no
    averaging, no tie-break)" → four judges, trimmed mean, still no tie-break.
  - Frontend slots line: `F` (levels 1–3) → `F1`–`F4` (levels 1–3), legacy `F` read as
    `F1`.

## Out of scope

- The pre-existing "cutoff medals on the per-apparatus `/standings` endpoint compare
  against the max-26 all-around cutoffs, so every 1–3 competitor reads as bronze there"
  issue (noted in the level-banded design's open-decisions). Independent of panel size;
  left for its own decision.
- Judge self-scoring / per-exercise FIG judging records — the four `F` slots make per-judge
  attribution *possible* at 1–3, but the live-entry and records work stays deferred.

## Testing strategy

Backend and frontend worked-example tests are the contract between `scoring.py` and
`score-math.ts`; both gain the four-judge trimmed-mean case. Panel-storage tests cover the
new conflict group and the legacy-`F` migration. `ScoreForm` tests assert the 1–3 band now
renders four score boxes bound to `F1..F4`. No new migration, so no migration round-trip
test.
