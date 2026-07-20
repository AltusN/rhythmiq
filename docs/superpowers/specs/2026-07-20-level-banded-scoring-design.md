# Level-banded scoring — design

**Date:** 2026-07-20
**Status:** design agreed, three questions open (see end)
**Supersedes:** the `E_ONLY_LEVELS` rule shipped in `app/scoring.py`

## Why

Scoring currently has two bands: levels 1–7 are Execution-only, levels 8+ get the
full D+A+E panel (`app/scoring.py:23`, `is_panel_valid_for_level`). That is wrong.
There are **three** bands, they differ in more than which panels apply, and two of
the differences change what a stored number *means* rather than just how it is
combined.

This is a **spec change, not a feature addition**. The backend today actively
rejects a Difficulty mark at level 4, which the new rules require.

## The three bands

| Band | Scorer enters | Computation | Max per routine |
|---|---|---|---|
| **1–3** | one final mark per judge (D already folded in by the judge) | `average(final marks)` | **13** |
| **4–7** | DB1, DB2 + E1, E2 | `average(DB) + E` | **13** |
| **8+** | DB, DA, A1, A2, E1–E4 | `(DB + DA) + average(A) + trimmedMean(E)` | FIG open |

Penalty is subtracted from the total in every band.

Execution is **always out of 10**, at every level. Difficulty at levels 4–7 is
assumed out of 3 (13 − 10) — *open question 1*.

### Levels 1–3 are pre-aggregated, not E-only

The judges compute D+E on paper and hand the scorer a single finished number out
of 13. The application is not calculating a score at this band; it is recording
one. This is why the band cannot be modelled as "E-only".

### Levels 4–7 keep the existing additive D formula unchanged

There is **no DA** at this band — two judges both score DB, and those two marks are
averaged. The shipped formula already produces this:

```python
d_score = rounded(by_panel[difficulty_body]) + rounded(by_panel[difficulty_apparatus])
```

With no DA marks, `trimmed_mean([])` returns 0, so `D = average(DB1, DB2) + 0`.
**Adding zero is a no-op** — the D math needs no change at all.

Likewise `trimmed_mean` already returns a plain average below `TRIM_THRESHOLD = 4`,
so "average 2 E marks" is existing behaviour.

### Deliberate asymmetry

Levels 4–7 have **two** DB judges; level 8+ has **one** DB and **one** DA. This is
intentional (confirmed 2026-07-20). Do not "fix" it into consistency.

## Decision: a distinct `Panel.final` for levels 1–3

The level 1–3 mark is neither an execution score nor a difficulty score. It gets its
own `Panel` member rather than being stored as an existing panel.

**Rejected:** storing it as `Panel.execution` with the cap raised to 13.
`models.py:213` caps E at 10 *because E is always out of 10* — a guarantee that
holds at every level. Relaxing that constraint to accommodate a different quantity
wearing E's name weakens a real invariant at levels 8+. That is the failure mode
behind finding C3 (one name, two meanings, two implementations, divergence). A
distinct panel keeps every stored value's meaning invariant across bands.

**Rejected:** storing it as D (uncapped). Every level 1–3 competitor would then tie
on `e_score = 0`, collapsing any E-based ordering.

**Cost:** one `ALTER TYPE ... ADD VALUE` migration, hand-written — autogenerate does
not detect new enum values (see CLAUDE.md).

## Decision: convert deductions at entry

**The E panel always receives deductions**, at every level (confirmed 2026-07-20).
A judge writes `1.5` meaning 1.5 off, and `E = 10 − 1.5 = 8.5`.

The one exception is levels 1–3, which have no separate E entry at all — the scorer
receives a single already-finished mark there, so there is nothing to convert.

Because the rule is universal rather than band-specific, the conversion belongs in
one place at the form boundary, **not** in the per-band scoring profile.

`JudgeScore.value` stores the **resulting E score**, not the deduction. The form
accepts a deduction and converts before persisting.

