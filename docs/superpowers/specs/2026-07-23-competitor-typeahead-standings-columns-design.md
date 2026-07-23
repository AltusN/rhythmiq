# Competitor typeahead + band-aware standings columns

**Date:** 2026-07-23
**Status:** Design approved, pending implementation plan

## Context

Two meet-day UI corrections, plus one item that turned out to need no work.

1. **Adding a competitor uses a plain `<select>`.** `EntryCreateForm.tsx` renders every
   gymnast (or group) as an `<option>`. With a real roster that list is long and
   unsearchable — the operator wants to type a name and have the list filter.
2. **The apparatus standings table shows meaningless `0.00` D/A/E for levels 1–3.** A 1–3
   routine's whole score is a single `final` mark; its `d_score`/`a_score`/`e_score` are
   always 0, but the table renders them as `0.00`, which reads as real zeros. The same
   table also shows `A = 0.00` for levels 4–7, which have no artistry panel.
3. **Cutoff medals on per-apparatus standings — ALREADY CORRECT, no work.** `_apparatus_medal`
   in `app/routers/results.py` already returns `None` for cutoff bands (levels 1–3) on the
   per-apparatus endpoint (their max-26 all-around cutoffs don't apply to a single 0–13
   routine). That is why MEDAL is correctly empty for 1–3 on the Apparatus tab; 1–3 cutoff
   medals appear only on the All-Around tab, where the scale matches. Documented here so a
   future reader does not "re-fix" it. No change.

Both changes are **frontend-only**. No backend, schema, or API change.

## Item B — Competitor typeahead

### Component: `CompetitorCombobox`

A new reusable component, `frontend/src/features/entries/CompetitorCombobox.tsx`, replacing
the Competitor `<select>` in `EntryCreateForm.tsx`. One clear job: filter a list of
labelled options as the user types and report the selected id.

Props:

```ts
interface CompetitorComboboxOption {
  id: number;
  label: string;
}
interface CompetitorComboboxProps {
  options: CompetitorComboboxOption[];
  value: string;                 // selected id as a string ("" = none), matching RHF
  onChange: (id: string) => void;
  ariaLabel?: string;            // default "Competitor"
}
```

Behaviour:

- A single text input (`role="combobox"`, `aria-label` from the prop) plus a dropdown list
  of matching options rendered while the input is focused and there is at least one match.
- **Filter (case-insensitive, name-part prefix):** an option matches when **any
  whitespace-separated part of its label starts with** the typed query. Empty query → all
  options. So `"Le"` matches `"Leah Geyer"` (first part), `"Ge"` matches it (second part),
  `"ah"` matches nothing (not a start). This is `matchesNamePartPrefix(label, query)`,
  exported for direct unit testing.
- **Selecting** an option (click or Enter on the highlighted row) calls `onChange(String(id))`
  and puts the option's label in the input, closing the list.
- **Keyboard:** ArrowDown/ArrowUp move the highlight within the filtered list (wrapping is
  not required); Enter selects the highlighted option; Escape closes the list without
  changing the value.
- **Typing after a selection** re-opens the list and filters again; clearing the input to a
  string that matches no option leaves `value` unchanged until another option is chosen
  (the form's zod `min(1)` still guards submit).
- The input's displayed text is derived from `value` on mount/prop change (show the selected
  option's label) so re-rendering with a value shows the chosen name.

Deliberately **no new dependency** (CLAUDE.md keeps the dep list minimal) — a small
controlled component, not react-select/Downshift.

### Wiring in `EntryCreateForm.tsx`

- Map the current `kind` list to options: gymnasts → `{ id, label: "First Last" }`; groups →
  `{ id, label: name }`.
- Render `<CompetitorCombobox options={...} value={watch("competitorId")}
  onChange={(id) => setValue("competitorId", id, { shouldValidate: true })}
  ariaLabel="Competitor" />` in place of the `<select>` (RHF `setValue`, since the combobox
  is not a native input `register` can bind).
- Toggling Gymnast/Group already changes the option list; also clear the selection
  (`setValue("competitorId", "")`) on that toggle so a stale gymnast id can't submit as a
  group. The existing zod field, error display, bib/level/age/fee fields, and submit are
  unchanged.

## Item C — Band-aware standings columns

In `StandingsPage.tsx`'s apparatus table, render each of the D / A / E cells as its number
only when the row's band uses that panel, else an em dash `"—"`. Derive the band per row
from `profileForLevel(row.level)` (already exported from `frontend/src/lib/score-math.ts`;
it returns `{ panels: string[] }`).

- **D** cell: number if `panels` includes `"difficulty_body"` or `"difficulty_apparatus"`,
  else `"—"`.
- **A** cell: number if `panels` includes `"artistry"`, else `"—"`.
- **E** cell: number if `panels` includes `"execution"`, else `"—"`.

Effect: 1–3 rows show `"—"` for D/A/E (the mark shows in **Total**); 4–7 rows show `"—"`
for A; 8+ rows show all three. Rank/Bib/Competitor/Level/Pen/Total/Medal are unchanged.
Because it is computed per row, a mixed "All levels" table renders each row by its own band.
The all-around table (Total/Routines/Medal) is untouched. No separate "Final" column is
added — Total already carries the 1–3 mark (less penalty).

Small helper (local to `StandingsPage.tsx`, or colocated): `panelApplies(level, panel)` or
inline checks against `profileForLevel(level).panels`.

## Testing

- **`matchesNamePartPrefix`** unit tests: `"Le"`→matches `"Leah Geyer"`; `"Ge"`→matches;
  `"ah"`→no; empty query→matches; case-insensitive (`"le"` matches).
- **`CompetitorCombobox`** component tests (Testing Library): typing filters the visible
  options; clicking an option calls `onChange` with the id and shows the label; ArrowDown +
  Enter selects; Escape closes without change.
- **`EntryCreateForm` / EntriesPage**: update the existing "creates a gymnast entry" test to
  drive the combobox (type part of the name, pick the option) instead of `selectOptions`,
  and assert the POST body still carries the right `gymnast_id`. Also assert switching to
  Group clears a previously chosen gymnast.
- **`StandingsPage`**: a level-1 apparatus row renders `"—"` for D/A/E and its mark in
  Total; an 8+ row renders numbers for D/A/E; (optional) a 4–7 row renders `"—"` for A.

All tests use existing MSW fixtures / synthetic data. No backend test changes.

## Out of scope

- The Scoring page's existing "Search name or bib…" competitor filter (separate component,
  already a filter; not touched).
- Bib-number matching in the add-entry picker (no bib exists at pick time).
- Any backend/medal change (Item 3 needs none).
- A separate "Final" column for 1–3 standings (Total suffices).
