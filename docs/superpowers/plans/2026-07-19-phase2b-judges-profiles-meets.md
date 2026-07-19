# Phase 2b Implementation Plan — Judges, Routine Profiles, Meet CRUD

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close out the v1 frontend scope by adding admin screens for judges and routine profiles, moving meet create/edit onto the meet list and meet header, and fixing the shipped gymnast form's group select.

**Architecture:** Judges and routine profiles are new consumers of the existing admin shared layer (`ResourceTable`, `FormDialog`, `FkSelect`, `useResourceList`, `useResourceDelete`) under `src/features/admin/`. Meets deliberately do **not** use that layer — they stay on `/` and the meet shell because they have a status lifecycle and a navigating row. Frontend-only; zero backend files change.

**Tech Stack:** React 19, TypeScript (strict), Vite, TanStack Query v5, React Hook Form + Zod, Tailwind, openapi-fetch. Tests: Vitest + Testing Library + MSW.

**Spec:** `docs/superpowers/specs/2026-07-19-phase2b-design.md`

## Global Constraints

- **Zod mirrors the real backend schema, never this plan's prose.** Open the referenced
  `backend/app/schemas/*.py` and copy the actual `Field(...)` bounds. Where this plan's
  example code and the backend disagree, **the backend wins**.
- **Do not modify `src/features/admin/components/` or `src/features/admin/hooks/`.**
  Consuming the shared layer unchanged is a deliberate, falsifiable prediction of this
  plan. If a task genuinely cannot proceed without changing it, STOP and report that —
  do not silently edit it.
- **No backend files change.** Not `backend/**`, not `frontend/src/api/schema.d.ts`
  (no schema regeneration is needed; every endpoint already exists in the committed
  schema).
- **PATCH sends only dirty fields.** Every edit form builds its body from
  `formState.dirtyFields`, following `GymnastForm.buildBody`. An untouched nullable FK
  must never be sent as explicit `null`.
- **Assert request bodies with `toEqual`, never `toMatchObject`** — an unexpected extra
  field must fail the test.
- **Commit messages start with `feat:` / `fix:` / `chore:` / `docs:` / `test:`.**
- **Run from `frontend/`.** `npm test -- --run` for the suite, `npm run build` for
  typecheck + build.
- Existing test count before this plan: **153 across 24 files**. Every task must leave
  the suite green.

---

### Task 1: Judges admin screen

**Files:**
- Modify: `frontend/src/api/types.ts` (add `RoutineProfileRead` export — used by Task 3, added here so Task 1 and 3 don't both touch the file)
- Create: `frontend/src/features/admin/judges/JudgeForm.tsx`
- Create: `frontend/src/features/admin/judges/JudgesPage.tsx`
- Modify: `frontend/src/App.tsx` (add `/admin/judges` route)
- Modify: `frontend/src/features/admin/AdminShell.tsx:4-10` (add Judges to `RESOURCES`)
- Test: `frontend/test/features/admin/judges/JudgesPage.test.tsx`

**Interfaces:**
- Consumes: `ResourceTable`, `FormDialog`, `useResourceList`, `useResourceDelete` (unchanged); `makeJudge` from `test/fixtures.ts` (already exists); `JudgeRead` from `src/api/types.ts` (already exported).
- Produces: `JudgeForm`, `type JudgeBody` from `judges/JudgeForm.tsx`. `RoutineProfileRead` type export consumed by Task 3.

**Backend facts (verified — do not re-derive):**
- `backend/app/schemas/judge.py`: `first_name`/`last_name` are `Field(min_length=2, max_length=100)`. `country_code` is optional, validated as exactly 3 alpha chars, and **uppercased server-side** — the client must NOT uppercase. `brevet` is optional free text (`String`, nullable, not an enum).
- `JudgeUpdate` carries **every** field, so nothing is disabled on edit. This is the first admin resource with no immutable-field concern.
- `JudgeScore.judge_id` and `PenaltyRecord.judge_id` are both `ondelete="RESTRICT"`. A judge delete is **rejected** (409) once they have scores or penalties — nothing cascades. Confirm copy must not warn about destroying scores.
- `uq_judge_identity` is a `UniqueConstraint` on (`first_name`, `last_name`, `country_code`) → duplicates 409. Surfaced via `apiDetail`, not reproduced client-side.
- `list_judges` accepts a `country_code` query param.

- [ ] **Step 1: Add the `RoutineProfileRead` type export**

In `frontend/src/api/types.ts`, add alongside the existing exports:

```ts
export type RoutineProfileRead = components["schemas"]["RoutineProfileRead"];
```

- [ ] **Step 2: Write the failing tests**

Create `frontend/test/features/admin/judges/JudgesPage.test.tsx`:

```tsx
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeJudge } from "../../../fixtures";
import { api, server } from "../../../msw/server";
import { renderApp } from "../../../utils";

test("lists judges", async () => {
  server.use(
    http.get(api("/judges/"), () =>
      HttpResponse.json([
        makeJudge({ id: 1, first_name: "Naledi", last_name: "Dlamini", country_code: "RSA", brevet: "Cat I" }),
        makeJudge({ id: 2, first_name: "Elena", last_name: "Petrova", country_code: "BUL", brevet: null }),
      ]),
    ),
  );
  renderApp("/admin/judges");
  expect(await screen.findByText("Naledi")).toBeInTheDocument();
  expect(screen.getByText("Cat I")).toBeInTheDocument();
  expect(screen.getByText("BUL")).toBeInTheDocument();
});

test("shows an empty message when there are no judges", async () => {
  server.use(http.get(api("/judges/"), () => HttpResponse.json([])));
  renderApp("/admin/judges");
  expect(await screen.findByText("No judges yet.")).toBeInTheDocument();
});

test("surfaces a list error", async () => {
  server.use(
    http.get(api("/judges/"), () =>
      HttpResponse.json({ detail: "Database unavailable" }, { status: 500 }),
    ),
  );
  renderApp("/admin/judges");
  expect(await screen.findByRole("alert")).toHaveTextContent("Database unavailable");
});

test("creates a judge, sending nulls for blank optional fields", async () => {
  server.use(http.get(api("/judges/"), () => HttpResponse.json([])));
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/judges/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeJudge(), { status: 201 });
    }),
  );
  renderApp("/admin/judges");
  await userEvent.click(await screen.findByRole("button", { name: "New judge" }));
  await userEvent.type(screen.getByLabelText("First name"), "Ana");
  await userEvent.type(screen.getByLabelText("Last name"), "Meyer");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toEqual({
      first_name: "Ana",
      last_name: "Meyer",
      country_code: null,
      brevet: null,
    }),
  );
});

test("does not uppercase the country code client-side", async () => {
  server.use(http.get(api("/judges/"), () => HttpResponse.json([])));
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/judges/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeJudge(), { status: 201 });
    }),
  );
  renderApp("/admin/judges");
  await userEvent.click(await screen.findByRole("button", { name: "New judge" }));
  await userEvent.type(screen.getByLabelText("First name"), "Ana");
  await userEvent.type(screen.getByLabelText("Last name"), "Meyer");
  await userEvent.type(screen.getByLabelText("Country code"), "rsa");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(posted).not.toBeNull());
  expect(posted!.country_code).toBe("rsa");
});

test("blocks a 2-letter country code before sending", async () => {
  server.use(http.get(api("/judges/"), () => HttpResponse.json([])));
  let called = false;
  server.use(
    http.post(api("/judges/"), () => {
      called = true;
      return HttpResponse.json(makeJudge(), { status: 201 });
    }),
  );
  renderApp("/admin/judges");
  await userEvent.click(await screen.findByRole("button", { name: "New judge" }));
  await userEvent.type(screen.getByLabelText("First name"), "Ana");
  await userEvent.type(screen.getByLabelText("Last name"), "Meyer");
  await userEvent.type(screen.getByLabelText("Country code"), "RS");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Must be 3 letters")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("PATCHes only the changed field", async () => {
  server.use(
    http.get(api("/judges/"), () =>
      HttpResponse.json([makeJudge({ id: 7, first_name: "Naledi", last_name: "Dlamini" })]),
    ),
  );
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/judges/7"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeJudge({ id: 7 }));
    }),
  );
  renderApp("/admin/judges");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Naledi Dlamini" }));
  const brevet = screen.getByLabelText("Brevet");
  await userEvent.clear(brevet);
  await userEvent.type(brevet, "Cat II");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ brevet: "Cat II" }));
});

test("keeps the dialog open and shows the detail on a duplicate-identity 409", async () => {
  server.use(http.get(api("/judges/"), () => HttpResponse.json([])));
  server.use(
    http.post(api("/judges/"), () =>
      HttpResponse.json({ detail: "Judge already exists" }, { status: 409 }),
    ),
  );
  renderApp("/admin/judges");
  await userEvent.click(await screen.findByRole("button", { name: "New judge" }));
  await userEvent.type(screen.getByLabelText("First name"), "Ana");
  await userEvent.type(screen.getByLabelText("Last name"), "Meyer");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Judge already exists")).toBeInTheDocument();
  expect(screen.getByLabelText("First name")).toBeInTheDocument();
});

test("filters by country as a server round trip", async () => {
  const seen: (string | null)[] = [];
  server.use(
    http.get(api("/judges/"), ({ request }) => {
      seen.push(new URL(request.url).searchParams.get("country_code"));
      return HttpResponse.json([makeJudge({ id: 1, first_name: "Naledi", last_name: "Dlamini" })]);
    }),
  );
  renderApp("/admin/judges");
  expect(await screen.findByText("Naledi")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Country"), "BUL");
  await waitFor(() => expect(seen).toContain("BUL"));
});

test("search filters rows client-side without refetching", async () => {
  let calls = 0;
  server.use(
    http.get(api("/judges/"), () => {
      calls += 1;
      return HttpResponse.json([
        makeJudge({ id: 1, first_name: "Naledi", last_name: "Dlamini" }),
        makeJudge({ id: 2, first_name: "Elena", last_name: "Petrova" }),
      ]);
    }),
  );
  renderApp("/admin/judges");
  expect(await screen.findByText("Naledi")).toBeInTheDocument();
  const before = calls;
  await userEvent.type(screen.getByLabelText("Search"), "Petrova");
  await waitFor(() => expect(screen.queryByText("Naledi")).not.toBeInTheDocument());
  expect(screen.getByText("Elena")).toBeInTheDocument();
  expect(calls).toBe(before);
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `npm test -- --run test/features/admin/judges/JudgesPage.test.tsx`
Expected: FAIL — no route matches `/admin/judges`, so the queries never fire and `findByText` times out.

- [ ] **Step 4: Write `JudgeForm.tsx`**

Create `frontend/src/features/admin/judges/JudgeForm.tsx`:

```tsx
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
```

- [ ] **Step 5: Write `JudgesPage.tsx`**

Create `frontend/src/features/admin/judges/JudgesPage.tsx`. Note the country filter is a
genuine server round trip with `country` in the query key; `search` stays out of the key.

```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiDetail, client } from "../../../api/client";
import type { JudgeRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FormDialog } from "../components/FormDialog";
import { ResourceTable } from "../components/ResourceTable";
import { useResourceDelete } from "../hooks/useResourceDelete";
import { useResourceList } from "../hooks/useResourceList";
import { JudgeForm, type JudgeBody } from "./JudgeForm";

