import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { Apparatus, GroupRead, GymnastRead, Level } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { APPARATUS, LEVELS, labelize } from "../../../lib/domain";

/**
 * Mirrors backend/app/schemas/routine_profile.py.
 *
 * Owner selection copies src/features/entries/EntryCreateForm.tsx: a `kind` radio plus
 * ONE `competitorId` field, mapped to gymnast_id/group_id at submit. With a single field
 * there is no stale second value to leak, so the backend's exactly-one-of rule
 * (validate_gymnast_or_group) is structurally unreachable rather than re-validated here.
 */
const profileSchema = z.object({
  kind: z.enum(["gymnast", "group"]),
  competitorId: z.string().min(1, "Pick a gymnast or group"),
  apparatus: z.string().min(1, "Pick an apparatus"),
  level: z.string().min(1, "Pick a level"),
  music_url: z.string().trim(),
  choreography_notes: z.string().trim().max(500, "At most 500 characters"),
});
type ProfileFormValues = z.infer<typeof profileSchema>;

export type RoutineProfileCreateBody = {
  gymnast_id: number | null;
  group_id: number | null;
  apparatus: Apparatus;
  level: Level;
  music_url: string | null;
  choreography_notes: string | null;
};

const toText = (v: string): string | null => (v.trim() === "" ? null : v.trim());

export function RoutineProfileCreateForm({
  gymnasts,
  groups,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  gymnasts: GymnastRead[];
  groups: GroupRead[];
  pending: boolean;
  error: string | null;
  onSubmit: (body: RoutineProfileCreateBody) => void;
  onCancel: () => void;
}) {
  const { register, handleSubmit, watch, formState } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      kind: "gymnast",
      competitorId: "",
      apparatus: "",
      level: "",
      music_url: "",
      choreography_notes: "",
    },
  });
  const { errors } = formState;
  const kind = watch("kind");

  const buildBody = (v: ProfileFormValues): RoutineProfileCreateBody => ({
    gymnast_id: v.kind === "gymnast" ? Number(v.competitorId) : null,
    group_id: v.kind === "group" ? Number(v.competitorId) : null,
    apparatus: v.apparatus as Apparatus,
    level: v.level as Level,
    music_url: toText(v.music_url),
    choreography_notes: toText(v.choreography_notes),
  });

  const fieldClass = "mt-1 block w-full rounded border border-gray-300 p-1";

  return (
    <form onSubmit={handleSubmit((v) => onSubmit(buildBody(v)))} className="grid gap-3">
      <ErrorBanner message={error} />
      <fieldset className="text-sm">
        <legend>Owner</legend>
        {/*
          The visible text after each radio doubles as its implicit accessible name
          (HTML label-wrapping), independently of any aria-label on the input itself.
          "Gymnast" alone here would collide with the competitor <select>'s
          aria-label="Gymnast" below — getByLabelText("Gymnast") would then match two
          elements. "Gymnast owner" keeps that name distinct.
        */}
        <label className="mr-4">
          <input type="radio" value="gymnast" {...register("kind")} /> Gymnast owner
        </label>
        <label>
          <input type="radio" value="group" {...register("kind")} /> Group
        </label>
      </fieldset>
      <label className="text-sm">
        {kind === "gymnast" ? "Gymnast" : "Group name"}
        <select
          {...register("competitorId")}
          aria-label={kind === "gymnast" ? "Gymnast" : "Group name"}
          className={fieldClass}
        >
          <option value="">— select —</option>
          {kind === "gymnast"
            ? gymnasts.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.first_name} {g.last_name}
                </option>
              ))
            : groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
        </select>
        {errors.competitorId && (
          <span className="text-xs text-red-700">{errors.competitorId.message}</span>
        )}
      </label>
      <label className="text-sm">
        Apparatus
        <select {...register("apparatus")} aria-label="Apparatus" className={fieldClass}>
          <option value="">— select —</option>
          {APPARATUS.map((a) => (
            <option key={a} value={a}>
              {labelize(a)}
            </option>
          ))}
        </select>
        {errors.apparatus && (
          <span className="text-xs text-red-700">{errors.apparatus.message}</span>
        )}
      </label>
      <label className="text-sm">
        Level
        <select {...register("level")} aria-label="Level" className={fieldClass}>
          <option value="">— select —</option>
          {LEVELS.map((l) => (
            <option key={l} value={l}>
              {labelize(l)}
            </option>
          ))}
        </select>
        {errors.level && <span className="text-xs text-red-700">{errors.level.message}</span>}
      </label>
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
