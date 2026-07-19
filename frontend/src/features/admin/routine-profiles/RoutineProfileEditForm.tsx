import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { RoutineProfileRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { labelize } from "../../../lib/domain";

/**
 * RoutineProfileUpdate accepts ONLY music_url and choreography_notes — owner, apparatus
 * and level form the model's UniqueConstraint and are create-only. They render as a
 * read-only context line rather than disabled controls, because they are never editable
 * here (delete + recreate), not merely disabled for now. This is a deliberate departure
 * from the Phase 2 `disabled={!!initial}` convention used elsewhere in the admin
 * console — do not "fix" it back.
 */
const editSchema = z.object({
  music_url: z.string().trim(),
  choreography_notes: z.string().trim().max(500, "At most 500 characters"),
});
type EditFormValues = z.infer<typeof editSchema>;

export type RoutineProfileEditBody = {
  music_url?: string | null;
  choreography_notes?: string | null;
};

const toText = (v: string): string | null => (v.trim() === "" ? null : v.trim());

export function RoutineProfileEditForm({
  initial,
  ownerName,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  initial: RoutineProfileRead;
  ownerName: string;
  pending: boolean;
  error: string | null;
  onSubmit: (body: RoutineProfileEditBody) => void;
  onCancel: () => void;
}) {
  const { register, handleSubmit, formState } = useForm<EditFormValues>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      music_url: initial.music_url ?? "",
      choreography_notes: initial.choreography_notes ?? "",
    },
  });
  const { dirtyFields, errors } = formState;

  const buildBody = (v: EditFormValues): RoutineProfileEditBody => {
    const body: RoutineProfileEditBody = {};
    if (dirtyFields.music_url) body.music_url = toText(v.music_url);
    if (dirtyFields.choreography_notes) {
      body.choreography_notes = toText(v.choreography_notes);
    }
    return body;
  };

  const fieldClass = "mt-1 block w-full rounded border border-gray-300 p-1";

  return (
    <form onSubmit={handleSubmit((v) => onSubmit(buildBody(v)))} className="grid gap-3">
      <ErrorBanner message={error} />
      <div className="rounded bg-gray-50 p-2 text-sm">
        <div className="font-semibold">
          {ownerName} · {labelize(initial.apparatus)} · {labelize(initial.level)}
        </div>
        <div className="text-xs text-gray-500">
          To change these, delete the profile and create a new one.
        </div>
      </div>
      <label className="text-sm">
        Music URL
        <input {...register("music_url")} aria-label="Music URL" className={fieldClass} />
      </label>
      <label className="text-sm">
        Choreography notes
        <textarea
          {...register("choreography_notes")}
          aria-label="Choreography notes"
          className={fieldClass}
        />
        {errors.choreography_notes && (
          <span className="text-xs text-red-700">{errors.choreography_notes.message}</span>
        )}
      </label>
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded border border-gray-300 px-3 py-1 text-sm"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={pending}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          Save
        </button>
      </div>
    </form>
  );
}
