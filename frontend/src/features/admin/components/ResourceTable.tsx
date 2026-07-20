import type { ReactNode } from "react";

export type Column<T> = { header: string; render: (row: T) => ReactNode };

export function ResourceTable<T extends { id: number }>({
  rows,
  columns,
  rowLabel,
  onEdit,
  onDelete,
  emptyMessage,
}: {
  rows: T[];
  columns: Column<T>[];
  rowLabel: (row: T) => string;
  onEdit: (row: T) => void;
  onDelete: (row: T) => void;
  emptyMessage: string;
}) {
  if (rows.length === 0) return <p className="text-sm text-gray-500">{emptyMessage}</p>;

  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="border-b border-gray-300 text-left">
          {columns.map((c) => (
            <th key={c.header} className="px-2 py-1">
              {c.header}
            </th>
          ))}
          <th className="px-2 py-1" />
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id} className="border-b border-gray-200">
            {columns.map((c) => (
              <td key={c.header} className="px-2 py-1">
                {c.render(row)}
              </td>
            ))}
            <td className="whitespace-nowrap px-2 py-1 text-right">
              <button
                type="button"
                aria-label={`Edit ${rowLabel(row)}`}
                onClick={() => onEdit(row)}
                className="rounded border border-gray-300 px-2 py-0.5 text-xs"
              >
                Edit
              </button>
              <button
                type="button"
                aria-label={`Delete ${rowLabel(row)}`}
                onClick={() => onDelete(row)}
                className="ml-2 rounded border border-gray-300 px-2 py-0.5 text-xs text-red-700"
              >
                Delete
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
