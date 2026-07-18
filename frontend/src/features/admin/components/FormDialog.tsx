import { useEffect, type ReactNode } from "react";

/**
 * Modal shell only. The error banner and the Cancel/Save buttons live inside each
 * resource's own form, because they are wired to that form's RHF instance.
 *
 * `onClose` fires on Escape and on a backdrop click (clicking the overlay itself,
 * not the panel). Every caller wires it to the exact same handler as the form's
 * own `onCancel`, so all three dismissal paths behave identically — including
 * whatever else that handler does (e.g. clearing an error). Deliberately no Tab
 * focus trap: scoped out as fiddly to get right and to test in jsdom.
 */
export function FormDialog({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 flex items-center justify-center bg-black/30"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="w-96 rounded border border-gray-200 bg-white p-4 shadow-lg"
      >
        <h2 className="mb-2 text-lg font-semibold">{title}</h2>
        {children}
      </div>
    </div>
  );
}
