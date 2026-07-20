import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { ClubRead, CoachRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FkSelect } from "../components/FkSelect";

const coachSchema = z.object({
  first_name: z.string().trim().min(2, "At least 2 characters").max(100, "At most 100 characters"),
  last_name: z.string().trim().min(2, "At least 2 characters").max(100, "At most 100 characters"),
  club_id: z.string().min(1, "Pick a club"),
  is_head_coach: z.boolean(),
});
type CoachFormValues = z.infer<typeof coachSchema>;

export type CoachBody = {
  first_name?: string;
  last_name?: string;
  club_id?: number;
  is_head_coach?: boolean;
};

export function CoachForm({
  initial,
  clubs,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  initial: CoachRead | null;
  clubs: ClubRead[];
  pending: boolean;
  error: string | null;
  onSubmit: (body: CoachBody) => void;
  onCancel: () => void;
}) {
  const { register, handleSubmit, formState } = useForm<CoachFormValues>({
    resolver: zodResolver(coachSchema),
    defaultValues: {
      first_name: initial?.first_name ?? "",
      last_name: initial?.last_name ?? "",
      club_id: initial?.club_id?.toString() ?? "",
      is_head_coach: initial?.is_head_coach ?? false,
    },
  });
  const { dirtyFields, errors } = formState;

  // club_id is fixed at creation and excluded from CoachUpdate on the
  // backend — reassigning a coach to a different club is a separate domain
  // operation, not a plain field edit — so an edit never includes it in the
  // diff, even though the field stays visible (disabled) in the dialog.
  const buildBody = (v: CoachFormValues): CoachBody => {
    const full: CoachBody = {
      first_name: v.first_name,
      last_name: v.last_name,
      club_id: Number(v.club_id),
      is_head_coach: v.is_head_coach,
    };
    if (!initial) return full;
    const body: CoachBody = {};
    if (dirtyFields.first_name) body.first_name = full.first_name;
    if (dirtyFields.last_name) body.last_name = full.last_name;
    if (dirtyFields.is_head_coach) body.is_head_coach = full.is_head_coach;
    return body;
  };

  const fieldClass = "mt-1 block w-full rounded border border-gray-300 p-1";

  return (
    <form onSubmit={handleSubmit((v) => onSubmit(buildBody(v)))} className="grid gap-3">
      <ErrorBanner message={error} />
      <label className="text-sm">
        First name
        <input {...register("first_name")} aria-label="First name" maxLength={100} className={fieldClass} />
        {errors.first_name && (
          <span className="text-xs text-red-700">{errors.first_name.message}</span>
        )}
      </label>
      <label className="text-sm">
        Last name
        <input {...register("last_name")} aria-label="Last name" maxLength={100} className={fieldClass} />
        {errors.last_name && (
          <span className="text-xs text-red-700">{errors.last_name.message}</span>
        )}
      </label>
      <div>
        <FkSelect
          label="Club"
          noneLabel="— pick —"
          options={clubs.map((c) => ({ id: c.id, label: c.name }))}
          disabled={!!initial}
          title={initial ? "Club cannot be changed after creation" : undefined}
          {...register("club_id")}
        />
        {errors.club_id && (
          <span className="text-xs text-red-700">{errors.club_id.message}</span>
        )}
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" {...register("is_head_coach")} aria-label="Head coach" />
        Head coach
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
