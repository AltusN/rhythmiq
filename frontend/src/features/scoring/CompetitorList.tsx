import type { MeetEntryRead } from "../../api/types";
import { AGE_GROUPS, APPARATUS, LEVELS, labelize } from "../../lib/domain";

interface CompetitorListProps {
  entries: MeetEntryRead[];
  nameFor: (entry: MeetEntryRead) => string;
  scoredTotals: ReadonlyMap<number, string>;
  selectedEntryId: number | null;
  onSelect: (entry: MeetEntryRead) => void;
  search: string;
  onSearchChange: (s: string) => void;
  level: string;
  onLevelChange: (l: string) => void;
  ageGroup: string;
  onAgeGroupChange: (a: string) => void;
  apparatus: string;
  onApparatusChange: (a: string) => void;
}

export function CompetitorList({
  entries,
  nameFor,
  scoredTotals,
  selectedEntryId,
  onSelect,
  search,
  onSearchChange,
  level,
  onLevelChange,
  ageGroup,
  onAgeGroupChange,
  apparatus,
  onApparatusChange,
}: CompetitorListProps) {
  const needle = search.trim().toLowerCase();
  const visible = entries.filter(
    (e) =>
      needle === "" ||
      (e.bib_number ?? "").toLowerCase().includes(needle) ||
      nameFor(e).toLowerCase().includes(needle),
  );

  return (
    <div className="w-72 shrink-0">
      <div className="text-xs font-semibold uppercase text-gray-500">Competitors</div>
      <input
        aria-label="Search competitors"
        placeholder="Search name or bib…"
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
        className="my-2 w-full rounded border border-gray-300 p-1 text-sm"
      />
      {/*
        Apparatus is NOT a filter. Level and age group narrow which competitors are
        listed; apparatus decides which routine is being scored -- it's half the key
        the lazily-created Routine is keyed on (see save-scores.ts). Keeping it in the
        filter row read as "another way to narrow the list", so it gets its own
        full-width row above them.
      */}
      <label
        htmlFor="scoring-apparatus"
        className="text-xs font-semibold uppercase text-gray-500"
      >
        Apparatus
      </label>
      <select
        id="scoring-apparatus"
        value={apparatus}
        onChange={(e) => onApparatusChange(e.target.value)}
        className="mb-2 mt-1 block w-full rounded border border-gray-300 p-1 text-sm"
      >
        {APPARATUS.map((a) => (
          <option key={a} value={a}>
            {a}
          </option>
        ))}
      </select>
      <div className="mb-2 flex gap-2">
        <select
          aria-label="Level filter"
          value={level}
          onChange={(e) => onLevelChange(e.target.value)}
          className="min-w-0 flex-1 rounded border border-gray-300 p-1 text-sm"
        >
          <option value="">All levels</option>
          {LEVELS.map((l) => (
            <option key={l} value={l}>
              {labelize(l)}
            </option>
          ))}
        </select>
        <select
          aria-label="Age group filter"
          value={ageGroup}
          onChange={(e) => onAgeGroupChange(e.target.value)}
          className="min-w-0 flex-1 rounded border border-gray-300 p-1 text-sm"
        >
          <option value="">All ages</option>
          {AGE_GROUPS.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </div>
      <ul className="divide-y divide-gray-100 overflow-hidden rounded border border-gray-200 bg-white">
        {visible.map((entry) => {
          const total = scoredTotals.get(entry.id);
          const selected = entry.id === selectedEntryId;
          return (
            <li key={entry.id}>
              <button
                onClick={() => onSelect(entry)}
                aria-current={selected ? "true" : undefined}
                className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm ${
                  selected ? "bg-blue-50 font-semibold" : "hover:bg-gray-50"
                }`}
              >
                <span>
                  {entry.bib_number} · {nameFor(entry)}
                </span>
                {total !== undefined && (
                  <span className="text-xs text-gray-500">✓ {total}</span>
                )}
              </button>
            </li>
          );
        })}
        {visible.length === 0 && (
          <li className="px-3 py-2 text-sm text-gray-500">No competitors match.</li>
        )}
      </ul>
    </div>
  );
}
