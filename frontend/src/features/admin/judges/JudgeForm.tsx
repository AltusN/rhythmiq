import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { JudgeRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";

/**
 * Mirrors backend/app/schemas/judge.py. country_code is validated for shape only —
 * JudgeCreate.validate_country_code uppercases server-side, and the form shows the
 * saved value after the round trip (same rule as District.abbreviation).
 */
const judgeSchema = z.object({
  first_name: z.string().trim().min(2, "At least 2 characters").max(100, "At most 100 characters"),
  last_name: z.string().trim().min(2, "At least 2 characters").max(100, "At most 100 characters"),
  country_code: z
    .string()
    .trim()
    .refine((v) => v === "" || /^[A-Za-z]{3}$/.test(v), "Must be 3 letters"),
  brevet: z.string().trim(),
});
type JudgeFormValues = z.infer<typeof judgeSchema>;

export type JudgeBody = {
  first_name?: string;
  last_name?: string;
  country_code?: string | null;
  brevet?: string | null;
};

const toText = (v: string): string | null => (v.trim() === "" ? null : v.trim());

export function JudgeForm({
  initial,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  initial: JudgeRead | null;
  pending: boolean;
  error: string | null;
  onSubmit: (body: JudgeBody) => void;
  onCancel: () => void;
}) {
  const { register, handleSubmit, formState } = useForm<JudgeFormValues>({
    resolver: zodResolver(judgeSchema),
    defaultValues: {
      first_name: initial?.first_name ?? "",
      last_name: initial?.last_name ?? "",
      country_code: initial?.country_code ?? "",
      brevet: initial?.brevet ?? "",
    },
  });
  const { dirtyFields, errors } = formState;

  const buildBody = (v: JudgeFormValues): JudgeBody => {
    const full: JudgeBody = {
      first_name: v.first_name,
      last_name: v.last_name,
      country_code: toText(v.country_code),
      brevet: toText(v.brevet),
    };
    if (!initial) return full;
    const body: JudgeBody = {};
    for (const key of Object.keys(full) as (keyof JudgeBody)[]) {
      if (dirtyFields[key as keyof JudgeFormValues]) {
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
      <label className="text-sm">
        Country code
        <input {...register("country_code")} aria-label="Country code" className={fieldClass} />
        {errors.country_code && (
          <span className="text-xs text-red-700">{errors.country_code.message}</span>
        )}
      </label>
      <label className="text-sm">
        Brevet
        <input {...register("brevet")} aria-label="Brevet" className={fieldClass} />
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
