import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

/**
 * Confirm, delete, invalidate. A 409 (RESTRICT: dependents exist) surfaces as the
 * API's own `detail` — the frontend never predicts whether a delete will be allowed.
 *
 * `describe` returns the *entire* confirm-dialog message, not just a noun phrase.
 * Delete semantics differ by resource: District/Club/Group deletes are rejected
 * outright (409) when dependents exist, but a Gymnast delete cascades to their
 * meet entries and routines, and its confirm copy says so ("This also deletes
 * their meet entries and routines."). A single hard-coded "Delete X?" template
 * can't express both, so the caller supplies the full text.
 *
 * A delete error is only meaningful until the list it refers to is confirmed
 * fresh again — e.g. a later successful save on the same resource. The hook
 * doesn't guess when that happens: it exposes `clearError` and the caller
 * clears it explicitly from whichever action actually resolved it (typically
 * the save mutation's `onSuccess`, right alongside clearing that mutation's
 * own form error).
 */
export function useResourceDelete<T>({
  queryKey,
  describe,
  remove,
}: {
  queryKey: unknown[];
  describe: (row: T) => string;
  remove: (row: T) => Promise<void>;
}): { confirmDelete: (row: T) => void; error: string | null; clearError: () => void } {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: remove,
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey });
    },
    onError: (e: Error) => setError(e.message),
  });

  const confirmDelete = (row: T) => {
    if (!window.confirm(describe(row))) return;
    mutation.mutate(row);
  };

  return { confirmDelete, error, clearError: () => setError(null) };
}