/** Countries offered by the filter. Judges are few; a free-text filter would be worse. */
const COUNTRIES = ["RSA", "BUL", "RUS", "ESP", "ITA", "JPN", "UKR", "USA"];

export function JudgesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [country, setCountry] = useState("");
  const [dialog, setDialog] = useState<{ row: JudgeRead | null } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const list = useResourceList<JudgeRead>({
    queryKey: ["judges", country],
    fetchRows: async () => {
      const { data, error } = await client.GET("/judges/", {
        params: { query: country === "" ? {} : { country_code: country } },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    search,
    searchText: (j) => `${j.first_name} ${j.last_name} ${j.brevet ?? ""}`,
  });

  const saveMutation = useMutation({
    mutationFn: async (body: JudgeBody) => {
      const editingRow = dialog?.row ?? null;
      if (editingRow) {
        const { data, error } = await client.PATCH("/judges/{judge_id}", {
          params: { path: { judge_id: editingRow.id } },
          body,
        });
        if (error) throw new Error(apiDetail(error));
        return data;
      }
      const { data, error } = await client.POST("/judges/", {
        body: body as { first_name: string; last_name: string },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      clearDeleteError();
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["judges"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });

  const {
    confirmDelete,
    error: deleteError,
    clearError: clearDeleteError,
  } = useResourceDelete<JudgeRead>({
    queryKey: ["judges"],
    // JudgeScore.judge_id and PenaltyRecord.judge_id are both ondelete="RESTRICT",
    // so a judge with scores or penalties can't be deleted at all — nothing cascades.
    // The 409 detail says so; the confirm copy must not promise otherwise.
    describe: (j) => `Delete judge "${j.first_name} ${j.last_name}"?`,
    remove: async (j) => {
      const { error } = await client.DELETE("/judges/{judge_id}", {
        params: { path: { judge_id: j.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
  });

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-xl font-bold">Judges</h1>
        <button
          type="button"
          onClick={() => {
            setFormError(null);
            setDialog({ row: null });
          }}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New judge
        </button>
      </div>
      <div className="mb-3 flex gap-4">
        <label className="text-sm">
          Search
          <input
            aria-label="Search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="ml-2 rounded border border-gray-300 p-1"
          />
        </label>
        <label className="text-sm">
          Country
          <select
            aria-label="Country"
            value={country}
            onChange={(e) => {
              clearDeleteError();
              setCountry(e.target.value);
            }}
            className="ml-2 rounded border border-gray-300 p-1"
          >
            <option value="">— all —</option>
            {COUNTRIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ErrorBanner message={list.error ?? deleteError} />
      {list.loaded && (
        <ResourceTable
          rows={list.rows}
          columns={[
            { header: "First name", render: (j) => j.first_name },
            { header: "Last name", render: (j) => j.last_name },
            { header: "Country", render: (j) => j.country_code ?? "—" },
            { header: "Brevet", render: (j) => j.brevet ?? "—" },
          ]}
          rowLabel={(j) => `${j.first_name} ${j.last_name}`}
          onEdit={(j) => {
            setFormError(null);
            setDialog({ row: j });
          }}
          onDelete={confirmDelete}
          emptyMessage="No judges yet."
        />
      )}
      <FormDialog
        open={dialog !== null}
        title={dialog?.row ? "Edit judge" : "New judge"}
        onClose={() => setDialog(null)}
      >
        {dialog && (
          <JudgeForm
            key={dialog.row?.id ?? "new"}
            initial={dialog.row}
            pending={saveMutation.isPending}
            error={formError}
            onSubmit={(body) => saveMutation.mutate(body)}
            onCancel={() => setDialog(null)}
          />
        )}
      </FormDialog>
    </div>
  );
}
```

- [ ] **Step 6: Wire the route and the sidebar**

In `frontend/src/App.tsx`, add the import and the route inside the `/admin` block, after `gymnasts`:

```tsx
import { JudgesPage } from "./features/admin/judges/JudgesPage";
```

```tsx
<Route path="judges" element={<JudgesPage />} />
```

In `frontend/src/features/admin/AdminShell.tsx`, append to `RESOURCES`:

```tsx
  { path: "judges", label: "Judges" },
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `npm test -- --run test/features/admin/judges/JudgesPage.test.tsx`
Expected: PASS, 10 tests.

- [ ] **Step 8: Verify the client-search test is load-bearing**

Temporarily change `searchText` in `JudgesPage.tsx` to `() => ""` and re-run. The
"search filters rows client-side" test MUST fail. Restore it afterwards. A search test
that passes with a broken accessor is worthless — this was Important #2 of the Phase 2
final review.

- [ ] **Step 9: Run the full suite and build**

Run: `npm test -- --run && npm run build`
Expected: all tests pass (163 = 153 + 10), clean build.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/features/admin/judges frontend/src/App.tsx frontend/src/features/admin/AdminShell.tsx frontend/test/features/admin/judges
git commit -m "feat: judges admin screen"
```

---

### Task 2: Fix the gymnast form's group select

**Files:**
- Modify: `frontend/src/features/admin/gymnasts/GymnastForm.tsx:56-120`
- Test: `frontend/test/features/admin/gymnasts/GymnastsPage.test.tsx` (append)

**Interfaces:**
- Consumes: `GymnastForm`'s existing props (`initial`, `clubs`, `groups`, …) — unchanged signature, so `GymnastsPage.tsx` needs no edit.
- Produces: nothing new.

**The bug:** the group select offers every group regardless of club. `Group.club_id` is
`nullable=False`, and `backend/app/routers/gymnast.py` rejects a mismatch on both write
paths (line 44 on POST, line 117 on PATCH). Every cross-club option is therefore
*provably* invalid for the gymnast being edited.

**Three required behaviours** — behaviour 3 is the load-bearing one:

1. Group is **disabled until a club is chosen**, with a hint.
2. Changing the club **clears `group_id`**, so an invalid pair can't be assembled from
   individually-valid steps.
3. On edit, the **currently-assigned group stays in the options even if it's an orphan**,
   flagged. Without this, filtering blanks the select for a pre-existing cross-club
   gymnast and silently drops the assignment on save.

**Known accepted gap:** the backend permits `club_id = None` with `group_id` set
(`routers/gymnast.py:37` nests the check inside `if payload.club_id is not None`). The
form forbids it via behaviour 1. Do not change the backend.

- [ ] **Step 1: Write the failing tests**

Append to `frontend/test/features/admin/gymnasts/GymnastsPage.test.tsx` (keep the
existing imports; add `makeGroup`/`makeClub` to the fixture import if absent):

```tsx
test("offers only groups belonging to the selected club", async () => {
  server.use(http.get(api("/gymnasts/"), () => HttpResponse.json([])));
  server.use(
    http.get(api("/clubs/"), () =>
      HttpResponse.json([makeClub({ id: 1, name: "Cape RG" }), makeClub({ id: 2, name: "Durban RG" })]),
    ),
  );
  server.use(
    http.get(api("/groups/"), () =>
      HttpResponse.json([
        makeGroup({ id: 10, club_id: 1, name: "Cape Juniors" }),
        makeGroup({ id: 20, club_id: 2, name: "Durban Seniors" }),
      ]),
    ),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "New gymnast" }));

  const group = screen.getByLabelText("Group");
  expect(group).toBeDisabled();

  await waitFor(() => expect(screen.getByText("Cape RG")).toBeInTheDocument());
  await userEvent.selectOptions(screen.getByLabelText("Club"), "1");

  expect(group).toBeEnabled();
  expect(within(group).getByText("Cape Juniors")).toBeInTheDocument();
  expect(within(group).queryByText("Durban Seniors")).not.toBeInTheDocument();
});

test("clears the group when the club changes", async () => {
  server.use(http.get(api("/gymnasts/"), () => HttpResponse.json([])));
  server.use(
    http.get(api("/clubs/"), () =>
      HttpResponse.json([makeClub({ id: 1, name: "Cape RG" }), makeClub({ id: 2, name: "Durban RG" })]),
    ),
  );
  server.use(
    http.get(api("/groups/"), () =>
      HttpResponse.json([
        makeGroup({ id: 10, club_id: 1, name: "Cape Juniors" }),
        makeGroup({ id: 20, club_id: 2, name: "Durban Seniors" }),
      ]),
    ),
  );
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/gymnasts/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGymnast(), { status: 201 });
    }),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "New gymnast" }));
  await waitFor(() => expect(screen.getByText("Cape RG")).toBeInTheDocument());

  await userEvent.selectOptions(screen.getByLabelText("Club"), "1");
  await userEvent.selectOptions(screen.getByLabelText("Group"), "10");
  await userEvent.selectOptions(screen.getByLabelText("Club"), "2");

  expect((screen.getByLabelText("Group") as HTMLSelectElement).value).toBe("");

  await userEvent.type(screen.getByLabelText("First name"), "Ana");
  await userEvent.type(screen.getByLabelText("Last name"), "Meyer");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(posted).not.toBeNull());
  expect(posted!.group_id).toBeNull();
  expect(posted!.club_id).toBe(2);
});

test("keeps an orphaned group in the options and does not drop it on an unrelated save", async () => {
  // Gymnast 5 is in club 1 but assigned group 20, which belongs to club 2.
  // Filtering must not blank the select and silently unassign the group.
  server.use(
    http.get(api("/gymnasts/"), () =>
      HttpResponse.json([
        makeGymnast({ id: 5, club_id: 1, group_id: 20, first_name: "Ana", last_name: "Meyer" }),
      ]),
    ),
  );
  server.use(http.get(api("/clubs/"), () => HttpResponse.json([makeClub({ id: 1, name: "Cape RG" })])));
  server.use(
    http.get(api("/groups/"), () =>
      HttpResponse.json([
        makeGroup({ id: 10, club_id: 1, name: "Cape Juniors" }),
        makeGroup({ id: 20, club_id: 2, name: "Durban Seniors" }),
      ]),
    ),
  );
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/gymnasts/5"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGymnast({ id: 5 }));
    }),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Ana Meyer" }));

  const group = screen.getByLabelText("Group") as HTMLSelectElement;
  await waitFor(() => expect(group.value).toBe("20"));
  expect(within(group).getByText(/Durban Seniors/)).toBeInTheDocument();

  const first = screen.getByLabelText("First name");
  await userEvent.clear(first);
  await userEvent.type(first, "Anna");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() => expect(patched).toEqual({ first_name: "Anna" }));
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- --run test/features/admin/gymnasts/GymnastsPage.test.tsx`
Expected: FAIL — the group select is currently always enabled and lists every group.

- [ ] **Step 3: Implement the filtering in `GymnastForm.tsx`**

Replace the `useForm` destructure (line 56) to also pull `watch` and `setValue`, and add
the derived option list. Insert after the `const { dirtyFields, errors } = formState;`
line:

```tsx
  const selectedClubId = watch("club_id");

  /**
   * Group.club_id is NOT NULL and routers/gymnast.py rejects a group whose club differs
   * from the gymnast's (line 44 on POST, line 117 on PATCH), so cross-club options are
   * provably invalid — filtering them out is correctness, not polish.
   *
   * The assigned group is always kept, even when it's an orphan from another club:
   * dropping it would blank the select and silently unassign the gymnast on the next
   * save, which looks like a successful edit.
   */
  const groupOptions = (() => {
    const inClub = groups.filter((g) => String(g.club_id) === selectedClubId);
    const assignedId = initial?.group_id;
    if (assignedId == null || inClub.some((g) => g.id === assignedId)) return inClub;
    const orphan = groups.find((g) => g.id === assignedId);
    return orphan ? [{ ...orphan, name: `${orphan.name} (other club)` }, ...inClub] : inClub;
  })();
```

Change the `useForm` destructure on line 56 from:

```tsx
  const { register, handleSubmit, formState } = useForm<GymnastFormValues>({
```

to:

```tsx
  const { register, handleSubmit, formState, watch, setValue } = useForm<GymnastFormValues>({
```

Replace the two `FkSelect` blocks (lines 109-120) with:

```tsx
      <FkSelect
        label="Club"
        noneLabel="— none —"
        options={clubs.map((c) => ({ id: c.id, label: c.name }))}
        {...register("club_id", {
          onChange: () => setValue("group_id", "", { shouldDirty: true }),
        })}
      />
      <FkSelect
        label="Group"
        noneLabel="— none —"
        options={groupOptions.map((g) => ({ id: g.id, label: g.name }))}
        disabled={selectedClubId === ""}
        title={selectedClubId === "" ? "Select a club to choose a group" : undefined}
        {...register("group_id")}
      />
      {selectedClubId === "" && (
        <span className="text-xs text-gray-500">Select a club to choose a group</span>
      )}
```

Note: `register`'s `onChange` option runs *in addition to* RHF's own handler, so the club
value still updates normally. `shouldDirty: true` matters — without it, clearing the
group on a club change would not be included in the PATCH body.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test -- --run test/features/admin/gymnasts/GymnastsPage.test.tsx`
Expected: PASS, including the three new tests.

- [ ] **Step 5: Verify the orphan test is load-bearing**

Temporarily simplify `groupOptions` to just
`groups.filter((g) => String(g.club_id) === selectedClubId)` and re-run. The
"keeps an orphaned group" test MUST fail. Restore afterwards.

- [ ] **Step 6: Run the full suite and build**

Run: `npm test -- --run && npm run build`
Expected: all pass (166), clean build.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/admin/gymnasts/GymnastForm.tsx frontend/test/features/admin/gymnasts/GymnastsPage.test.tsx
git commit -m "fix: filter gymnast group options to the selected club"
```

---

### Task 3: Routine profiles — list and create

**Files:**
- Modify: `frontend/test/fixtures.ts` (add `makeRoutineProfile`)
- Create: `frontend/src/features/admin/routine-profiles/RoutineProfileCreateForm.tsx`
- Create: `frontend/src/features/admin/routine-profiles/RoutineProfilesPage.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/features/admin/AdminShell.tsx`
- Test: `frontend/test/features/admin/routine-profiles/RoutineProfilesPage.test.tsx`

**Interfaces:**
- Consumes: `RoutineProfileRead` (added in Task 1), `useCompetitorNames` from `src/lib/useCompetitorNames.ts`, `APPARATUS`/`LEVELS`/`labelize` from `src/lib/domain.ts`, the shared admin layer.
- Produces: `RoutineProfileCreateForm`, `type RoutineProfileCreateBody`. Task 4 adds the edit form beside it and wires it into this page.

**Backend facts (verified):**
- `backend/app/schemas/routine_profile.py`: `RoutineProfileCreate` requires exactly one of `gymnast_id`/`group_id` (`validate_gymnast_or_group`), plus `apparatus` and `level`; `music_url` optional; `choreography_notes` optional with `Field(max_length=500)`.
- `UniqueConstraint` on (owner, apparatus, level) → duplicates 409.
- `list_routine_profiles` accepts `gymnast_id`, `group_id`, `apparatus`, `level`. This plan wires **only `apparatus` and `level`** — an owner filter would need its own picker, and name search covers it.

**The owner-picker pattern** — copy `src/features/entries/EntryCreateForm.tsx:12,53-54,81-99`
verbatim in shape: a `kind` enum radio plus a **single** `competitorId` field, mapped at
submit. One field rather than two is the point: switching kind cannot leave a stale value
behind, so exactly-one-of is structural and the client never reproduces the backend
validator.

- [ ] **Step 1: Add the fixture**

In `frontend/test/fixtures.ts`, add `RoutineProfileRead` to the type import list and append:

```ts
export function makeRoutineProfile(
  overrides: Partial<RoutineProfileRead> = {},
): RoutineProfileRead {
  return {
    id: id(),
    gymnast_id: 1,
    group_id: null,
    apparatus: "ribbon",
    level: "level_3",
    music_url: null,
    choreography_notes: null,
    ...overrides,
  };
}
```

- [ ] **Step 2: Write the failing tests**

Create `frontend/test/features/admin/routine-profiles/RoutineProfilesPage.test.tsx`:

```tsx
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeGroup, makeGymnast, makeRoutineProfile } from "../../../fixtures";
import { api, server } from "../../../msw/server";
import { renderApp } from "../../../utils";

function seedOwners() {
  server.use(
    http.get(api("/gymnasts/"), () =>
      HttpResponse.json([makeGymnast({ id: 1, first_name: "Ana", last_name: "Meyer" })]),
    ),
  );
  server.use(
    http.get(api("/groups/"), () => HttpResponse.json([makeGroup({ id: 9, name: "Junior Team A" })])),
  );
}

test("lists profiles with resolved owner names", async () => {
  seedOwners();
  server.use(
    http.get(api("/routine-profiles/"), () =>
      HttpResponse.json([
        makeRoutineProfile({ id: 1, gymnast_id: 1, group_id: null, apparatus: "ribbon", level: "level_3" }),
        makeRoutineProfile({ id: 2, gymnast_id: null, group_id: 9, apparatus: "hoop", level: "level_2" }),
      ]),
    ),
  );
  renderApp("/admin/routine-profiles");
  expect(await screen.findByText("Ana Meyer")).toBeInTheDocument();
  expect(screen.getByText("Junior Team A")).toBeInTheDocument();
});

test("shows an empty message when there are no profiles", async () => {
  seedOwners();
  server.use(http.get(api("/routine-profiles/"), () => HttpResponse.json([])));
  renderApp("/admin/routine-profiles");
  expect(await screen.findByText("No routine profiles yet.")).toBeInTheDocument();
});

test("surfaces a list error", async () => {
  seedOwners();
  server.use(
    http.get(api("/routine-profiles/"), () =>
      HttpResponse.json({ detail: "Database unavailable" }, { status: 500 }),
    ),
  );
  renderApp("/admin/routine-profiles");
  expect(await screen.findByRole("alert")).toHaveTextContent("Database unavailable");
});

test("creates a gymnast profile, sending group_id null", async () => {
  seedOwners();
  server.use(http.get(api("/routine-profiles/"), () => HttpResponse.json([])));
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/routine-profiles/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeRoutineProfile(), { status: 201 });
    }),
  );
  renderApp("/admin/routine-profiles");
  await userEvent.click(await screen.findByRole("button", { name: "New routine profile" }));
  await waitFor(() => expect(screen.getByText("Ana Meyer")).toBeInTheDocument());
  await userEvent.selectOptions(screen.getByLabelText("Gymnast"), "1");
  await userEvent.selectOptions(screen.getByLabelText("Apparatus"), "ribbon");
  await userEvent.selectOptions(screen.getByLabelText("Level"), "level_3");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toEqual({
      gymnast_id: 1,
      group_id: null,
      apparatus: "ribbon",
      level: "level_3",
      music_url: null,
      choreography_notes: null,
    }),
  );
});

