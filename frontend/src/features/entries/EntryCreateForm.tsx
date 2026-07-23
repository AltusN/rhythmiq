import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { apiDetail, client } from "../../api/client";
import type { AgeGroup, GroupRead, GymnastRead, Level } from "../../api/types";
import { ErrorBanner } from "../../components/ErrorBanner";
import { AGE_GROUPS, LEVELS, labelize } from "../../lib/domain";
import { CompetitorCombobox } from "./CompetitorCombobox";

const entrySchema = z.object({
  kind: z.enum(["gymnast", "group"]),
  competitorId: z.string().min(1, "Pick a competitor"),
  bib_number: z.string().trim().min(1, "Bib number is required"),
  level: z.string().min(1, "Pick a level"),
  age_group: z.string().min(1, "Pick an age group"),
  entry_fee_paid: z.boolean(),
});
type EntryFormValues = z.infer<typeof entrySchema>;

export function EntryCreateForm({
  meetId,
  gymnasts,
  groups,
  onCreated,
}: {
  meetId: number;
  gymnasts: GymnastRead[];
  groups: GroupRead[];
  onCreated: () => void;
}) {
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const { register, handleSubmit, watch, reset, setValue, formState } =
    useForm<EntryFormValues>({
      resolver: zodResolver(entrySchema),
      defaultValues: {
        kind: "gymnast",
        competitorId: "",
        bib_number: "",
        level: "",
        age_group: "",
        entry_fee_paid: false,
      },
    });
  const kind = watch("kind");

  const createMutation = useMutation({
    mutationFn: async (values: EntryFormValues) => {
      const { data, error } = await client.POST("/meet-entries/", {
        body: {
          meet_id: meetId,
          gymnast_id: values.kind === "gymnast" ? Number(values.competitorId) : null,
          group_id: values.kind === "group" ? Number(values.competitorId) : null,
          bib_number: values.bib_number,
          level: values.level as Level,
          age_group: values.age_group as AgeGroup,
          entry_fee_paid: values.entry_fee_paid,
        },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setServerError(null);
      reset();
      queryClient.invalidateQueries({ queryKey: ["entries", meetId] });
      onCreated();
    },
    onError: (e: Error) => setServerError(e.message),
  });

  return (
    <form
      onSubmit={handleSubmit((v) => createMutation.mutate(v))}
      className="mb-4 grid max-w-xl gap-3 rounded border border-gray-200 bg-white p-4"
    >
      <ErrorBanner message={serverError} />
      <fieldset className="flex gap-4">
        <label className="flex items-center gap-1 text-sm">
          <input
            type="radio"
            value="gymnast"
            {...register("kind", { onChange: () => setValue("competitorId", "") })}
          />{" "}
          Gymnast
        </label>
        <label className="flex items-center gap-1 text-sm">
          <input
            type="radio"
            value="group"
            {...register("kind", { onChange: () => setValue("competitorId", "") })}
          />{" "}
          Group
        </label>
      </fieldset>
      <label className="text-sm">
        Competitor
        <CompetitorCombobox
          ariaLabel="Competitor"
          value={watch("competitorId")}
          onChange={(id) => setValue("competitorId", id, { shouldValidate: true })}
          options={
            kind === "gymnast"
              ? gymnasts.map((g) => ({ id: g.id, label: `${g.first_name} ${g.last_name}` }))
              : groups.map((g) => ({ id: g.id, label: g.name }))
          }
        />
        {formState.errors.competitorId && (
          <span className="text-xs text-red-700">{formState.errors.competitorId.message}</span>
        )}
      </label>
      <label className="text-sm">
        Bib number
        <input
          {...register("bib_number")}
          aria-label="Bib number"
          className="mt-1 block w-full rounded border border-gray-300 p-1"
        />
        {formState.errors.bib_number && (
          <span className="text-xs text-red-700">{formState.errors.bib_number.message}</span>
        )}
      </label>
      <div className="flex gap-3">
        <label className="flex-1 text-sm">
          Level
          <select {...register("level")} aria-label="Level" className="mt-1 block w-full rounded border border-gray-300 p-1">
            <option value="">— pick —</option>
            {LEVELS.map((l) => (
              <option key={l} value={l}>
                {labelize(l)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex-1 text-sm">
          Age group
          <select {...register("age_group")} aria-label="Age group" className="mt-1 block w-full rounded border border-gray-300 p-1">
            <option value="">— pick —</option>
            {AGE_GROUPS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" {...register("entry_fee_paid")} /> Entry fee paid
      </label>
      <button
        type="submit"
        disabled={createMutation.isPending}
        className="justify-self-start rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
      >
        Create entry
      </button>
    </form>
  );
}
