import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { ClubRead, GroupRead, GymnastRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FkSelect } from "../components/FkSelect";

/** Select and date inputs hand back strings; "" means "not set" and becomes null. */
const gymnastSchema = z.object({
  first_name: z
    .string()
    .trim()
    .min(2, "At least 2 characters")
    .max(100, "At most 100 characters"),
  last_name: z
    .string()
    .trim()
    .min(2, "At least 2 characters")
    .max(100, "At most 100 characters"),
  club_id: z.string(),
  group_id: z.string(),
  date_of_birth: z.string(),
  country_code: z.string().trim().max(3, "At most 3 characters"),
});
type GymnastFormValues = z.infer<typeof gymnastSchema>;

export type GymnastBody = {
  first_name?: string;
  last_name?: string;
  club_id?: number | null;
  group_id?: number | null;
  date_of_birth?: string | null;
  country_code?: string | null;
};

const toId = (v: string): number | null => (v === "" ? null : Number(v));
const toText = (v: string): string | null => (v.trim() === "" ? null : v.trim());

export function GymnastForm({
  initial,
  clubs,
  groups,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  initial: GymnastRead | null;
  clubs: ClubRead[];
  groups: GroupRead[];
  pending: boolean;
  error: string | null;
  onSubmit: (body: GymnastBody) => void;
  onCancel: () => void;
}) {
  const { register, handleSubmit, formState } = useForm<GymnastFormValues>({
    resolver: zodResolver(gymnastSchema),
    defaultValues: {
      first_name: initial?.first_name ?? "",
      last_name: initial?.last_name ?? "",
      club_id: initial?.club_id?.toString() ?? "",
      group_id: initial?.group_id?.toString() ?? "",
      date_of_birth: initial?.date_of_birth ?? "",
      country_code: initial?.country_code ?? "",
    },
  });
  const { dirtyFields, errors } = formState;

  const buildBody = (v: GymnastFormValues): GymnastBody => {
    const full: GymnastBody = {
      first_name: v.first_name,
      last_name: v.last_name,
      club_id: toId(v.club_id),
      group_id: toId(v.group_id),
      date_of_birth: toText(v.date_of_birth),
      country_code: toText(v.country_code),
    };
    if (!initial) return full;
    // PATCH only what the user touched: an untouched nullable FK must not be
    // sent as explicit null, or the server would unassign it.
    const body: GymnastBody = {};
    for (const key of Object.keys(full) as (keyof GymnastBody)[]) {
      if (dirtyFields[key as keyof GymnastFormValues]) {
        Object.assign(body, { [key]: full[key] });
      }
    }
    return body;
  };

  const fieldClass = "mt-1 block w-full rounded border border-gray-300 p-1";

  return (
    <form onSubmit={handleSubmit((v) => onSubmit(buildBody(v)))} className="grid gap-3">
      <ErrorBanner message={error} />
      <label className="text-sm">
        First name
        <input {...register("first_name")} aria-label="First name" className={fieldClass} />
        {errors.first_name && (
          <span className="text-xs text-red-700">{errors.first_name.message}</span>
        )}
      </label>
      <label className="text-sm">
        Last name
        <input {...register("last_name")} aria-label="Last name" className={fieldClass} />
        {errors.last_name && (
          <span className="text-xs text-red-700">{errors.last_name.message}</span>
        )}
      </label>
      <FkSelect
        label="Club"
        noneLabel="— none —"
        options={clubs.map((c) => ({ id: c.id, label: c.name }))}
        {...register("club_id")}
      />
      <FkSelect
        label="Group"
        noneLabel="— none —"
        options={groups.map((g) => ({ id: g.id, label: g.name }))}
        {...register("group_id")}
      />
      <label className="text-sm">
        Date of birth
        <input
          type="date"
          {...register("date_of_birth")}
          aria-label="Date of birth"
          className={fieldClass}
        />
      </label>
      <label className="text-sm">
        Country code
        <input
          {...register("country_code")}
          aria-label="Country code"
          className={fieldClass}
        />
        {errors.country_code && (
          <span className="text-xs text-red-700">{errors.country_code.message}</span>
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