test("switching owner kind to Group sends gymnast_id null", async () => {
  seedOwners();
  server.use(http.get(api("/routine-profiles/"), () => HttpResponse.json([])));
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/routine-profiles/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeRoutineProfile(), { status: 201 });
    }),
  );
  renderApp("/admin/routine-profiles");
  await userEvent.click(await screen.findByRole("button", { name: "New routine profile" }));
  await waitFor(() => expect(screen.getByText("Ana Meyer")).toBeInTheDocument());
  await userEvent.selectOptions(screen.getByLabelText("Gymnast"), "1");
  await userEvent.click(screen.getByLabelText("Group"));
  await waitFor(() => expect(screen.getByLabelText("Group name")).toBeInTheDocument());
  await userEvent.selectOptions(screen.getByLabelText("Group name"), "9");
  await userEvent.selectOptions(screen.getByLabelText("Apparatus"), "hoop");
  await userEvent.selectOptions(screen.getByLabelText("Level"), "level_2");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toEqual({
      gymnast_id: null,
      group_id: 9,
      apparatus: "hoop",
      level: "level_2",
      music_url: null,
      choreography_notes: null,
    }),
  );
});

test("blocks submission when no owner is picked", async () => {
  seedOwners();
  server.use(http.get(api("/routine-profiles/"), () => HttpResponse.json([])));
  let called = false;
  server.use(
    http.post(api("/routine-profiles/"), () => {
      called = true;
      return HttpResponse.json(makeRoutineProfile(), { status: 201 });
    }),
  );
  renderApp("/admin/routine-profiles");
  await userEvent.click(await screen.findByRole("button", { name: "New routine profile" }));
  await userEvent.selectOptions(screen.getByLabelText("Apparatus"), "ribbon");
  await userEvent.selectOptions(screen.getByLabelText("Level"), "level_3");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Pick a gymnast or group")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("blocks choreography notes over 500 characters", async () => {
  seedOwners();
  server.use(http.get(api("/routine-profiles/"), () => HttpResponse.json([])));
  let called = false;
  server.use(
    http.post(api("/routine-profiles/"), () => {
      called = true;
      return HttpResponse.json(makeRoutineProfile(), { status: 201 });
    }),
  );
  renderApp("/admin/routine-profiles");
  await userEvent.click(await screen.findByRole("button", { name: "New routine profile" }));
  await waitFor(() => expect(screen.getByText("Ana Meyer")).toBeInTheDocument());
  await userEvent.selectOptions(screen.getByLabelText("Gymnast"), "1");
  await userEvent.selectOptions(screen.getByLabelText("Apparatus"), "ribbon");
  await userEvent.selectOptions(screen.getByLabelText("Level"), "level_3");
  const notes = screen.getByLabelText("Choreography notes");
  await userEvent.click(notes);
  await userEvent.paste("x".repeat(501));
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("At most 500 characters")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("shows the 409 detail on a duplicate profile", async () => {
  seedOwners();
  server.use(http.get(api("/routine-profiles/"), () => HttpResponse.json([])));
  server.use(
    http.post(api("/routine-profiles/"), () =>
      HttpResponse.json({ detail: "Routine profile already exists" }, { status: 409 }),
    ),
  );
  renderApp("/admin/routine-profiles");
  await userEvent.click(await screen.findByRole("button", { name: "New routine profile" }));
  await waitFor(() => expect(screen.getByText("Ana Meyer")).toBeInTheDocument());
  await userEvent.selectOptions(screen.getByLabelText("Gymnast"), "1");
  await userEvent.selectOptions(screen.getByLabelText("Apparatus"), "ribbon");
  await userEvent.selectOptions(screen.getByLabelText("Level"), "level_3");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Routine profile already exists")).toBeInTheDocument();
});

test("filters by apparatus as a server round trip", async () => {
  seedOwners();
  const seen: (string | null)[] = [];
  server.use(
    http.get(api("/routine-profiles/"), ({ request }) => {
      seen.push(new URL(request.url).searchParams.get("apparatus"));
      return HttpResponse.json([makeRoutineProfile({ id: 1, gymnast_id: 1, group_id: null })]);
    }),
  );
  renderApp("/admin/routine-profiles");
  expect(await screen.findByText("Ana Meyer")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Apparatus filter"), "hoop");
  await waitFor(() => expect(seen).toContain("hoop"));
});

test("search filters rows client-side without refetching", async () => {
  seedOwners();
  let calls = 0;
  server.use(
    http.get(api("/routine-profiles/"), () => {
      calls += 1;
      return HttpResponse.json([
        makeRoutineProfile({ id: 1, gymnast_id: 1, group_id: null }),
        makeRoutineProfile({ id: 2, gymnast_id: null, group_id: 9 }),
      ]);
    }),
  );
  renderApp("/admin/routine-profiles");
  expect(await screen.findByText("Ana Meyer")).toBeInTheDocument();
  const before = calls;
  await userEvent.type(screen.getByLabelText("Search"), "Junior");
  await waitFor(() => expect(screen.queryByText("Ana Meyer")).not.toBeInTheDocument());
  expect(screen.getByText("Junior Team A")).toBeInTheDocument();
  expect(calls).toBe(before);
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `npm test -- --run test/features/admin/routine-profiles/RoutineProfilesPage.test.tsx`
Expected: FAIL — no route matches `/admin/routine-profiles`.

- [ ] **Step 4: Write `RoutineProfileCreateForm.tsx`**

Create `frontend/src/features/admin/routine-profiles/RoutineProfileCreateForm.tsx`:

```tsx
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
        <label className="mr-4">
          <input type="radio" value="gymnast" {...register("kind")} aria-label="Gymnast owner" />{" "}
          Gymnast
        </label>
        <label>
          <input type="radio" value="group" {...register("kind")} aria-label="Group" /> Group
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
```

- [ ] **Step 5: Write `RoutineProfilesPage.tsx`**

Create `frontend/src/features/admin/routine-profiles/RoutineProfilesPage.tsx`. Task 4
replaces the create-only dialog body with a create/edit switch; leave the structure
ready for that.

```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiDetail, client } from "../../../api/client";
import type { Apparatus, RoutineProfileRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { APPARATUS, labelize } from "../../../lib/domain";
import { useCompetitorNames } from "../../../lib/useCompetitorNames";
import { FormDialog } from "../components/FormDialog";
import { ResourceTable } from "../components/ResourceTable";
import { useResourceDelete } from "../hooks/useResourceDelete";
import { useResourceList } from "../hooks/useResourceList";
import {
  RoutineProfileCreateForm,
  type RoutineProfileCreateBody,
} from "./RoutineProfileCreateForm";

export function RoutineProfilesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [apparatus, setApparatus] = useState("");
  const [dialog, setDialog] = useState<{ row: RoutineProfileRead | null } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  // Reused from the scoring screen — resolves the gymnast-or-group name pair.
  const { gymnasts, groups, error: namesError } = useCompetitorNames();

  const ownerName = (p: RoutineProfileRead): string => {
    if (p.gymnast_id != null) {
      const g = gymnasts.find((g) => g.id === p.gymnast_id);
      return g ? `${g.first_name} ${g.last_name}` : `Gymnast #${p.gymnast_id}`;
    }
    const grp = groups.find((g) => g.id === p.group_id);
    return grp ? grp.name : `Group #${p.group_id}`;
  };

  const list = useResourceList<RoutineProfileRead>({
    queryKey: ["routine-profiles", apparatus],
    fetchRows: async () => {
      const { data, error } = await client.GET("/routine-profiles/", {
        params: { query: apparatus === "" ? {} : { apparatus: apparatus as Apparatus } },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    search,
    searchText: (p) => `${ownerName(p)} ${p.apparatus} ${p.level}`,
  });

  const saveMutation = useMutation({
    mutationFn: async (body: RoutineProfileCreateBody) => {
      const { data, error } = await client.POST("/routine-profiles/", { body });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      clearDeleteError();
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["routine-profiles"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });

  const {
    confirmDelete,
    error: deleteError,
    clearError: clearDeleteError,
  } = useResourceDelete<RoutineProfileRead>({
    queryKey: ["routine-profiles"],
    describe: (p) =>
      `Delete the ${labelize(p.apparatus)} profile for ${ownerName(p)}? Routine music will fall back to none.`,
    remove: async (p) => {
      const { error } = await client.DELETE("/routine-profiles/{routine_profile_id}", {
        params: { path: { routine_profile_id: p.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
  });

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-xl font-bold">Routine profiles</h1>
        <button
          type="button"
          onClick={() => {
            setFormError(null);
            setDialog({ row: null });
          }}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New routine profile
        </button>
      </div>
      <div className="mb-3 flex gap-4">
        <label className="text-sm">
          Search
          <input
            aria-label="Search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="ml-2 rounded border border-gray-300 p-1"
          />
        </label>
        <label className="text-sm">
          Apparatus
          <select
            aria-label="Apparatus filter"
            value={apparatus}
            onChange={(e) => {
              clearDeleteError();
              setApparatus(e.target.value);
            }}
            className="ml-2 rounded border border-gray-300 p-1"
          >
            <option value="">— all —</option>
            {APPARATUS.map((a) => (
              <option key={a} value={a}>
                {labelize(a)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ErrorBanner message={list.error ?? deleteError ?? namesError?.message ?? null} />
      {list.loaded && (
        <ResourceTable
          rows={list.rows}
          columns={[
            { header: "Owner", render: (p) => ownerName(p) },
            { header: "Apparatus", render: (p) => labelize(p.apparatus) },
            { header: "Level", render: (p) => labelize(p.level) },
            { header: "Music URL", render: (p) => p.music_url ?? "—" },
          ]}
          rowLabel={(p) => `${ownerName(p)} ${labelize(p.apparatus)}`}
          onEdit={(p) => {
            setFormError(null);
            setDialog({ row: p });
          }}
          onDelete={confirmDelete}
          emptyMessage="No routine profiles yet."
        />
      )}
      <FormDialog
        open={dialog !== null}
        title={dialog?.row ? "Edit routine profile" : "New routine profile"}
        onClose={() => setDialog(null)}
      >
        {dialog && !dialog.row && (
          <RoutineProfileCreateForm
            gymnasts={gymnasts}
            groups={groups}
            pending={saveMutation.isPending}
            error={formError}
            onSubmit={(body) => saveMutation.mutate(body)}
            onCancel={() => setDialog(null)}
          />
        )}
      </FormDialog>
    </div>
  );
}
```

- [ ] **Step 6: Wire the route and the sidebar**

In `frontend/src/App.tsx`:

```tsx
import { RoutineProfilesPage } from "./features/admin/routine-profiles/RoutineProfilesPage";
```

```tsx
<Route path="routine-profiles" element={<RoutineProfilesPage />} />
```

In `frontend/src/features/admin/AdminShell.tsx`, append to `RESOURCES` after Judges:

```tsx
  { path: "routine-profiles", label: "Routine profiles" },
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `npm test -- --run test/features/admin/routine-profiles/RoutineProfilesPage.test.tsx`
Expected: PASS, 10 tests.

- [ ] **Step 8: Run the full suite and build**

Run: `npm test -- --run && npm run build`
Expected: all pass (176), clean build.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/features/admin/routine-profiles frontend/src/App.tsx frontend/src/features/admin/AdminShell.tsx frontend/test/fixtures.ts frontend/test/features/admin/routine-profiles
git commit -m "feat: routine profiles admin screen (list + create)"
```

---

### Task 4: Routine profile edit form

**Files:**
- Create: `frontend/src/features/admin/routine-profiles/RoutineProfileEditForm.tsx`
- Modify: `frontend/src/features/admin/routine-profiles/RoutineProfilesPage.tsx` (save mutation + dialog body)
- Test: `frontend/test/features/admin/routine-profiles/RoutineProfilesPage.test.tsx` (append)

**Interfaces:**
- Consumes: `RoutineProfileRead`, `ownerName` (defined inside `RoutineProfilesPage`; pass the resolved string in as a prop rather than re-deriving it).
- Produces: `RoutineProfileEditForm`, `type RoutineProfileEditBody = { music_url?: string | null; choreography_notes?: string | null }`.

**Why this is a separate component, not the create form with disabled fields:**
`RoutineProfileUpdate` accepts **only** `music_url` and `choreography_notes`. Owner,
apparatus and level together form the model's `UniqueConstraint` and are create-only
(delete + recreate to change them). Four inert greyed-out controls would misrepresent
"never editable here" as "temporarily disabled", so identity renders as a **read-only
context line** instead. This is a deliberate departure from the Phase 2
`disabled={!!initial}` convention — do not "fix" it back.

- [ ] **Step 1: Write the failing tests**

Append to `frontend/test/features/admin/routine-profiles/RoutineProfilesPage.test.tsx`:

```tsx
test("edit form shows identity as read-only text, not form controls", async () => {
  seedOwners();
  server.use(
    http.get(api("/routine-profiles/"), () =>
      HttpResponse.json([
        makeRoutineProfile({
          id: 3,
          gymnast_id: 1,
          group_id: null,
          apparatus: "ribbon",
          level: "level_3",
          music_url: "https://old.example/m.mp3",
        }),
      ]),
    ),
  );
  renderApp("/admin/routine-profiles");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Ana Meyer ribbon" }));

  expect(await screen.findByText("Ana Meyer · ribbon · level 3")).toBeInTheDocument();
  // Identity is text, not inputs — these controls must not exist in the edit dialog.
  expect(screen.queryByLabelText("Gymnast")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Apparatus")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Level")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Music URL")).toHaveValue("https://old.example/m.mp3");
});

test("PATCHes only the changed field on edit", async () => {
  seedOwners();
  server.use(
    http.get(api("/routine-profiles/"), () =>
      HttpResponse.json([
        makeRoutineProfile({ id: 3, gymnast_id: 1, group_id: null, apparatus: "ribbon", level: "level_3" }),
      ]),
    ),
  );
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/routine-profiles/3"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeRoutineProfile({ id: 3 }));
    }),
  );
  renderApp("/admin/routine-profiles");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Ana Meyer ribbon" }));
  await userEvent.type(await screen.findByLabelText("Music URL"), "https://new.example/m.mp3");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ music_url: "https://new.example/m.mp3" }));
});

test("clearing the music URL sends null", async () => {
  seedOwners();
  server.use(
    http.get(api("/routine-profiles/"), () =>
      HttpResponse.json([
        makeRoutineProfile({ id: 3, gymnast_id: 1, group_id: null, music_url: "https://old.example/m.mp3" }),
      ]),
    ),
  );
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/routine-profiles/3"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeRoutineProfile({ id: 3 }));
    }),
  );
  renderApp("/admin/routine-profiles");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Ana Meyer ribbon" }));
  await userEvent.clear(await screen.findByLabelText("Music URL"));
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ music_url: null }));
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- --run test/features/admin/routine-profiles/RoutineProfilesPage.test.tsx`
Expected: FAIL — the edit dialog currently renders nothing (`dialog && !dialog.row`).

- [ ] **Step 3: Write `RoutineProfileEditForm.tsx`**

Create `frontend/src/features/admin/routine-profiles/RoutineProfileEditForm.tsx`:

```tsx
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
 * here (delete + recreate), not merely disabled for now.
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
```

- [ ] **Step 4: Wire it into `RoutineProfilesPage.tsx`**

Add the import:

```tsx
import {
  RoutineProfileEditForm,
  type RoutineProfileEditBody,
} from "./RoutineProfileEditForm";
```

Replace the `saveMutation` `mutationFn` with a create/edit switch (the rest of the
mutation — `onSuccess`, `onError` — is unchanged):

```tsx
  const saveMutation = useMutation({
    mutationFn: async (body: RoutineProfileCreateBody | RoutineProfileEditBody) => {
      const editingRow = dialog?.row ?? null;
      if (editingRow) {
        const { data, error } = await client.PATCH(
          "/routine-profiles/{routine_profile_id}",
          {
            params: { path: { routine_profile_id: editingRow.id } },
            body: body as RoutineProfileEditBody,
          },
        );
        if (error) throw new Error(apiDetail(error));
        return data;
      }
      const { data, error } = await client.POST("/routine-profiles/", {
        body: body as RoutineProfileCreateBody,
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      clearDeleteError();
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["routine-profiles"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });
```

Replace the dialog body with the create/edit switch:

```tsx
        {dialog && !dialog.row && (
          <RoutineProfileCreateForm
            gymnasts={gymnasts}
            groups={groups}
            pending={saveMutation.isPending}
            error={formError}
            onSubmit={(body) => saveMutation.mutate(body)}
            onCancel={() => setDialog(null)}
          />
        )}
        {dialog?.row && (
          <RoutineProfileEditForm
            key={dialog.row.id}
            initial={dialog.row}
            ownerName={ownerName(dialog.row)}
            pending={saveMutation.isPending}
            error={formError}
            onSubmit={(body) => saveMutation.mutate(body)}
            onCancel={() => setDialog(null)}
          />
        )}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `npm test -- --run test/features/admin/routine-profiles/RoutineProfilesPage.test.tsx`
Expected: PASS, 13 tests.

- [ ] **Step 6: Run the full suite and build**

Run: `npm test -- --run && npm run build`
Expected: all pass (179), clean build.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/admin/routine-profiles frontend/test/features/admin/routine-profiles
git commit -m "feat: routine profile edit form"
```

---

### Task 5: Meet form and create on the meet list

**Files:**
- Create: `frontend/src/features/meets/MeetForm.tsx`
- Modify: `frontend/src/features/meets/MeetListPage.tsx` (whole file — row restructure + create)
- Modify: `frontend/test/features/meets/MeetListPage.test.tsx` (**already exists, 2 tests** — append, and fix both existing tests per Step 1)
- Modify: `frontend/test/App.test.tsx:6-10` (same districts-handler fix)

**BREAKING CHANGE — read before writing any code.** `MeetListPage` gains a
`GET /districts/` query. `test/setup.ts` runs MSW with
`server.listen({ onUnhandledRequest: "error" })`, so **any test that renders `/` without a
`/districts/` handler will now fail**. Three existing tests do exactly that:
`test/features/meets/MeetListPage.test.tsx` (both tests) and `test/App.test.tsx:7`. They
must each gain a districts handler. This is a mechanical fix, not a behaviour change —
do not "fix" it by removing the districts query.

**Interfaces:**
- Consumes: `MeetRead`, `DistrictRead`, `FormDialog`, `FkSelect`, `useResourceDelete` (Task 6), `labelize`.
- Produces: `MeetForm`, `type MeetBody`. Task 6 reuses `MeetForm` unchanged from the meet shell.

**Backend facts (verified — `backend/app/schemas/meet.py`):**
- `name`/`location` are `Field(min_length=2, max_length=100)`; `start_date`/`end_date` required on create.
- `medal_gold_min`/`medal_silver_min`: both-or-neither, and gold **>** silver.
- `MeetUpdate` **does include `district_id`** — meets and gymnasts are the two exceptions to the not-updatable-parent-FK rule, so **the district select stays ENABLED on edit**. Do not apply `disabled={!!initial}` here.
- `MeetUpdate` also includes `status`, but this form **must omit it**. Status changes belong to the meet-shell controls that enforce `ALLOWED_STATUS_TRANSITIONS` and the `completed` confirmation. Create relies on the server's `draft` default.
- Cross-field medal validation is safe client-side because the form holds both values in state even when only one is dirty. The PATCH still sends only dirty fields; the router re-checks against stored values via `_validate_partial_medal_cutoffs`.

**Row restructure:** `MeetListPage.tsx:26-39` currently wraps the entire row in one
`<Link>`. A `<button>` cannot be nested inside an `<a>` (invalid HTML, and the click
propagates into navigation). The `<Link>` must be narrowed to cover only the
name/details region, with Edit and Delete as siblings in a trailing actions area.
**Clicking the meet text must still navigate** — that's the primary meet-day action.

- [ ] **Step 1: Fix the three existing tests that render `/`**

In `frontend/test/App.test.tsx`, add the districts handler:

```tsx
test("renders the nav shell", async () => {
  server.use(http.get(api("/meets/"), () => HttpResponse.json([])));
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  renderApp("/");
  expect(await screen.findByText("Rhythmiq")).toBeInTheDocument();
});
```

In `frontend/test/features/meets/MeetListPage.test.tsx`, add
`server.use(http.get(api("/districts/"), () => HttpResponse.json([])));` to **both**
existing tests ("lists meets with status badges" and "shows the API error detail on
failure"), immediately after their existing `/meets/` handler.

Leave the assertions alone — both use `findByText`, which survives the row restructure.

- [ ] **Step 2: Write the failing tests**

Append to `frontend/test/features/meets/MeetListPage.test.tsx`. The file already imports
`screen`, `http`, `HttpResponse`, `makeMeet`, `api`, `server`, `renderApp` — add
`waitFor`, `userEvent` and `makeDistrict` to those imports rather than duplicating them:

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeDistrict, makeMeet } from "../../fixtures";
import { api, server } from "../../msw/server";
import { renderApp } from "../../utils";

function seedDistricts() {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([makeDistrict({ id: 1, name: "Western Cape", abbreviation: "WC" })]),
    ),
  );
}

test("meet name still navigates into the meet", async () => {
  seedDistricts();
  server.use(
    http.get(api("/meets/"), () => HttpResponse.json([makeMeet({ id: 4, name: "Spring Open" })])),
  );
  server.use(http.get(api("/meets/4"), () => HttpResponse.json(makeMeet({ id: 4, name: "Spring Open" }))));
  server.use(http.get(api("/meet-entries/"), () => HttpResponse.json([])));
  renderApp("/");
  await userEvent.click(await screen.findByRole("link", { name: /Spring Open/ }));
  expect(await screen.findByRole("heading", { name: /Spring Open/ })).toBeInTheDocument();
});

test("creates a meet without sending status", async () => {
  seedDistricts();
  server.use(http.get(api("/meets/"), () => HttpResponse.json([])));
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/meets/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeMeet(), { status: 201 });
    }),
  );
  renderApp("/");
  await userEvent.click(await screen.findByRole("button", { name: "New meet" }));
  await userEvent.type(screen.getByLabelText("Name"), "Spring Open");
  await userEvent.type(screen.getByLabelText("Location"), "Cape Town");
  await userEvent.type(screen.getByLabelText("Start date"), "2026-09-01");
  await userEvent.type(screen.getByLabelText("End date"), "2026-09-02");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toEqual({
      name: "Spring Open",
      location: "Cape Town",
      start_date: "2026-09-01",
      end_date: "2026-09-02",
      district_id: null,
      medal_gold_min: null,
      medal_silver_min: null,
    }),
  );
  expect(posted!).not.toHaveProperty("status");
});

test("blocks an end date before the start date", async () => {
  seedDistricts();
  server.use(http.get(api("/meets/"), () => HttpResponse.json([])));
  let called = false;
  server.use(
    http.post(api("/meets/"), () => {
      called = true;
      return HttpResponse.json(makeMeet(), { status: 201 });
    }),
  );
  renderApp("/");
  await userEvent.click(await screen.findByRole("button", { name: "New meet" }));
  await userEvent.type(screen.getByLabelText("Name"), "Spring Open");
  await userEvent.type(screen.getByLabelText("Location"), "Cape Town");
  await userEvent.type(screen.getByLabelText("Start date"), "2026-09-05");
  await userEvent.type(screen.getByLabelText("End date"), "2026-09-01");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("End date must be on or after the start date")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("blocks a gold minimum that is not above the silver minimum", async () => {
  seedDistricts();
  server.use(http.get(api("/meets/"), () => HttpResponse.json([])));
  let called = false;
  server.use(
    http.post(api("/meets/"), () => {
      called = true;
      return HttpResponse.json(makeMeet(), { status: 201 });
    }),
  );
  renderApp("/");
  await userEvent.click(await screen.findByRole("button", { name: "New meet" }));
  await userEvent.type(screen.getByLabelText("Name"), "Spring Open");
  await userEvent.type(screen.getByLabelText("Location"), "Cape Town");
  await userEvent.type(screen.getByLabelText("Start date"), "2026-09-01");
  await userEvent.type(screen.getByLabelText("End date"), "2026-09-02");
  await userEvent.type(screen.getByLabelText("Gold minimum"), "8");
  await userEvent.type(screen.getByLabelText("Silver minimum"), "9");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Gold minimum must be above silver")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("blocks setting only one medal minimum", async () => {
  seedDistricts();
  server.use(http.get(api("/meets/"), () => HttpResponse.json([])));
  let called = false;
  server.use(
    http.post(api("/meets/"), () => {
      called = true;
      return HttpResponse.json(makeMeet(), { status: 201 });
    }),
  );
  renderApp("/");
  await userEvent.click(await screen.findByRole("button", { name: "New meet" }));
  await userEvent.type(screen.getByLabelText("Name"), "Spring Open");
  await userEvent.type(screen.getByLabelText("Location"), "Cape Town");
  await userEvent.type(screen.getByLabelText("Start date"), "2026-09-01");
  await userEvent.type(screen.getByLabelText("End date"), "2026-09-02");
  await userEvent.type(screen.getByLabelText("Gold minimum"), "9");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Set both medal minimums or neither")).toBeInTheDocument();
  expect(called).toBe(false);
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `npm test -- --run test/features/meets/MeetListPage.test.tsx`
Expected: the 2 pre-existing tests PASS; the 5 new ones FAIL — there is no "New meet"
button yet.

- [ ] **Step 4: Write `MeetForm.tsx`**

Create `frontend/src/features/meets/MeetForm.tsx`:

```tsx
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
```

- [ ] **Step 5: Rewrite `MeetListPage.tsx`**

Replace the whole file. Note the row restructure: the `<Link>` no longer wraps the
actions.

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { apiDetail, client } from "../../api/client";
import type { DistrictRead, MeetRead } from "../../api/types";
import { ErrorBanner } from "../../components/ErrorBanner";
import { labelize } from "../../lib/domain";
import { FormDialog } from "../admin/components/FormDialog";
import { useResourceDelete } from "../admin/hooks/useResourceDelete";
import { MeetForm, type MeetBody } from "./MeetForm";

export function MeetListPage() {
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<{ row: MeetRead | null } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const meetsQuery = useQuery({
    queryKey: ["meets"],
    queryFn: async () => {
      const { data, error } = await client.GET("/meets/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const districtsQuery = useQuery({
    queryKey: ["districts"],
    queryFn: async () => {
      const { data, error } = await client.GET("/districts/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });
  const districts: DistrictRead[] = districtsQuery.data ?? [];

  const saveMutation = useMutation({
    mutationFn: async (body: MeetBody) => {
      const editingRow = dialog?.row ?? null;
      if (editingRow) {
        const { data, error } = await client.PATCH("/meets/{meet_id}", {
          params: { path: { meet_id: editingRow.id } },
          body,
        });
        if (error) throw new Error(apiDetail(error));
        return data;
      }
      const { data, error } = await client.POST("/meets/", {
        body: body as {
          name: string;
          location: string;
          start_date: string;
          end_date: string;
        },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      clearDeleteError();
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["meets"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });

  const {
    confirmDelete,
    error: deleteError,
    clearError: clearDeleteError,
  } = useResourceDelete<MeetRead>({
    queryKey: ["meets"],
    // Meet deletes cascade to entries and routines, but are rejected (409) while
    // in_progress or completed — a completed meet is the historical record.
    describe: (m) =>
      `Delete "${m.name}"? This also deletes its entries and routines. Meets that are in progress or completed cannot be deleted.`,
    remove: async (m) => {
      const { error } = await client.DELETE("/meets/{meet_id}", {
        params: { path: { meet_id: m.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
  });

  if (meetsQuery.isPending) return <p>Loading…</p>;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Meets</h1>
        <button
          type="button"
          onClick={() => {
            setFormError(null);
            setDialog({ row: null });
          }}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New meet
        </button>
      </div>
      <ErrorBanner
        message={
          meetsQuery.error?.message ??
          districtsQuery.error?.message ??
          deleteError ??
          null
        }
      />
      <ul className="divide-y divide-gray-200 rounded border border-gray-200 bg-white">
        {(meetsQuery.data ?? []).map((meet) => (
          // The Link covers only the meet text: a <button> cannot be nested inside an
          // <a>, and the click would propagate into navigation.
          <li key={meet.id} className="flex items-center justify-between px-4 py-3">
            <Link to={`/meets/${meet.id}`} className="flex-1 hover:underline">
              <span>
                {meet.name}{" "}
                <span className="text-sm text-gray-500">
                  {meet.location} · {meet.start_date}
                </span>
              </span>
            </Link>
            <span className="ml-3 rounded bg-gray-100 px-2 py-1 text-xs">
              {labelize(meet.status)}
            </span>
            <button
              type="button"
              aria-label={`Edit ${meet.name}`}
              onClick={() => {
                setFormError(null);
                setDialog({ row: meet });
              }}
              className="ml-3 rounded border border-gray-300 px-2 py-0.5 text-xs"
            >
              Edit
            </button>
            <button
              type="button"
              aria-label={`Delete ${meet.name}`}
              onClick={() => confirmDelete(meet)}
              className="ml-2 rounded border border-gray-300 px-2 py-0.5 text-xs text-red-700"
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
      <FormDialog
        open={dialog !== null}
        title={dialog?.row ? "Edit meet" : "New meet"}
        onClose={() => setDialog(null)}
      >
        {dialog && (
          <MeetForm
            key={dialog.row?.id ?? "new"}
            initial={dialog.row}
            districts={districts}
            pending={saveMutation.isPending}
            error={formError}
            onSubmit={(body) => saveMutation.mutate(body)}
            onCancel={() => setDialog(null)}
          />
        )}
      </FormDialog>
    </div>
  );
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `npm test -- --run test/features/meets/MeetListPage.test.tsx`
Expected: PASS, 7 tests (2 pre-existing + 5 new).

- [ ] **Step 7: Run the full suite and build**

Run: `npm test -- --run && npm run build`
Expected: all pass (184), clean build.

If anything outside these files fails, it is almost certainly another test rendering `/`
without a `/districts/` handler — add one there too rather than changing `MeetListPage`.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/features/meets frontend/test/features/meets frontend/test/App.test.tsx
git commit -m "feat: create, edit and delete meets from the meet list"
```

---

### Task 6: Edit meet details from the meet shell

**Files:**
- Modify: `frontend/src/features/meets/MeetShell.tsx`
- Test: `frontend/test/features/meets/MeetShell.test.tsx` (append)

**Interfaces:**
- Consumes: `MeetForm`, `type MeetBody` from Task 5 — unchanged, no new props.
- Produces: nothing new.

Task 5 already delivered create, edit and delete on `/`. This task adds the second entry
point: an `[Edit details]` button in the meet header opening the same `MeetForm`. Status
controls stay exactly as they are — this button must not touch them.

- [ ] **Step 1: Write the failing tests**

Append to `frontend/test/features/meets/MeetShell.test.tsx` (keep existing imports and
whatever handler helper the file already uses for `/meets/{id}`):

```tsx
test("edits meet details from the header without sending status", async () => {
  server.use(
    http.get(api("/meets/4"), () =>
      HttpResponse.json(makeMeet({ id: 4, name: "Spring Open", status: "scheduled" })),
    ),
  );
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  server.use(http.get(api("/meet-entries/"), () => HttpResponse.json([])));
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/meets/4"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeMeet({ id: 4, name: "Spring Classic" }));
    }),
  );
  renderApp("/meets/4/scoring");
  await userEvent.click(await screen.findByRole("button", { name: "Edit details" }));
  const name = await screen.findByLabelText("Name");
  await userEvent.clear(name);
  await userEvent.type(name, "Spring Classic");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ name: "Spring Classic" }));
});

test("the details dialog offers no status control", async () => {
  server.use(
    http.get(api("/meets/4"), () =>
      HttpResponse.json(makeMeet({ id: 4, name: "Spring Open", status: "scheduled" })),
    ),
  );
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  server.use(http.get(api("/meet-entries/"), () => HttpResponse.json([])));
  renderApp("/meets/4/scoring");
  await userEvent.click(await screen.findByRole("button", { name: "Edit details" }));
  expect(await screen.findByLabelText("Name")).toBeInTheDocument();
  expect(screen.queryByLabelText("Status")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- --run test/features/meets/MeetShell.test.tsx`
Expected: FAIL — no "Edit details" button.

- [ ] **Step 3: Add the button and dialog to `MeetShell.tsx`**

**Verified facts about the current `MeetShell.tsx` — do not re-derive:**
`useMutation`, `useQuery`, `useQueryClient`, `useState` are **already imported** (line 1-2).
`const queryClient = useQueryClient()` is **already in scope** (line 18). The meet query
key is **`["meet", meetId]`** (line 22). After the `isPending`/`error` early returns
(lines 49-50), `meet` is guaranteed non-null, so no `meet &&` guard is needed. The status
buttons live in a `<div className="flex gap-2">` at lines 76-87.

Add only these imports:

```tsx
import type { DistrictRead } from "../../api/types";
import { FormDialog } from "../admin/components/FormDialog";
import { MeetForm, type MeetBody } from "./MeetForm";
```

Add state and the districts query alongside the existing meet query:

```tsx
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [detailsError, setDetailsError] = useState<string | null>(null);

  const districtsQuery = useQuery({
    queryKey: ["districts"],
    queryFn: async () => {
      const { data, error } = await client.GET("/districts/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });
  const districts: DistrictRead[] = districtsQuery.data ?? [];
```

Add a save mutation beside the existing `statusMutation` (line 32), reusing the
`queryClient` already in scope:

```tsx
  const detailsMutation = useMutation({
    mutationFn: async (body: MeetBody) => {
      const { data, error } = await client.PATCH("/meets/{meet_id}", {
        params: { path: { meet_id: Number(meetId) } },
        body,
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setDetailsError(null);
      setDetailsOpen(false);
      queryClient.invalidateQueries({ queryKey: ["meet", meetId] });
      queryClient.invalidateQueries({ queryKey: ["meets"] });
    },
    onError: (e: Error) => setDetailsError(e.message),
  });
```

Add the button inside the header's `<div className="flex gap-2">` (line 76), **after** the
status-transition buttons so status controls stay leftmost and unchanged:

```tsx
        <button
          type="button"
          onClick={() => {
            setDetailsError(null);
            setDetailsOpen(true);
          }}
          className="rounded border border-gray-300 px-3 py-1 text-sm"
        >
          Edit details
        </button>
```

And the dialog, immediately after `<Outlet context={meet} />` (line 107), still inside the
outer `<div>`. No `meet &&` guard — the early returns above already narrowed it:

```tsx
      <FormDialog
        open={detailsOpen}
        title="Edit meet"
        onClose={() => setDetailsOpen(false)}
      >
        {detailsOpen && (
          <MeetForm
            initial={meet}
            districts={districts}
            pending={detailsMutation.isPending}
            error={detailsError}
            onSubmit={(body) => detailsMutation.mutate(body)}
            onCancel={() => setDetailsOpen(false)}
          />
        )}
      </FormDialog>
```

**Watch for the same MSW breakage as Task 5:** `MeetShell` now fetches `/districts/`, so
every existing test rendering a `/meets/:id/*` route needs a `/districts/` handler.
Check `test/features/meets/MeetShell.test.tsx` and the scoring/entries/standings test
files, and add handlers where missing.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test -- --run test/features/meets/MeetShell.test.tsx`
Expected: PASS, including the two new tests.

- [ ] **Step 5: Run the full suite and build**

Run: `npm test -- --run && npm run build`
Expected: all pass (186), clean build.

- [ ] **Step 6: Manual verification through the real stack**

Start the backend (`make dev` from the repo root) and `npm run dev` from `frontend/`,
then confirm in a browser at `http://127.0.0.1:5173`:

1. `/admin/judges` — create a judge, edit their brevet, try deleting one who has scored
   (expect a 409 message, not a crash).
2. `/admin/routine-profiles` — create a gymnast-owned profile and a group-owned one;
   confirm the edit dialog shows the read-only identity line.
3. `/admin/gymnasts` — confirm the group select is disabled until a club is chosen and
   only lists that club's groups.
4. `/` — create a meet, edit it, confirm the meet name still navigates into the meet.
5. Open a meet → `[Edit details]` → rename it → confirm the header updates and the
   status control is untouched.

If browser automation is unavailable, substitute live-backend smoke tests through the
Vite proxy and say explicitly in the report which checks were not run in a real browser.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/meets frontend/test/features/meets
git commit -m "feat: edit meet details from the meet shell header"
```

---

## Plan self-review notes

**Spec coverage:** §1 Judges → Task 1. §2 Routine profiles → Tasks 3 (list+create) and 4
(edit). §3 Meet CRUD → Tasks 5 (form, create, list restructure, delete) and 6 (shell
entry point). §4 Gymnast group fix → Task 2. Sidebar → Tasks 1 and 3. Testing
conventions → Global Constraints plus the load-bearing verification steps in Tasks 1 and
2. Non-goals → Global Constraints.

**Test-count arithmetic** (baseline 153 across 24 files): T1 +10 → 163, T2 +3 → 166,
T3 +10 → 176, T4 +3 → 179, T5 +5 → 184, T6 +2 → 186. The 2 tests already in
`MeetListPage.test.tsx` are part of the 153 baseline and are fixed, not added, in T5.

**Findings from the self-review, already folded into the tasks above:**

1. **The MSW unhandled-request trap (highest risk in this plan).** `test/setup.ts` runs
   `server.listen({ onUnhandledRequest: "error" })`. Both `MeetListPage` (T5) and
   `MeetShell` (T6) gain a `GET /districts/` query, so *every existing test rendering
   those routes fails* until it gets a districts handler — three known cases in T5
   (`App.test.tsx:7` plus both tests in `MeetListPage.test.tsx`), and an unbounded set in
   T6. This is a mechanical fix; the wrong reaction is to drop the districts query.
2. `MeetListPage.test.tsx` and `MeetShell.test.tsx` **already exist** — T5 and T6 append
   to them rather than creating them.
3. T6's references to `MeetShell` internals are now stated as verified facts (query key
   `["meet", meetId]`, `queryClient` already in scope, `meet` non-null after the early
   returns) rather than "read the file and adapt", which was a placeholder in disguise.

**Deliberate deviations from Phase 2 convention, each documented in code comments so a
later reviewer doesn't revert them:**
1. The meet district select stays **enabled** on edit (`MeetUpdate` really does accept
   `district_id`).
2. Routine profile edit uses a **read-only context line**, not disabled controls.
3. Meets do **not** use `ResourceTable`.

**Known open risk:** T5 changes the DOM shape of `/`'s rows. The two existing tests use
`findByText` and survive, but any future assertion about a whole-row link would not.
