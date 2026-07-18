import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { ClubRead, GroupRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FkSelect } from "../components/FkSelect";

const groupSchema = z.object({
  name: z.string().trim().min(2, "At least 2 characters").max(100, "At most 100 characters"),
  club_id: z.string().min(1, "Pick a club"),
});
type GroupFormValues = z.infer<typeof groupSchema>;

export type GroupBody = { name?: string; club_id?: number };

export function GroupForm({
  initial,
  clubs,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  initial: GroupRead | null;
  clubs: ClubRead[];
  pending: boolean;
  error: string | null;
  onSubmit: (body: GroupBody) => void;
  onCancel: () => void;
}) {
  const { register, handleSubmit, formState } = useForm<GroupFormValues>({
    resolver: zodResolver(groupSchema),
    defaultValues: {
      name: initial?.name ?? "",
      club_id: initial?.club_id?.toString() ?? "",
    },
  });
  const { dirtyFields, errors } = formState;

  // club_id is fixed at creation and excluded from GroupUpdate on the
  // backend — reassigning a group to a different club is a separate domain
  // operation, not a plain field edit — so an edit never includes it in the
  // diff, even though the field stays visible (disabled) in the dialog.
  const buildBody = (v: GroupFormValues): GroupBody => {
    const full: GroupBody = { name: v.name, club_id: Number(v.club_id) };
    if (!initial) return full;
    const body: GroupBody = {};
    if (dirtyFields.name) body.name = full.name;
    return body;
  };

  const fieldClass = "mt-1 block w-full rounded border border-gray-300 p-1";

  return (
    <form onSubmit={handleSubmit((v) => onSubmit(buildBody(v)))} className="grid gap-3">
      <ErrorBanner message={error} />
      <label className="text-sm">
        Name
        <input {...register("name")} aria-label="Name" className={fieldClass} />
        {errors.name && <span className="text-xs text-red-700">{errors.name.message}</span>}
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
