import { useEffect, useRef, useState } from "react";

export interface CompetitorComboboxOption {
  id: number;
  label: string;
}

/** Case-insensitive: any whitespace-separated part of `label` starts with `query`. */
export function matchesNamePartPrefix(label: string, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (q === "") return true;
  return label
    .toLowerCase()
    .split(/\s+/)
    .some((part) => part.startsWith(q));
}

export function CompetitorCombobox({
  options,
  value,
  onChange,
  ariaLabel = "Competitor",
}: {
  options: CompetitorComboboxOption[];
  value: string;
  onChange: (id: string) => void;
  ariaLabel?: string;
}) {
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);

  // Keep the input text in sync with the externally-controlled value: fires only when a
  // selection is committed or the option list swaps (gymnast<->group), never on keystrokes
  // (those change `text`, not `value`).
  useEffect(() => {
    const selected = options.find((o) => String(o.id) === value);
    setText(selected ? selected.label : "");
  }, [value, options]);

  const selected = options.find((o) => String(o.id) === value);
  const q = text.trim();
  const showAll = q === "" || (selected != null && q === selected.label);
  const filtered = showAll ? options : options.filter((o) => matchesNamePartPrefix(o.label, q));

  function select(option: CompetitorComboboxOption) {
    onChange(String(option.id));
    setText(option.label);
    setOpen(false);
  }

  return (
    <div ref={rootRef} className="relative">
      <input
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-label={ariaLabel}
        value={text}
        autoComplete="off"
        className="mt-1 block w-full rounded border border-gray-300 p-1"
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
          setHighlight(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setOpen(true);
            setHighlight((h) => Math.min(h + 1, filtered.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setHighlight((h) => Math.max(h - 1, 0));
          } else if (e.key === "Enter") {
            if (open && filtered[highlight]) {
              e.preventDefault();
              select(filtered[highlight]);
            }
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
      />
      {open && filtered.length > 0 && (
        <ul
          role="listbox"
          className="absolute z-10 mt-1 max-h-48 w-full overflow-auto rounded border border-gray-300 bg-white shadow"
        >
          {filtered.map((o, i) => (
            <li key={o.id} role="option" aria-selected={i === highlight}>
              <button
                type="button"
                // preventDefault keeps the input from blurring (which would close the
                // list) before the click registers and selects the option.
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => select(o)}
                onMouseEnter={() => setHighlight(i)}
                className={`block w-full px-2 py-1 text-left text-sm ${
                  i === highlight ? "bg-blue-100" : "bg-white"
                }`}
              >
                {o.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