**Why:** ranking breaks ties on highest E (`scoring.py:182`, per FIG Technical
Regulations). Storing raw deductions would invert that — highest deduction is the
*worst* execution — and would silently reverse tied competitors. Converting at entry
keeps one invariant across the whole system: *a `value` on an E panel is always an
execution score out of 10*, and confines the deduction concept to the UI, where the
judge actually thinks in it.

Trimming is unaffected either way: discarding the highest and lowest deduction
selects the same marks as discarding the lowest and highest score.

## Decision: architecture — one declarative scoring profile

Replace the boolean `E_ONLY_LEVELS` / `isEOnlyLevel` with a single table mapping band
→ `{panels, judge counts, D combination, medal mode}`. `app/scoring.py` derives both
validity and math from it; `frontend/src/lib/score-math.ts` mirrors it, exactly as
those two files already mirror each other.

**Why not extend the existing predicates:** this rule has to be known in at least
five places — backend validity, backend math, frontend math mirror, the judge-slot
panel UI, and the score form's box layout. Finding C3 exists precisely because the
lock rule was implemented twice and diverged, while the medal-cutoff rule stayed
consistent across four layers because it was specified once and implemented downward.

**Why not configurable data (a `level_scoring_profile` table):** YAGNI. Levels are an
enum and bands change on FIG's cycle, not weekly.

## Ranking and medals

### No tie-breaking at levels 1–7

Ties are not broken at these bands. Tied competitors share a rank. The E-based
tie-break stays for level 8+ only.

At levels 1–3 there is no separable E to break on anyway.

### Two medal systems

- **Levels 1–3: score cutoffs.** `Meet.medal_gold_min` / `medal_silver_min`, applied
  to the **final all-around result**, not a single routine. Levels 1–3 compete on
  **2 apparatus**, so the all-around max is **26** (13 + 13) and a gold cutoff around
  24 is normal. The existing `medal_for_total` already implements this.
- **Levels 4–7: placement.** No cutoffs. Medals go to the first three **distinct
  total values**, and ties share a medal:
  - two tied at top → gold, gold; next distinct → silver; next distinct → bronze
  - one winner, two tied second → gold; silver, silver; then 4th → bronze

**Ranks are unchanged** — competition ranking (1,2,2,4) stays as documented in
CLAUDE.md. Medal assignment is a **separate pass over distinct totals**, not a lookup
of `rank <= 3`. Implementing it as `rank <= 3` would deny bronze to the 4th-place
gymnast in the second example above.

## What does not change

- `JudgeScore` schema. DB1/DB2 are two *judges* on one `difficulty_body` panel, and
  the table is already keyed `(routine, judge, panel)` with uniqueness on that triple.
- The additive D formula (see above).
- `trimmed_mean` itself.
- Competition ranking semantics.
- No existing data becomes invalid: current level 4–7 routines hold only E marks,
  which stays legal under the new rules — merely incomplete. No backfill needed.

## Consequences to handle

1. **Seed data medal cutoffs** are currently gold 24.00 / silver 21.00. These are
   *correct* for a levels 1–3 all-around out of 26 — but the seed must ensure they
   are only meaningful for that band.
2. **A7's medal-cutoff copy** (open in the punch list) should teach the 0–26
   all-around scale, and note the fields apply to levels 1–3 only.
3. **The judge-slot panel UI** (`rhythmiq.panel.<meetId>` in localStorage) has slots
   `D, A, E1–E4`. It needs DB1/DB2 at levels 4–7, A1/A2 at 8+, and a single final
   slot at 1–3.
4. **Finding B4 is largely resolved** by fixing E panel size per band: the E formula
   stops varying invisibly with who turned up.
5. **`ScoreForm` box layout** becomes band-dependent (1 box / 4 boxes / 8 boxes).

## Open questions

1. **Is D at levels 4–7 out of 3?** Inferred from 13 − 10, not confirmed.
2. **How many judges submit a final mark at levels 1–3** — one, or several averaged?
3. **Do levels 8+ use placement medals, cutoffs, or neither?** Only 1–3 (cutoffs) and
   4–7 (placement) have been specified.

**Answered 2026-07-20:** the E panel always receives deductions, at every level, and
they are converted to a score at entry (was open question 2).
