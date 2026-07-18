import type { SelectHTMLAttributes } from "react";

/**
 * Spreads the rest props onto the native <select>, so it works both with RHF's
 * `{...register("club_id")}` and with a plain controlled `value`/`onChange` filter.
 */
export function FkSelect({
  label,
  options,
  noneLabel,
  ...selectProps
}: {
  label: string;
  options: { id: number; label: string }[];
  noneLabel?: string;
} & SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <label className="text-sm">
      {label}
      <select
        aria-label={label}
        {...selectProps}
        className="mt-1 block w-full rounded border border-gray-300 p-1"
      >
        {noneLabel !== undefined && <option value="">{noneLabel}</option>}
        {options.map((o) => (
          <option key={o.id} value={o.id}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
