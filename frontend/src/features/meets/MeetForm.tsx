import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { DistrictRead, MeetRead } from "../../api/types";
import { ErrorBanner } from "../../components/ErrorBanner";
import { FkSelect } from "../admin/components/FkSelect";

/**
 * Mirrors backend/app/schemas/meet.py.
 *
 * `status` is deliberately ABSENT even though MeetUpdate accepts it: status changes
 * belong to the meet-shell controls, which enforce ALLOWED_STATUS_TRANSITIONS and the
 * confirmation gate on `completed`. Creating relies on the server's `draft` default.
 *
 * The medal cross-field rules are checked here because the form always holds BOTH
 * values in state even when only one is dirty. The PATCH still sends only dirty fields;
 * the router re-checks the incoming value against the stored counterpart in
 * _validate_partial_medal_cutoffs.
 */
const meetSchema = z
  .object({
    name: z.string().trim().min(2, "At least 2 characters").max(100, "At most 100 characters"),
    location: z.string().trim().min(2, "At least 2 characters").max(100, "At most 100 characters"),
    start_date: z.string().min(1, "Start date is required"),
    end_date: z.string().min(1, "End date is required"),
    district_id: z.string(),
    medal_gold_min: z.string().trim(),
    medal_silver_min: z.string().trim(),
  })
  .refine((v) => v.start_date === "" || v.end_date === "" || v.start_date <= v.end_date, {
    message: "End date must be on or after the start date",
    path: ["end_date"],
  })
  .refine((v) => (v.medal_gold_min === "") === (v.medal_silver_min === ""), {
    message: "Set both medal minimums or neither",
    path: ["medal_gold_min"],
  })
  .refine(
    (v) =>
      v.medal_gold_min === "" ||
      v.medal_silver_min === "" ||
      Number(v.medal_gold_min) > Number(v.medal_silver_min),
    { message: "Gold minimum must be above silver", path: ["medal_gold_min"] },
  );
type MeetFormValues = z.infer<typeof meetSchema>;

export type MeetBody = {
  name?: string;
  location?: string;
  start_date?: string;
  end_date?: string;
  district_id?: number | null;
  medal_gold_min?: number | null;
  medal_silver_min?: number | null;
};

const toId = (v: string): number | null => (v === "" ? null : Number(v));
const toNum = (v: string): number | null => (v.trim() === "" ? null : Number(v));

export function MeetForm({
  initial,
  districts,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  initial: MeetRead | null;
  districts: DistrictRead[];
  pending: boolean;
  error: string | null;
  onSubmit: (body: MeetBody) => void;
  onCancel: () => void;
}) {
  const { register, handleSubmit, formState } = useForm<MeetFormValues>({
    resolver: zodResolver(meetSchema),
    defaultValues: {
      name: initial?.name ?? "",
      location: initial?.location ?? "",
      start_date: initial?.start_date ?? "",
      end_date: initial?.end_date ?? "",
      district_id: initial?.district_id?.toString() ?? "",
      medal_gold_min: initial?.medal_gold_min?.toString() ?? "",
      medal_silver_min: initial?.medal_silver_min?.toString() ?? "",
    },
  });
  const { dirtyFields, errors } = formState;

  const buildBody = (v: MeetFormValues): MeetBody => {
    const full: MeetBody = {
      name: v.name,
      location: v.location,
      start_date: v.start_date,
      end_date: v.end_date,
      district_id: toId(v.district_id),
      medal_gold_min: toNum(v.medal_gold_min),
      medal_silver_min: toNum(v.medal_silver_min),
    };
    if (!initial) return full;
    const body: MeetBody = {};
    for (const key of Object.keys(full) as (keyof MeetBody)[]) {
      if (dirtyFields[key as keyof MeetFormValues]) {
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
        Name
        <input {...register("name")} aria-label="Name" className={fieldClass} />
        {errors.name && <span className="text-xs text-red-700">{errors.name.message}</span>}
      </label>
      <label className="text-sm">
        Location
        <input {...register("location")} aria-label="Location" className={fieldClass} />
        {errors.location && (
          <span className="text-xs text-red-700">{errors.location.message}</span>
        )}
      </label>
      <label className="text-sm">
        Start date
        <input type="date" {...register("start_date")} aria-label="Start date" className={fieldClass} />
        {errors.start_date && (
          <span className="text-xs text-red-700">{errors.start_date.message}</span>
        )}
      </label>
      <label className="text-sm">
        End date
        <input type="date" {...register("end_date")} aria-label="End date" className={fieldClass} />
        {errors.end_date && (
          <span className="text-xs text-red-700">{errors.end_date.message}</span>
        )}
      </label>
      {/* MeetUpdate DOES accept district_id, so this stays enabled on edit — unlike
          Club/Coach/Group, whose parent FK is not updatable. Do not add `disabled`. */}
      <FkSelect
        label="District"
        noneLabel="— none —"
        options={districts.map((d) => ({ id: d.id, label: d.name }))}
        {...register("district_id")}
      />
      <label className="text-sm">
        Gold minimum
        <input
          type="number"
          step="0.01"
          {...register("medal_gold_min")}
          aria-label="Gold minimum"
          className={fieldClass}
        />
        {errors.medal_gold_min && (
          <span className="text-xs text-red-700">{errors.medal_gold_min.message}</span>
        )}
      </label>
      <label className="text-sm">
        Silver minimum
        <input
          type="number"
          step="0.01"
          {...register("medal_silver_min")}
          aria-label="Silver minimum"
          className={fieldClass}
        />
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
