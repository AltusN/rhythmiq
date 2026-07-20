import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { ClubRead, DistrictRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FkSelect } from "../components/FkSelect";

const clubSchema = z.object({
  name: z.string().trim().min(2, "At least 2 characters").max(100, "At most 100 characters"),
  abbreviation: z
    .string()
    .trim()
    .min(1, "Abbreviation is required")
    .max(10, "At most 10 characters"),
  district_id: z.string().min(1, "Pick a district"),
});
type ClubFormValues = z.infer<typeof clubSchema>;

export type ClubBody = { name?: string; abbreviation?: string; district_id?: number };

export function ClubForm({
  initial,
  districts,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  initial: ClubRead | null;
  districts: DistrictRead[];
  pending: boolean;
  error: string | null;
  onSubmit: (body: ClubBody) => void;
  onCancel: () => void;
}) {
  const { register, handleSubmit, formState } = useForm<ClubFormValues>({
    resolver: zodResolver(clubSchema),
    defaultValues: {
      name: initial?.name ?? "",
      abbreviation: initial?.abbreviation ?? "",
      district_id: initial?.district_id?.toString() ?? "",
    },
  });
  const { dirtyFields, errors } = formState;

  // district_id is fixed at creation and excluded from ClubUpdate on the
  // backend — moving a club between districts is a domain operation that
  // deserves its own endpoint — so an edit never includes it in the diff,
  // even though the field stays visible (disabled) in the dialog.
  const buildBody = (v: ClubFormValues): ClubBody => {
    const full: ClubBody = {
      name: v.name,
      abbreviation: v.abbreviation,
      district_id: Number(v.district_id),
    };
    if (!initial) return full;
    const body: ClubBody = {};
    if (dirtyFields.name) body.name = full.name;
    if (dirtyFields.abbreviation) body.abbreviation = full.abbreviation;
    return body;
  };

  const fieldClass = "mt-1 block w-full rounded border border-gray-300 p-1";

  return (
    <form onSubmit={handleSubmit((v) => onSubmit(buildBody(v)))} className="grid gap-3">
      <ErrorBanner message={error} />
      <label className="text-sm">
        Name
        <input {...register("name")} aria-label="Name" maxLength={100} className={fieldClass} />
        {errors.name && <span className="text-xs text-red-700">{errors.name.message}</span>}
      </label>
      <label className="text-sm">
        Abbreviation
        <input
          {...register("abbreviation")}
          aria-label="Abbreviation"
          className={fieldClass}
        />
        {errors.abbreviation && (
          <span className="text-xs text-red-700">{errors.abbreviation.message}</span>
        )}
      </label>
      <div>
        <FkSelect
          label="District"
          noneLabel="— pick —"
          options={districts.map((d) => ({ id: d.id, label: d.name }))}
          disabled={!!initial}
          title={initial ? "District cannot be changed after creation" : undefined}
          {...register("district_id")}
        />
        {errors.district_id && (
          <span className="text-xs text-red-700">{errors.district_id.message}</span>
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
