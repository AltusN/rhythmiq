import { useQuery } from "@tanstack/react-query";

/** Client-side search: lists are unpaginated, so filtering never hits the API. */
export function matchesSearch(text: string, query: string): boolean {
  const needle = query.trim().toLowerCase();
  return needle === "" || text.toLowerCase().includes(needle);
}

export function useResourceList<T>({
  queryKey,
  fetchRows,
  search = "",
  searchText,
}: {
  queryKey: unknown[];
  fetchRows: () => Promise<T[]>;
  search?: string;
  searchText?: (row: T) => string;
}): { rows: T[]; allRows: T[]; loaded: boolean; error: string | null } {
  const query = useQuery({ queryKey, queryFn: fetchRows });
  const all = query.data ?? [];
  const rows = searchText ? all.filter((r) => matchesSearch(searchText(r), search)) : all;
  return {
    rows,
    // Unfiltered, for callers that build filter options out of the data. Deriving
    // options from `rows` would let a filter narrow away its own options.
    allRows: all,
    loaded: query.data !== undefined,
    error: query.error ? query.error.message : null,
  };
}
