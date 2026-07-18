import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { DistrictRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";

const districtSchema = z.object({
  name: z.string().trim().min(2, "At least 2 characters").max(100, "At most 100 characters"),
  abbreviation: z
    .string()
    .trim()
    .min(1, "Abbreviation is required")
    .max(10, "At most 10 characters"),
});
type DistrictFormValues = z.infer<typeof districtSchema>;

export type DistrictBody = Partial<DistrictFormValues>;

export function DistrictForm({
  initial,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  initial: DistrictRead | null;
  pending: boolean;
  error: string | null;
  onSubmit: (body: DistrictBody) => void;
  onCancel: () => void;
}) {
  const { register, handleSubmit, formState } = useForm<DistrictFormValues>({
    resolver: zodResolver(districtSchema),
    defaultValues: {
      name: initial?.name ?? "",
      abbreviation: initial?.abbreviation ?? "",
    },
  });
  const { dirtyFields } = formState;

  // PATCH sends only what changed; POST sends everything.
  const buildBody = (values: DistrictFormValues): DistrictBody => {
    if (!initial) return values;
    const body: DistrictBody = {};
    if (dirtyFields.name) body.name = values.name;
    if (dirtyFields.abbreviation) body.abbreviation = values.abbreviation;
    return body;
  };

  return (
    <form onSubmit={handleSubmit((v) => onSubmit(buildBody(v)))} className="grid gap-3">
      <ErrorBanner message={error} />
      <label className="text-sm">
        Name
        <input
          {...register("name")}
          aria-label="Name"
          className="mt-1 block w-full rounded border border-gray-300 p-1"
        />
        {formState.errors.name && (
          <span className="text-xs text-red-700">{formState.errors.name.message}</span>
        )}
      </label>
      <label className="text-sm">
        Abbreviation
        <input
          {...register("abbreviation")}
          aria-label="Abbreviation"
          className="mt-1 block w-full rounded border border-gray-300 p-1"
        />
        {formState.errors.abbreviation && (
          <span className="text-xs text-red-700">
            {formState.errors.abbreviation.message}
          </span>
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
