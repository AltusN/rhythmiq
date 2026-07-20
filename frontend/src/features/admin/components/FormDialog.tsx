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
 *
 * The panel is height-capped for a reason: the overlay is `fixed inset-0`, so it is
 * exactly viewport-sized and does NOT scroll with the page. Without `max-h`, a form
 * taller than the viewport gets centred and overflows off BOTH ends, leaving its
 * title and its Save/Cancel buttons unreachable — the form cannot be submitted at
 * all. Observed on the gymnast edit form at ~700px viewport height. jsdom has no
 * layout engine, so no test can reproduce that; the FormDialog test asserts the
 * classes are present purely so they cannot be stripped silently during a restyle.
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
      className="fixed inset-0 flex items-center justify-center overflow-y-auto p-4 bg-black/30"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="max-h-[90vh] w-96 overflow-y-auto rounded border border-gray-200 bg-white p-4 shadow-lg"
      >
        <h2 className="mb-2 text-lg font-semibold">{title}</h2>
        {children}
      </div>
    </div>
  );
}
