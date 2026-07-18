# Admin Console (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an admin console to the Rhythmiq frontend for managing the competitor chain — districts, clubs, coaches, groups and gymnasts — replacing `/docs` as the way reference data gets entered.

**Architecture:** Three stages. Stage A hand-writes two pilot screens at opposite ends of the complexity range (District: two text fields, no FK; Gymnast: two optional FKs, nullable date, nullable country code, club filter). Stage B extracts the shared table/dialog/list/FK-picker layer from the duplication those two pilots actually exhibit. Stage C rolls the remaining three resources out on that layer. Forms stay hand-written per resource throughout — only the shell around them is shared.

**Tech Stack:** React 19, TypeScript (strict), Vite, TanStack Query, React Router, React Hook Form + Zod, Tailwind, openapi-fetch. Tests: Vitest + Testing Library + MSW.

**Spec:** `docs/superpowers/specs/2026-07-18-admin-console-design.md`

## Global Constraints

- All frontend commands run from `frontend/`. Tests: `npm test -- --run`. Typecheck+build: `npm run build`. Lint/format is `ruff` for backend only; frontend has no linter step.
- **No backend changes.** Every type this plan needs already exists in the committed `src/api/schema.d.ts`. Do not run `make types`.
- Server state goes through TanStack Query only. No `useEffect` fetching.
- Form state belongs to React Hook Form and is never clobbered by background refetches.
- Zod schemas mirror **DB constraints only** — field length, required vs nullable. Uniqueness, RESTRICT and abbreviation-uppercasing stay server-side and surface as the API's `detail` string.
- Updates (`PATCH`) send **only dirty fields**, matching the backend's `model_dump(exclude_unset=True)` contract.
- No polling in admin. `refetchInterval` stays a scoring/standings concern.
- No pagination — list endpoints return full lists; search and sort are client-side.
- Every commit subject starts with `feat:`, `fix:`, `chore:`, `docs:`, `test:` or `refactor:`.
- Error text shown to the user for a failed request is always the API's `detail` via `apiDetail(error)` — never a hand-written substitute.

## Deviation from the spec (deliberate, already decided)

The spec lists `DeleteConfirm` as an extracted **component**. It is implemented instead as a **hook**, `useResourceDelete`, because Phase 1 already standardizes on `window.confirm` for destructive actions (see `EntriesPage.tsx` and its tests, which spy on `window.confirm`). A bespoke confirm component would make admin deletes behave differently from entry deletes for no user-visible gain. Everything else in the spec's extraction table is built as written.

## File Structure

**Created:**

| File | Responsibility |
|---|---|
| `src/features/admin/AdminShell.tsx` | Admin sidebar + `<Outlet />`; sibling of `MeetShell` |
| `src/features/admin/districts/DistrictsPage.tsx` | Districts list, dialog wiring, delete |
| `src/features/admin/districts/DistrictForm.tsx` | District create/edit form body |
| `src/features/admin/gymnasts/GymnastsPage.tsx` | Gymnasts list, search, club filter, dialog wiring, delete |
| `src/features/admin/gymnasts/GymnastForm.tsx` | Gymnast create/edit form body |
| `src/features/admin/clubs/ClubsPage.tsx` + `ClubForm.tsx` | Clubs screen |
| `src/features/admin/coaches/CoachesPage.tsx` + `CoachForm.tsx` | Coaches screen |
| `src/features/admin/groups/GroupsPage.tsx` + `GroupForm.tsx` | Groups screen |
| `src/features/admin/components/ResourceTable.tsx` | Column-driven table + Edit/Delete action cells |
| `src/features/admin/components/FormDialog.tsx` | Modal shell: title, error banner, Cancel/Submit, pending state |
| `src/features/admin/components/FkSelect.tsx` | FK `<select>` with optional `— none —` |
| `src/features/admin/hooks/useResourceList.ts` | List query + client-side search filter |
| `src/features/admin/hooks/useResourceDelete.ts` | confirm → DELETE → invalidate → surface 409 `detail` |

**Modified:**

| File | Change |
|---|---|
| `src/api/client.ts:23` | `apiDetail` formats 422 arrays readably |
| `src/api/types.ts` | export `DistrictRead`, `ClubRead`, `CoachRead` |
| `src/App.tsx` | `/admin` routes |
| `src/components/Layout.tsx` | Meets / Admin nav links |
| `test/fixtures.ts` | `makeDistrict`, `makeClub`, `makeCoach` |
| `test/api/client.test.ts:16-22` | update the 422 expectation |

**Test files** mirror `src/` under `test/features/admin/…`, one per page plus one per extracted unit.

---

## Stage A — Pilots

### Task 1: `apiDetail` formats 422 validation arrays

`apiDetail` currently renders FastAPI's 422 body as raw JSON. Five admin forms will hit it.

**Files:**
- Modify: `frontend/src/api/client.ts:22-30`
- Test: `frontend/test/api/client.test.ts:16-22` (replace the existing test)

**Interfaces:**
- Consumes: nothing
- Produces: `apiDetail(error: unknown): string` — unchanged signature, changed 422 behaviour

- [ ] **Step 1: Replace the existing 422 test**

Replace lines 16-22 of `frontend/test/api/client.test.ts` with:

```ts
test("apiDetail extracts string detail", () => {
  expect(apiDetail({ detail: "Meet with id 9 not found" })).toBe(
    "Meet with id 9 not found",
  );
  expect(apiDetail(undefined)).toBe("Request failed");
});

test("apiDetail formats 422 validation arrays as field: message lines", () => {
  const body = {
    detail: [
      { loc: ["body", "abbreviation"], msg: "String should have at most 10 characters" },
      { loc: ["body", "name"], msg: "Field required" },
    ],
  };
  expect(apiDetail(body)).toBe(
    "abbreviation: String should have at most 10 characters\nname: Field required",
  );
});

test("apiDetail falls back to JSON for unrecognised array shapes", () => {
  expect(apiDetail({ detail: [{ oops: 1 }] })).toBe('[{"oops":1}]');
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- --run test/api/client.test.ts`
Expected: FAIL — the 422 test gets the JSON string instead of `field: message` lines.

- [ ] **Step 3: Implement**

Replace `apiDetail` in `frontend/src/api/client.ts` with:

```ts
/** One entry of FastAPI's 422 body: {"loc": ["body", "name"], "msg": "Field required"}. */
function formatValidationItem(item: unknown): string | null {
  if (!item || typeof item !== "object") return null;
  const { loc, msg } = item as { loc?: unknown; msg?: unknown };
  if (typeof msg !== "string") return null;
  const field = Array.isArray(loc) ? loc[loc.length - 1] : undefined;
  return typeof field === "string" || typeof field === "number"
    ? `${field}: ${msg}`
    : msg;
}

/** Extract FastAPI's `detail` from an error body (409/404 are strings, 422 is an array). */
export function apiDetail(error: unknown): string {
  if (error && typeof error === "object" && "detail" in error) {
    const d = (error as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      const lines = d.map(formatValidationItem);
      if (lines.every((line): line is string => line !== null)) {
        return lines.join("\n");
      }
    }
    return JSON.stringify(d);
  }
  return "Request failed";
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test -- --run test/api/client.test.ts`
Expected: PASS, 4 tests.

- [ ] **Step 5: Run the full suite — this touches every existing error path**

Run: `npm test -- --run`
Expected: PASS, all existing tests still green.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.ts frontend/test/api/client.test.ts
git commit -m "fix: format 422 validation errors as field: message lines"
```

---

### Task 2: Admin shell, routes and districts list

Read-only first: the shell plus a districts table. Create/edit/delete come in Tasks 3-5.

**Files:**
- Create: `frontend/src/features/admin/AdminShell.tsx`
- Create: `frontend/src/features/admin/districts/DistrictsPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/test/fixtures.ts`
- Test: `frontend/test/features/admin/AdminShell.test.tsx`
- Test: `frontend/test/features/admin/districts/DistrictsPage.test.tsx`

**Interfaces:**
- Consumes: `client`, `apiDetail` from `src/api/client`; `ErrorBanner`
- Produces: `AdminShell` (default-less named export), `DistrictsPage`, `makeDistrict(overrides?: Partial<DistrictRead>): DistrictRead`, type `DistrictRead`

- [ ] **Step 1: Write the failing tests**

Create `frontend/test/features/admin/AdminShell.test.tsx`:

```tsx
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { api, server } from "../../msw/server";
import { renderApp } from "../../utils";

test("/admin redirects to districts and shows the resource sidebar", async () => {
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  renderApp("/admin");
  expect(await screen.findByRole("heading", { name: "Districts" })).toBeInTheDocument();
  for (const name of ["Districts", "Clubs", "Coaches", "Groups", "Gymnasts"]) {
    expect(screen.getByRole("link", { name })).toBeInTheDocument();
  }
});

test("the top nav links to meets and admin", async () => {
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  renderApp("/admin/districts");
  expect(await screen.findByRole("link", { name: "Meets" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Admin" })).toBeInTheDocument();
});
```

Create `frontend/test/features/admin/districts/DistrictsPage.test.tsx`:

```tsx
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { makeDistrict } from "../../../fixtures";
import { api, server } from "../../../msw/server";
import { renderApp } from "../../../utils";

test("lists districts", async () => {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([
        makeDistrict({ id: 1, name: "Western Cape", abbreviation: "WC" }),
        makeDistrict({ id: 2, name: "Gauteng", abbreviation: "GAU" }),
      ]),
    ),
  );
  renderApp("/admin/districts");
  expect(await screen.findByText("Western Cape")).toBeInTheDocument();
  expect(screen.getByText("GAU")).toBeInTheDocument();
});

test("shows an empty message when there are no districts", async () => {
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  renderApp("/admin/districts");
  expect(await screen.findByText("No districts yet.")).toBeInTheDocument();
});

test("surfaces a list error", async () => {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json({ detail: "Database unavailable" }, { status: 500 }),
    ),
  );
  renderApp("/admin/districts");
  expect(await screen.findByRole("alert")).toHaveTextContent("Database unavailable");
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm test -- --run test/features/admin`
Expected: FAIL — `makeDistrict` is not exported; no `/admin` route.

- [ ] **Step 3: Add the type export and fixture**

Append to `frontend/src/api/types.ts`:

```ts
export type DistrictRead = components["schemas"]["DistrictRead"];
```

Append to `frontend/test/fixtures.ts` (and add `DistrictRead` to the existing `import type { … }` block at the top):

```ts
export function makeDistrict(overrides: Partial<DistrictRead> = {}): DistrictRead {
  return { id: id(), name: "Western Cape", abbreviation: "WC", ...overrides };
}
```

- [ ] **Step 4: Write `AdminShell`**

Create `frontend/src/features/admin/AdminShell.tsx`:

```tsx
import { NavLink, Outlet } from "react-router-dom";

/** Resources in dependency order — a district must exist before a club, and so on. */
const RESOURCES = [
  { path: "districts", label: "Districts" },
  { path: "clubs", label: "Clubs" },
  { path: "coaches", label: "Coaches" },
  { path: "groups", label: "Groups" },
  { path: "gymnasts", label: "Gymnasts" },
];

export function AdminShell() {
  return (
    <div className="flex gap-6">
      <nav className="w-44 shrink-0">
        <ul className="space-y-1">
          {RESOURCES.map((r) => (
            <li key={r.path}>
              <NavLink
                to={r.path}
                className={({ isActive }) =>
                  `block rounded px-3 py-1 text-sm ${
                    isActive ? "bg-blue-600 font-semibold text-white" : "hover:bg-gray-200"
                  }`
                }
              >
                {r.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <section className="min-w-0 flex-1">
        <Outlet />
      </section>
    </div>
  );
}
```

- [ ] **Step 5: Write `DistrictsPage` (read-only)**

Create `frontend/src/features/admin/districts/DistrictsPage.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { apiDetail, client } from "../../../api/client";
import type { DistrictRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";

export function DistrictsPage() {
  const districtsQuery = useQuery({
    queryKey: ["districts"],
    queryFn: async (): Promise<DistrictRead[]> => {
      const { data, error } = await client.GET("/districts/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  return (
    <div>
      <h1 className="mb-3 text-xl font-bold">Districts</h1>
      <ErrorBanner message={districtsQuery.error ? districtsQuery.error.message : null} />
      {districtsQuery.data?.length === 0 && (
        <p className="text-sm text-gray-500">No districts yet.</p>
      )}
      {districtsQuery.data && districtsQuery.data.length > 0 && (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-300 text-left">
              <th className="py-1">Name</th>
              <th className="py-1">Abbreviation</th>
            </tr>
          </thead>
          <tbody>
            {districtsQuery.data.map((d) => (
              <tr key={d.id} className="border-b border-gray-200">
                <td className="py-1">{d.name}</td>
                <td className="py-1">{d.abbreviation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Wire the routes**

In `frontend/src/App.tsx`, add the imports and the `/admin` branch inside the existing `<Route element={<Layout />}>`:

```tsx
import { AdminShell } from "./features/admin/AdminShell";
import { DistrictsPage } from "./features/admin/districts/DistrictsPage";
```

```tsx
        <Route path="/admin" element={<AdminShell />}>
          <Route index element={<Navigate to="districts" replace />} />
          <Route path="districts" element={<DistrictsPage />} />
        </Route>
```

- [ ] **Step 7: Add the nav links**

Replace the `<nav>` block in `frontend/src/components/Layout.tsx`:

```tsx
      <nav className="flex items-center gap-6 border-b border-gray-200 bg-white px-6 py-3">
        <Link to="/" className="text-lg font-bold">
          Rhythmiq
        </Link>
        <Link to="/" className="text-sm hover:underline">
          Meets
        </Link>
        <Link to="/admin" className="text-sm hover:underline">
          Admin
        </Link>
      </nav>
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `npm test -- --run test/features/admin`
Expected: PASS, 5 tests.

- [ ] **Step 9: Typecheck and full suite**

Run: `npm run build && npm test -- --run`
Expected: build succeeds; all tests pass.

- [ ] **Step 10: Commit**

```bash
git add frontend/src frontend/test
git commit -m "feat: admin shell with districts list"
```

---

### Task 3: District create

**Files:**
- Create: `frontend/src/features/admin/districts/DistrictForm.tsx`
- Modify: `frontend/src/features/admin/districts/DistrictsPage.tsx`
- Test: `frontend/test/features/admin/districts/DistrictsPage.test.tsx` (append)

**Interfaces:**
- Consumes: `DistrictRead`, `client`, `apiDetail`, `ErrorBanner`
- Produces: `DistrictForm({ initial, onSubmit, onCancel, pending, error })` where `initial: DistrictRead | null` (null = create) and `onSubmit: (body: { name?: string; abbreviation?: string }) => void`

- [ ] **Step 1: Write the failing tests**

Append to `frontend/test/features/admin/districts/DistrictsPage.test.tsx`:

```tsx
import { waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

test("creates a district", async () => {
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/districts/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeDistrict(), { status: 201 });
    }),
  );
  renderApp("/admin/districts");
  await userEvent.click(await screen.findByRole("button", { name: "New district" }));
  await userEvent.type(screen.getByLabelText("Name"), "Free State");
  await userEvent.type(screen.getByLabelText("Abbreviation"), "FS");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toEqual({ name: "Free State", abbreviation: "FS" }),
  );
});

test("blocks an over-long abbreviation before sending", async () => {
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  let called = false;
  server.use(
    http.post(api("/districts/"), () => {
      called = true;
      return HttpResponse.json(makeDistrict(), { status: 201 });
    }),
  );
  renderApp("/admin/districts");
  await userEvent.click(await screen.findByRole("button", { name: "New district" }));
  await userEvent.type(screen.getByLabelText("Name"), "Free State");
  await userEvent.type(screen.getByLabelText("Abbreviation"), "TOOMANYCHARS");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("At most 10 characters")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("keeps the dialog open and shows the detail on a 409", async () => {
  server.use(http.get(api("/districts/"), () => HttpResponse.json([])));
  server.use(
    http.post(api("/districts/"), () =>
      HttpResponse.json({ detail: "District abbreviation already exists" }, { status: 409 }),
    ),
  );
  renderApp("/admin/districts");
  await userEvent.click(await screen.findByRole("button", { name: "New district" }));
  await userEvent.type(screen.getByLabelText("Name"), "Gauteng");
  await userEvent.type(screen.getByLabelText("Abbreviation"), "GAU");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("already exists");
  expect(screen.getByLabelText("Name")).toHaveValue("Gauteng");
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm test -- --run test/features/admin/districts`
Expected: FAIL — no "New district" button.

- [ ] **Step 3: Write `DistrictForm`**

Create `frontend/src/features/admin/districts/DistrictForm.tsx`:

```tsx
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { DistrictRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";

const districtSchema = z.object({
  name: z.string().trim().min(1, "Name is required"),
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
```

- [ ] **Step 4: Wire create into `DistrictsPage`**

Rewrite `frontend/src/features/admin/districts/DistrictsPage.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiDetail, client } from "../../../api/client";
import type { DistrictRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { DistrictForm, type DistrictBody } from "./DistrictForm";

export function DistrictsPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const districtsQuery = useQuery({
    queryKey: ["districts"],
    queryFn: async (): Promise<DistrictRead[]> => {
      const { data, error } = await client.GET("/districts/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const saveMutation = useMutation({
    mutationFn: async (body: DistrictBody) => {
      const { data, error } = await client.POST("/districts/", {
        body: body as { name: string; abbreviation: string },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      setDialogOpen(false);
      queryClient.invalidateQueries({ queryKey: ["districts"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });

  const openCreate = () => {
    setFormError(null);
    setDialogOpen(true);
  };

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-xl font-bold">Districts</h1>
        <button
          type="button"
          onClick={openCreate}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New district
        </button>
      </div>
      <ErrorBanner message={districtsQuery.error ? districtsQuery.error.message : null} />
      {districtsQuery.data?.length === 0 && (
        <p className="text-sm text-gray-500">No districts yet.</p>
      )}
      {districtsQuery.data && districtsQuery.data.length > 0 && (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-300 text-left">
              <th className="py-1">Name</th>
              <th className="py-1">Abbreviation</th>
            </tr>
          </thead>
          <tbody>
            {districtsQuery.data.map((d) => (
              <tr key={d.id} className="border-b border-gray-200">
                <td className="py-1">{d.name}</td>
                <td className="py-1">{d.abbreviation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {dialogOpen && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/30">
          <div className="w-96 rounded border border-gray-200 bg-white p-4 shadow-lg">
            <h2 className="mb-2 text-lg font-semibold">New district</h2>
            <DistrictForm
              initial={null}
              pending={saveMutation.isPending}
              error={formError}
              onSubmit={(body) => saveMutation.mutate(body)}
              onCancel={() => setDialogOpen(false)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `npm test -- --run test/features/admin/districts`
Expected: PASS, 6 tests.

- [ ] **Step 6: Commit**

```bash
git add frontend/src frontend/test
git commit -m "feat: create districts from the admin console"
```

---

### Task 4: District edit

**Files:**
- Modify: `frontend/src/features/admin/districts/DistrictsPage.tsx`
- Test: `frontend/test/features/admin/districts/DistrictsPage.test.tsx` (append)

**Interfaces:**
- Consumes: `DistrictForm` from Task 3 (its `initial` prop and dirty-field body-building are already written)
- Produces: nothing new

- [ ] **Step 1: Write the failing tests**

Append to `frontend/test/features/admin/districts/DistrictsPage.test.tsx`:

```tsx
test("edits a district, sending only the changed field", async () => {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([makeDistrict({ id: 4, name: "Gauteng", abbreviation: "GAU" })]),
    ),
  );
  let patched: Record<string, unknown> | null = null;
  let patchedId: string | undefined;
  server.use(
    http.patch(api("/districts/:districtId"), async ({ request, params }) => {
      patched = (await request.json()) as Record<string, unknown>;
      patchedId = params.districtId as string;
      return HttpResponse.json(makeDistrict({ id: 4 }));
    }),
  );
  renderApp("/admin/districts");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Gauteng" }));
  const name = screen.getByLabelText("Name");
  expect(name).toHaveValue("Gauteng");
  await userEvent.clear(name);
  await userEvent.type(name, "Gauteng North");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ name: "Gauteng North" }));
  expect(patchedId).toBe("4");
});

test("reopening the dialog for another row resets the fields", async () => {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([
        makeDistrict({ id: 1, name: "Western Cape", abbreviation: "WC" }),
        makeDistrict({ id: 2, name: "Gauteng", abbreviation: "GAU" }),
      ]),
    ),
  );
  renderApp("/admin/districts");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Western Cape" }));
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await userEvent.click(screen.getByRole("button", { name: "Edit Gauteng" }));
  expect(screen.getByLabelText("Name")).toHaveValue("Gauteng");
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm test -- --run test/features/admin/districts`
Expected: FAIL — no "Edit Gauteng" button.

- [ ] **Step 3: Add editing state, an Edit column and the PATCH branch**

In `DistrictsPage.tsx`, replace the `dialogOpen` state with an `editing` state and update the mutation, the table and the dialog:

```tsx
  // null = closed; { row: null } = create; { row } = edit
  const [dialog, setDialog] = useState<{ row: DistrictRead | null } | null>(null);
```

```tsx
  const saveMutation = useMutation({
    mutationFn: async (body: DistrictBody) => {
      const editingRow = dialog?.row ?? null;
      if (editingRow) {
        const { data, error } = await client.PATCH("/districts/{district_id}", {
          params: { path: { district_id: editingRow.id } },
          body,
        });
        if (error) throw new Error(apiDetail(error));
        return data;
      }
      const { data, error } = await client.POST("/districts/", {
        body: body as { name: string; abbreviation: string },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["districts"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });
```

Header button becomes `onClick={() => { setFormError(null); setDialog({ row: null }); }}`.

Add a third column to `<thead>`: `<th className="py-1" />`, and to each row:

```tsx
                <td className="py-1 text-right">
                  <button
                    type="button"
                    aria-label={`Edit ${d.name}`}
                    onClick={() => {
                      setFormError(null);
                      setDialog({ row: d });
                    }}
                    className="rounded border border-gray-300 px-2 py-0.5 text-xs"
                  >
                    Edit
                  </button>
                </td>
```

The dialog block becomes:

```tsx
      {dialog && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/30">
          <div className="w-96 rounded border border-gray-200 bg-white p-4 shadow-lg">
            <h2 className="mb-2 text-lg font-semibold">
              {dialog.row ? "Edit district" : "New district"}
            </h2>
            <DistrictForm
              key={dialog.row?.id ?? "new"}
              initial={dialog.row}
              pending={saveMutation.isPending}
              error={formError}
              onSubmit={(body) => saveMutation.mutate(body)}
              onCancel={() => setDialog(null)}
            />
          </div>
        </div>
      )}
```

The `key` is what makes the second test pass: it forces a fresh `DistrictForm` (and fresh RHF defaults) per row instead of reusing the previous row's state.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test -- --run test/features/admin/districts`
Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src frontend/test
git commit -m "feat: edit districts from the admin console"
```

---

### Task 5: District delete

**Files:**
- Modify: `frontend/src/features/admin/districts/DistrictsPage.tsx`
- Test: `frontend/test/features/admin/districts/DistrictsPage.test.tsx` (append)

**Interfaces:**
- Consumes: nothing new
- Produces: nothing new (the reusable hook is extracted in Task 10)

- [ ] **Step 1: Write the failing tests**

Append to `frontend/test/features/admin/districts/DistrictsPage.test.tsx`:

```tsx
test("deletes a district after confirmation", async () => {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([makeDistrict({ id: 4, name: "Gauteng" })]),
    ),
  );
  let deletedId: string | undefined;
  server.use(
    http.delete(api("/districts/:districtId"), ({ params }) => {
      deletedId = params.districtId as string;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/admin/districts");
  await userEvent.click(await screen.findByRole("button", { name: "Delete Gauteng" }));
  await waitFor(() => expect(deletedId).toBe("4"));
  expect(confirmSpy.mock.calls[0][0]).toContain("Gauteng");
  confirmSpy.mockRestore();
});

test("declining the confirm aborts the delete", async () => {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([makeDistrict({ id: 4, name: "Gauteng" })]),
    ),
  );
  let called = false;
  server.use(
    http.delete(api("/districts/:districtId"), () => {
      called = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
  renderApp("/admin/districts");
  await userEvent.click(await screen.findByRole("button", { name: "Delete Gauteng" }));
  expect(called).toBe(false);
  confirmSpy.mockRestore();
});

test("shows the API detail when a delete is blocked by dependents", async () => {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([makeDistrict({ id: 4, name: "Gauteng" })]),
    ),
  );
  server.use(
    http.delete(api("/districts/:districtId"), () =>
      HttpResponse.json(
        { detail: "Cannot delete district with existing clubs" },
        { status: 409 },
      ),
    ),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/admin/districts");
  await userEvent.click(await screen.findByRole("button", { name: "Delete Gauteng" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("existing clubs");
  confirmSpy.mockRestore();
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm test -- --run test/features/admin/districts`
Expected: FAIL — no "Delete Gauteng" button.

- [ ] **Step 3: Add the delete mutation and button**

In `DistrictsPage.tsx` add state and a mutation:

```tsx
  const [listError, setListError] = useState<string | null>(null);

  const deleteMutation = useMutation({
    mutationFn: async (row: DistrictRead) => {
      const { error } = await client.DELETE("/districts/{district_id}", {
        params: { path: { district_id: row.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
    onSuccess: () => {
      setListError(null);
      queryClient.invalidateQueries({ queryKey: ["districts"] });
    },
    onError: (e: Error) => setListError(e.message),
  });

  const confirmDelete = (row: DistrictRead) => {
    if (!window.confirm(`Delete district "${row.name}"?`)) return;
    deleteMutation.mutate(row);
  };
```

Show both errors above the table:

```tsx
      <ErrorBanner
        message={districtsQuery.error ? districtsQuery.error.message : listError}
      />
```

And add the button beside Edit in the action cell:

```tsx
                  <button
                    type="button"
                    aria-label={`Delete ${d.name}`}
                    onClick={() => confirmDelete(d)}
                    className="ml-2 rounded border border-gray-300 px-2 py-0.5 text-xs text-red-700"
                  >
                    Delete
                  </button>
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test -- --run test/features/admin/districts`
Expected: PASS, 11 tests.

- [ ] **Step 5: Full suite and typecheck**

Run: `npm run build && npm test -- --run`
Expected: build succeeds; all tests pass. **Pilot 1 is complete.**

- [ ] **Step 6: Commit**

```bash
git add frontend/src frontend/test
git commit -m "feat: delete districts with 409 dependent handling"
```

---

### Task 6: Gymnasts list with search and club filter

Pilot 2. Deliberately written standalone, in the same shape as `DistrictsPage`, so Stage B has two honest samples to extract from. Do **not** try to reuse anything from Districts yet.

**Files:**
- Create: `frontend/src/features/admin/gymnasts/GymnastsPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/test/fixtures.ts`
- Test: `frontend/test/features/admin/gymnasts/GymnastsPage.test.tsx`

**Interfaces:**
- Consumes: `GymnastRead` (already exported), `makeGymnast` (already exists)
- Produces: `GymnastsPage`, `ClubRead` type export, `makeClub(overrides?: Partial<ClubRead>): ClubRead`

- [ ] **Step 1: Write the failing tests**

Create `frontend/test/features/admin/gymnasts/GymnastsPage.test.tsx`:

```tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeClub, makeGymnast } from "../../../fixtures";
import { api, server } from "../../../msw/server";
import { renderApp } from "../../../utils";

function mockBase(gymnasts: unknown[] = []) {
  server.use(
    http.get(api("/gymnasts/"), () => HttpResponse.json(gymnasts)),
    http.get(api("/clubs/"), () =>
      HttpResponse.json([
        makeClub({ id: 1, name: "Star Gymnastics" }),
        makeClub({ id: 2, name: "Acro Academy" }),
      ]),
    ),
    http.get(api("/groups/"), () => HttpResponse.json([])),
  );
}

test("lists gymnasts with their club name", async () => {
  mockBase([
    makeGymnast({ id: 10, first_name: "Anna", last_name: "Botha", club_id: 1 }),
  ]);
  renderApp("/admin/gymnasts");
  expect(await screen.findByText("Anna Botha")).toBeInTheDocument();
  expect(screen.getByText("Star Gymnastics")).toBeInTheDocument();
});

test("shows an em dash for a gymnast with no club", async () => {
  // dob and country are filled in so the club cell is the only em dash on the row.
  mockBase([
    makeGymnast({
      id: 11,
      first_name: "Mia",
      last_name: "Nel",
      club_id: null,
      date_of_birth: "2012-08-19",
      country_code: "RSA",
    }),
  ]);
  renderApp("/admin/gymnasts");
  expect(await screen.findByText("Mia Nel")).toBeInTheDocument();
  expect(screen.getByText("—")).toBeInTheDocument();
});

test("search filters rows by name, client-side", async () => {
  mockBase([
    makeGymnast({ id: 10, first_name: "Anna", last_name: "Botha", club_id: 1 }),
    makeGymnast({ id: 11, first_name: "Mia", last_name: "Nel", club_id: 2 }),
  ]);
  renderApp("/admin/gymnasts");
  await screen.findByText("Anna Botha");
  await userEvent.type(screen.getByLabelText("Search"), "nel");
  expect(screen.queryByText("Anna Botha")).toBeNull();
  expect(screen.getByText("Mia Nel")).toBeInTheDocument();
});

test("the club filter refetches scoped to that club", async () => {
  mockBase([makeGymnast({ id: 10, first_name: "Anna", last_name: "Botha", club_id: 1 })]);
  const requested: (string | null)[] = [];
  server.use(
    http.get(api("/gymnasts/"), ({ request }) => {
      requested.push(new URL(request.url).searchParams.get("club_id"));
      return HttpResponse.json([]);
    }),
  );
  renderApp("/admin/gymnasts");
  await screen.findByLabelText("Club filter");
  await userEvent.selectOptions(screen.getByLabelText("Club filter"), "2");
  await screen.findByText("No gymnasts yet.");
  expect(requested).toContain("2");
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm test -- --run test/features/admin/gymnasts`
Expected: FAIL — `makeClub` not exported; no `/admin/gymnasts` route.

- [ ] **Step 3: Add the type export and fixture**

Append to `frontend/src/api/types.ts`:

```ts
export type ClubRead = components["schemas"]["ClubRead"];
```

Append to `frontend/test/fixtures.ts` (adding `ClubRead` to the top import block):

```ts
export function makeClub(overrides: Partial<ClubRead> = {}): ClubRead {
  return {
    id: id(),
    district_id: 1,
    name: "Star Gymnastics",
    abbreviation: "STAR",
    ...overrides,
  };
}
```

- [ ] **Step 4: Write `GymnastsPage` (read-only)**

Create `frontend/src/features/admin/gymnasts/GymnastsPage.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { apiDetail, client } from "../../../api/client";
import type { ClubRead, GymnastRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";

export function GymnastsPage() {
  const [search, setSearch] = useState("");
  const [clubFilter, setClubFilter] = useState("");

  const clubsQuery = useQuery({
    queryKey: ["clubs", {}],
    queryFn: async (): Promise<ClubRead[]> => {
      const { data, error } = await client.GET("/clubs/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const clubId = clubFilter === "" ? undefined : Number(clubFilter);
  const gymnastsQuery = useQuery({
    queryKey: ["gymnasts", { club_id: clubId }],
    queryFn: async (): Promise<GymnastRead[]> => {
      const { data, error } = await client.GET("/gymnasts/", {
        params: { query: clubId === undefined ? {} : { club_id: clubId } },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const clubName = (id: number | null) =>
    id === null ? "—" : (clubsQuery.data?.find((c) => c.id === id)?.name ?? "—");

  const needle = search.trim().toLowerCase();
  const rows = (gymnastsQuery.data ?? []).filter((g) =>
    needle === ""
      ? true
      : `${g.first_name} ${g.last_name}`.toLowerCase().includes(needle),
  );

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-xl font-bold">Gymnasts</h1>
      </div>
      <div className="mb-3 flex gap-3">
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
          Club filter
          <select
            aria-label="Club filter"
            value={clubFilter}
            onChange={(e) => setClubFilter(e.target.value)}
            className="ml-2 rounded border border-gray-300 p-1"
          >
            <option value="">All clubs</option>
            {clubsQuery.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ErrorBanner message={gymnastsQuery.error ? gymnastsQuery.error.message : null} />
      {gymnastsQuery.data && rows.length === 0 && (
        <p className="text-sm text-gray-500">No gymnasts yet.</p>
      )}
      {rows.length > 0 && (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-300 text-left">
              <th className="py-1">Name</th>
              <th className="py-1">Club</th>
              <th className="py-1">Date of birth</th>
              <th className="py-1">Country</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((g) => (
              <tr key={g.id} className="border-b border-gray-200">
                <td className="py-1">
                  {g.first_name} {g.last_name}
                </td>
                <td className="py-1">{clubName(g.club_id)}</td>
                <td className="py-1">{g.date_of_birth ?? "—"}</td>
                <td className="py-1">{g.country_code ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Add the route**

In `frontend/src/App.tsx`, import `GymnastsPage` and add inside the `/admin` route:

```tsx
          <Route path="gymnasts" element={<GymnastsPage />} />
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `npm test -- --run test/features/admin/gymnasts`
Expected: PASS, 4 tests.

- [ ] **Step 7: Commit**

```bash
git add frontend/src frontend/test
git commit -m "feat: gymnasts admin list with search and club filter"
```

---

### Task 7: Gymnast create

**Files:**
- Create: `frontend/src/features/admin/gymnasts/GymnastForm.tsx`
- Modify: `frontend/src/features/admin/gymnasts/GymnastsPage.tsx`
- Test: `frontend/test/features/admin/gymnasts/GymnastsPage.test.tsx` (append)

**Interfaces:**
- Consumes: `GymnastRead`, `ClubRead`, `GroupRead`
- Produces: `GymnastForm({ initial, clubs, groups, pending, error, onSubmit, onCancel })`; `GymnastBody` = the PATCH/POST body type

- [ ] **Step 1: Write the failing tests**

Append to `frontend/test/features/admin/gymnasts/GymnastsPage.test.tsx`:

```tsx
import { waitFor } from "@testing-library/react";
import { makeGroup } from "../../../fixtures";

test("creates a gymnast, sending nulls for the fields left blank", async () => {
  mockBase();
  server.use(
    http.get(api("/groups/"), () =>
      HttpResponse.json([makeGroup({ id: 3, name: "Zvezda RG" })]),
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
  await userEvent.type(screen.getByLabelText("First name"), "Zoe");
  await userEvent.type(screen.getByLabelText("Last name"), "Kruger");
  await userEvent.selectOptions(screen.getByLabelText("Club"), "1");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toEqual({
      first_name: "Zoe",
      last_name: "Kruger",
      club_id: 1,
      group_id: null,
      date_of_birth: null,
      country_code: null,
    }),
  );
});

test("sends the optional date and country when filled in", async () => {
  mockBase();
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/gymnasts/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGymnast(), { status: 201 });
    }),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "New gymnast" }));
  await userEvent.type(screen.getByLabelText("First name"), "Zoe");
  await userEvent.type(screen.getByLabelText("Last name"), "Kruger");
  await userEvent.type(screen.getByLabelText("Date of birth"), "2011-04-02");
  await userEvent.type(screen.getByLabelText("Country code"), "RSA");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toMatchObject({ date_of_birth: "2011-04-02", country_code: "RSA" }),
  );
});

test("rejects an over-long country code before sending", async () => {
  mockBase();
  let called = false;
  server.use(
    http.post(api("/gymnasts/"), () => {
      called = true;
      return HttpResponse.json(makeGymnast(), { status: 201 });
    }),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "New gymnast" }));
  await userEvent.type(screen.getByLabelText("First name"), "Zoe");
  await userEvent.type(screen.getByLabelText("Last name"), "Kruger");
  await userEvent.type(screen.getByLabelText("Country code"), "RSAX");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("At most 3 characters")).toBeInTheDocument();
  expect(called).toBe(false);
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm test -- --run test/features/admin/gymnasts`
Expected: FAIL — no "New gymnast" button.

- [ ] **Step 3: Write `GymnastForm`**

Create `frontend/src/features/admin/gymnasts/GymnastForm.tsx`:

```tsx
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { ClubRead, GroupRead, GymnastRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";

/** Select and date inputs hand back strings; "" means "not set" and becomes null. */
const gymnastSchema = z.object({
  first_name: z.string().trim().min(1, "First name is required"),
  last_name: z.string().trim().min(1, "Last name is required"),
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
      <label className="text-sm">
        Club
        <select {...register("club_id")} aria-label="Club" className={fieldClass}>
          <option value="">— none —</option>
          {clubs.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      <label className="text-sm">
        Group
        <select {...register("group_id")} aria-label="Group" className={fieldClass}>
          <option value="">— none —</option>
          {groups.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </select>
      </label>
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
```

- [ ] **Step 4: Wire create into `GymnastsPage`**

Add to `GymnastsPage.tsx`: the `useMutation`/`useQueryClient` imports, a groups query, dialog state, the POST mutation, a "New gymnast" header button and the dialog block — mirroring Task 3's `DistrictsPage` structure exactly:

```tsx
  const groupsQuery = useQuery({
    queryKey: ["groups", {}],
    queryFn: async (): Promise<GroupRead[]> => {
      const { data, error } = await client.GET("/groups/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const [dialog, setDialog] = useState<{ row: GymnastRead | null } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: async (body: GymnastBody) => {
      const { data, error } = await client.POST("/gymnasts/", {
        body: body as { first_name: string; last_name: string },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["gymnasts"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });
```

Header button:

```tsx
        <button
          type="button"
          onClick={() => {
            setFormError(null);
            setDialog({ row: null });
          }}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New gymnast
        </button>
```

Dialog:

```tsx
      {dialog && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/30">
          <div className="w-96 rounded border border-gray-200 bg-white p-4 shadow-lg">
            <h2 className="mb-2 text-lg font-semibold">
              {dialog.row ? "Edit gymnast" : "New gymnast"}
            </h2>
            <GymnastForm
              key={dialog.row?.id ?? "new"}
              initial={dialog.row}
              clubs={clubsQuery.data ?? []}
              groups={groupsQuery.data ?? []}
              pending={saveMutation.isPending}
              error={formError}
              onSubmit={(body) => saveMutation.mutate(body)}
              onCancel={() => setDialog(null)}
            />
          </div>
        </div>
      )}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `npm test -- --run test/features/admin/gymnasts`
Expected: PASS, 7 tests.

- [ ] **Step 6: Commit**

```bash
git add frontend/src frontend/test
git commit -m "feat: create gymnasts from the admin console"
```

---

### Task 8: Gymnast edit and delete

**Files:**
- Modify: `frontend/src/features/admin/gymnasts/GymnastsPage.tsx`
- Test: `frontend/test/features/admin/gymnasts/GymnastsPage.test.tsx` (append)

**Interfaces:**
- Consumes: `GymnastForm` from Task 7
- Produces: nothing new

- [ ] **Step 1: Write the failing tests**

Append to `frontend/test/features/admin/gymnasts/GymnastsPage.test.tsx`:

```tsx
test("edit sends only the changed field and leaves the untouched group alone", async () => {
  mockBase([
    makeGymnast({
      id: 10,
      first_name: "Anna",
      last_name: "Botha",
      club_id: 1,
      group_id: 3,
      date_of_birth: "2011-04-02",
    }),
  ]);
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/gymnasts/:gymnastId"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGymnast({ id: 10 }));
    }),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Anna Botha" }));
  const last = screen.getByLabelText("Last name");
  await userEvent.clear(last);
  await userEvent.type(last, "Botha-Smit");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ last_name: "Botha-Smit" }));
});

test("clearing the club sends an explicit null", async () => {
  mockBase([
    makeGymnast({ id: 10, first_name: "Anna", last_name: "Botha", club_id: 1 }),
  ]);
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/gymnasts/:gymnastId"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGymnast({ id: 10 }));
    }),
  );
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Anna Botha" }));
  await userEvent.selectOptions(screen.getByLabelText("Club"), "");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ club_id: null }));
});

test("deletes a gymnast after confirmation and surfaces a 409", async () => {
  mockBase([
    makeGymnast({ id: 10, first_name: "Anna", last_name: "Botha", club_id: 1 }),
  ]);
  server.use(
    http.delete(api("/gymnasts/:gymnastId"), () =>
      HttpResponse.json({ detail: "Cannot delete gymnast with entries" }, { status: 409 }),
    ),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/admin/gymnasts");
  await userEvent.click(await screen.findByRole("button", { name: "Delete Anna Botha" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("with entries");
  expect(confirmSpy.mock.calls[0][0]).toContain("Anna Botha");
  confirmSpy.mockRestore();
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm test -- --run test/features/admin/gymnasts`
Expected: FAIL — no "Edit Anna Botha" button.

- [ ] **Step 3: Add the PATCH branch, delete mutation and action cell**

In `GymnastsPage.tsx`, make `saveMutation` branch on `dialog?.row` exactly as Districts does:

```tsx
    mutationFn: async (body: GymnastBody) => {
      const editingRow = dialog?.row ?? null;
      if (editingRow) {
        const { data, error } = await client.PATCH("/gymnasts/{gymnast_id}", {
          params: { path: { gymnast_id: editingRow.id } },
          body,
        });
        if (error) throw new Error(apiDetail(error));
        return data;
      }
      const { data, error } = await client.POST("/gymnasts/", {
        body: body as { first_name: string; last_name: string },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
```

Add delete:

```tsx
  const [listError, setListError] = useState<string | null>(null);

  const deleteMutation = useMutation({
    mutationFn: async (row: GymnastRead) => {
      const { error } = await client.DELETE("/gymnasts/{gymnast_id}", {
        params: { path: { gymnast_id: row.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
    onSuccess: () => {
      setListError(null);
      queryClient.invalidateQueries({ queryKey: ["gymnasts"] });
    },
    onError: (e: Error) => setListError(e.message),
  });

  const confirmDelete = (row: GymnastRead) => {
    const name = `${row.first_name} ${row.last_name}`;
    if (!window.confirm(`Delete gymnast "${name}"?`)) return;
    deleteMutation.mutate(row);
  };
```

Update the error banner to `message={gymnastsQuery.error ? gymnastsQuery.error.message : listError}`, add a trailing `<th className="py-1" />` and an action cell per row:

```tsx
                <td className="py-1 text-right">
                  <button
                    type="button"
                    aria-label={`Edit ${g.first_name} ${g.last_name}`}
                    onClick={() => {
                      setFormError(null);
                      setDialog({ row: g });
                    }}
                    className="rounded border border-gray-300 px-2 py-0.5 text-xs"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${g.first_name} ${g.last_name}`}
                    onClick={() => confirmDelete(g)}
                    className="ml-2 rounded border border-gray-300 px-2 py-0.5 text-xs text-red-700"
                  >
                    Delete
                  </button>
                </td>
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test -- --run test/features/admin/gymnasts`
Expected: PASS, 10 tests.

- [ ] **Step 5: Full suite and typecheck**

Run: `npm run build && npm test -- --run`
Expected: build succeeds; all tests pass. **Stage A is complete — both pilots work.**

- [ ] **Step 6: Commit**

```bash
git add frontend/src frontend/test
git commit -m "feat: edit and delete gymnasts from the admin console"
```

---

## Stage B — Extract

Both pilots now work and are fully tested. The extraction is a **refactor**: the existing page tests must keep passing untouched. If a test needs editing to accommodate an extracted component, the extraction changed behaviour — fix the component, not the test.

### Task 9: Extract `ResourceTable` and `FormDialog`

**Files:**
- Create: `frontend/src/features/admin/components/ResourceTable.tsx`
- Create: `frontend/src/features/admin/components/FormDialog.tsx`
- Modify: `frontend/src/features/admin/districts/DistrictsPage.tsx`
- Modify: `frontend/src/features/admin/gymnasts/GymnastsPage.tsx`
- Test: `frontend/test/features/admin/components/ResourceTable.test.tsx`

**Interfaces:**
- Consumes: nothing
- Produces:
  ```ts
  export type Column<T> = { header: string; render: (row: T) => ReactNode };
  export function ResourceTable<T extends { id: number }>(props: {
    rows: T[];
    columns: Column<T>[];
    rowLabel: (row: T) => string;   // used for the Edit/Delete aria-labels
    onEdit: (row: T) => void;
    onDelete: (row: T) => void;
    emptyMessage: string;
  }): JSX.Element;

  export function FormDialog(props: {
    open: boolean;
    title: string;
    children: ReactNode;   // the resource's own form
  }): JSX.Element | null;
  ```

- [ ] **Step 1: Write the failing test**

Create `frontend/test/features/admin/components/ResourceTable.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResourceTable } from "../../../../src/features/admin/components/ResourceTable";

type Row = { id: number; name: string };
const rows: Row[] = [
  { id: 1, name: "Alpha" },
  { id: 2, name: "Beta" },
];
const columns = [{ header: "Name", render: (r: Row) => r.name }];

test("renders a row per item with labelled actions", async () => {
  const onEdit = vi.fn();
  const onDelete = vi.fn();
  render(
    <ResourceTable
      rows={rows}
      columns={columns}
      rowLabel={(r) => r.name}
      onEdit={onEdit}
      onDelete={onDelete}
      emptyMessage="Nothing here."
    />,
  );
  expect(screen.getByText("Alpha")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Edit Beta" }));
  expect(onEdit).toHaveBeenCalledWith(rows[1]);
  await userEvent.click(screen.getByRole("button", { name: "Delete Alpha" }));
  expect(onDelete).toHaveBeenCalledWith(rows[0]);
});

test("renders the empty message instead of a table when there are no rows", () => {
  render(
    <ResourceTable
      rows={[]}
      columns={columns}
      rowLabel={(r) => r.name}
      onEdit={vi.fn()}
      onDelete={vi.fn()}
      emptyMessage="Nothing here."
    />,
  );
  expect(screen.getByText("Nothing here.")).toBeInTheDocument();
  expect(screen.queryByRole("table")).toBeNull();
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -- --run test/features/admin/components`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `ResourceTable`**

Create `frontend/src/features/admin/components/ResourceTable.tsx`:

```tsx
import type { ReactNode } from "react";

export type Column<T> = { header: string; render: (row: T) => ReactNode };

export function ResourceTable<T extends { id: number }>({
  rows,
  columns,
  rowLabel,
  onEdit,
  onDelete,
  emptyMessage,
}: {
  rows: T[];
  columns: Column<T>[];
  rowLabel: (row: T) => string;
  onEdit: (row: T) => void;
  onDelete: (row: T) => void;
  emptyMessage: string;
}) {
  if (rows.length === 0) return <p className="text-sm text-gray-500">{emptyMessage}</p>;

  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="border-b border-gray-300 text-left">
          {columns.map((c) => (
            <th key={c.header} className="py-1">
              {c.header}
            </th>
          ))}
          <th className="py-1" />
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id} className="border-b border-gray-200">
            {columns.map((c) => (
              <td key={c.header} className="py-1">
                {c.render(row)}
              </td>
            ))}
            <td className="py-1 text-right">
              <button
                type="button"
                aria-label={`Edit ${rowLabel(row)}`}
                onClick={() => onEdit(row)}
                className="rounded border border-gray-300 px-2 py-0.5 text-xs"
              >
                Edit
              </button>
              <button
                type="button"
                aria-label={`Delete ${rowLabel(row)}`}
                onClick={() => onDelete(row)}
                className="ml-2 rounded border border-gray-300 px-2 py-0.5 text-xs text-red-700"
              >
                Delete
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 4: Write `FormDialog`**

Create `frontend/src/features/admin/components/FormDialog.tsx`:

```tsx
import type { ReactNode } from "react";

/**
 * Modal shell only. The error banner and the Cancel/Save buttons live inside each
 * resource's own form, because they are wired to that form's RHF instance.
 */
export function FormDialog({
  open,
  title,
  children,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black/30">
      <div className="w-96 rounded border border-gray-200 bg-white p-4 shadow-lg">
        <h2 className="mb-2 text-lg font-semibold">{title}</h2>
        {children}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Refactor both pilot pages onto them**

In `DistrictsPage.tsx`, replace the `<table>` block with:

```tsx
      {districtsQuery.data && (
        <ResourceTable
          rows={districtsQuery.data}
          columns={[
            { header: "Name", render: (d) => d.name },
            { header: "Abbreviation", render: (d) => d.abbreviation },
          ]}
          rowLabel={(d) => d.name}
          onEdit={(d) => {
            setFormError(null);
            setDialog({ row: d });
          }}
          onDelete={confirmDelete}
          emptyMessage="No districts yet."
        />
      )}
```

and delete the now-dead `districtsQuery.data?.length === 0` paragraph. Replace the dialog block with:

```tsx
      <FormDialog
        open={dialog !== null}
        title={dialog?.row ? "Edit district" : "New district"}
      >
        {dialog && (
          <DistrictForm
            key={dialog.row?.id ?? "new"}
            initial={dialog.row}
            pending={saveMutation.isPending}
            error={formError}
            onSubmit={(body) => saveMutation.mutate(body)}
            onCancel={() => setDialog(null)}
          />
        )}
      </FormDialog>
```

Do the same in `GymnastsPage.tsx` with its four columns (`Name`, `Club`, `Date of birth`, `Country`), `rowLabel={(g) => `${g.first_name} ${g.last_name}`}` and `emptyMessage="No gymnasts yet."`, keeping the `rows` variable (the search-filtered array) as the `rows` prop.

- [ ] **Step 6: Run the full admin suite — the pilot tests must pass unchanged**

Run: `npm test -- --run test/features/admin`
Expected: PASS, 25 tests (23 pilot tests + the 2 new `ResourceTable` tests). **Do not edit any Task 2-8 test to make this pass.**

- [ ] **Step 7: Typecheck and commit**

```bash
npm run build
git add frontend/src frontend/test
git commit -m "refactor: extract ResourceTable and FormDialog from the admin pilots"
```

---

### Task 10: Extract `useResourceList`, `useResourceDelete` and `FkSelect`

**Files:**
- Create: `frontend/src/features/admin/hooks/useResourceList.ts`
- Create: `frontend/src/features/admin/hooks/useResourceDelete.ts`
- Create: `frontend/src/features/admin/components/FkSelect.tsx`
- Modify: `frontend/src/features/admin/districts/DistrictsPage.tsx`
- Modify: `frontend/src/features/admin/gymnasts/GymnastsPage.tsx`
- Modify: `frontend/src/features/admin/gymnasts/GymnastForm.tsx`
- Test: `frontend/test/features/admin/hooks/useResourceList.test.ts`

**Interfaces:**
- Consumes: `apiDetail`, `client`
- Produces:
  ```ts
  export function matchesSearch(text: string, query: string): boolean;
  export function useResourceList<T>(opts: {
    queryKey: unknown[];
    fetchRows: () => Promise<T[]>;
    search?: string;
    searchText?: (row: T) => string;
  }): { rows: T[]; loaded: boolean; error: string | null };

  export function useResourceDelete<T>(opts: {
    queryKey: unknown[];
    describe: (row: T) => string;      // "district \"Gauteng\""
    remove: (row: T) => Promise<void>;
  }): { confirmDelete: (row: T) => void; error: string | null };

  export function FkSelect(props: {
    label: string;
    options: { id: number; label: string }[];
    noneLabel?: string;              // omit for a required FK
  } & SelectHTMLAttributes<HTMLSelectElement>): JSX.Element;
  ```

- [ ] **Step 1: Write the failing test for the search predicate**

Create `frontend/test/features/admin/hooks/useResourceList.test.ts`:

```ts
import { matchesSearch } from "../../../../src/features/admin/hooks/useResourceList";

test("matchesSearch is case-insensitive and trims the query", () => {
  expect(matchesSearch("Anna Botha", "botha")).toBe(true);
  expect(matchesSearch("Anna Botha", "  ANNA ")).toBe(true);
  expect(matchesSearch("Anna Botha", "nel")).toBe(false);
});

test("an empty query matches everything", () => {
  expect(matchesSearch("Anna Botha", "")).toBe(true);
  expect(matchesSearch("Anna Botha", "   ")).toBe(true);
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -- --run test/features/admin/hooks`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `useResourceList`**

Create `frontend/src/features/admin/hooks/useResourceList.ts`:

```ts
import { useQuery } from "@tanstack/react-query";

/** Client-side search: lists are unpaginated, so filtering never hits the API. */
export function matchesSearch(text: string, query: string): boolean {
  const needle = query.trim().toLowerCase();
  return needle === "" || text.toLowerCase().includes(needle);
}

export function useResourceList<T>({
  queryKey,
  fetchRows,
  search = "",
  searchText,
}: {
  queryKey: unknown[];
  fetchRows: () => Promise<T[]>;
  search?: string;
  searchText?: (row: T) => string;
}): { rows: T[]; loaded: boolean; error: string | null } {
  const query = useQuery({ queryKey, queryFn: fetchRows });
  const all = query.data ?? [];
  const rows = searchText ? all.filter((r) => matchesSearch(searchText(r), search)) : all;
  return {
    rows,
    loaded: query.data !== undefined,
    error: query.error ? query.error.message : null,
  };
}
```

- [ ] **Step 4: Write `useResourceDelete`**

Create `frontend/src/features/admin/hooks/useResourceDelete.ts`:

```ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

/**
 * Confirm, delete, invalidate. A 409 (RESTRICT: dependents exist) surfaces as the
 * API's own `detail` — the frontend never predicts whether a delete will be allowed.
 */
export function useResourceDelete<T>({
  queryKey,
  describe,
  remove,
}: {
  queryKey: unknown[];
  describe: (row: T) => string;
  remove: (row: T) => Promise<void>;
}): { confirmDelete: (row: T) => void; error: string | null } {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: remove,
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey });
    },
    onError: (e: Error) => setError(e.message),
  });

  const confirmDelete = (row: T) => {
    if (!window.confirm(`Delete ${describe(row)}?`)) return;
    mutation.mutate(row);
  };

  return { confirmDelete, error };
}
```

- [ ] **Step 5: Write `FkSelect`**

Create `frontend/src/features/admin/components/FkSelect.tsx`:

```tsx
import type { SelectHTMLAttributes } from "react";

/**
 * Spreads the rest props onto the native <select>, so it works both with RHF's
 * `{...register("club_id")}` and with a plain controlled `value`/`onChange` filter.
 */
export function FkSelect({
  label,
  options,
  noneLabel,
  ...selectProps
}: {
  label: string;
  options: { id: number; label: string }[];
  noneLabel?: string;
} & SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <label className="text-sm">
      {label}
      <select
        aria-label={label}
        {...selectProps}
        className="mt-1 block w-full rounded border border-gray-300 p-1"
      >
        {noneLabel !== undefined && <option value="">{noneLabel}</option>}
        {options.map((o) => (
          <option key={o.id} value={o.id}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
```

- [ ] **Step 6: Refactor both pilots onto the hooks**

In `DistrictsPage.tsx`, replace the `useQuery` block with:

```tsx
  const list = useResourceList<DistrictRead>({
    queryKey: ["districts"],
    fetchRows: async () => {
      const { data, error } = await client.GET("/districts/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });
```

and the delete mutation with:

```tsx
  const { confirmDelete, error: deleteError } = useResourceDelete<DistrictRead>({
    queryKey: ["districts"],
    describe: (d) => `district "${d.name}"`,
    remove: async (d) => {
      const { error } = await client.DELETE("/districts/{district_id}", {
        params: { path: { district_id: d.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
  });
```

Banner becomes `<ErrorBanner message={list.error ?? deleteError} />`; the table renders when `list.loaded` with `rows={list.rows}`.

Apply the same two substitutions in `GymnastsPage.tsx`, passing the search props:

```tsx
  const list = useResourceList<GymnastRead>({
    queryKey: ["gymnasts", { club_id: clubId }],
    fetchRows: async () => {
      const { data, error } = await client.GET("/gymnasts/", {
        params: { query: clubId === undefined ? {} : { club_id: clubId } },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    search,
    searchText: (g) => `${g.first_name} ${g.last_name}`,
  });
```

Delete the now-dead local `needle`/`rows` filtering.

- [ ] **Step 7: Refactor the club/group fields onto `FkSelect`**

In `GymnastForm.tsx`, replace the two `<label>`-wrapped selects with:

```tsx
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
```

In `GymnastsPage.tsx`, the club filter keeps its own `<label>`+`<select>` — it has an "All clubs" option rather than a none-option and is not an FK field. Leave it alone.

- [ ] **Step 8: Give Districts a search box too**

The spec calls for client-side search on every resource list. Districts did not get one in Stage A because `useResourceList` did not exist yet; now it does.

Append to `frontend/test/features/admin/districts/DistrictsPage.test.tsx`:

```tsx
test("search filters districts client-side", async () => {
  server.use(
    http.get(api("/districts/"), () =>
      HttpResponse.json([
        makeDistrict({ id: 1, name: "Western Cape", abbreviation: "WC" }),
        makeDistrict({ id: 2, name: "Gauteng", abbreviation: "GAU" }),
      ]),
    ),
  );
  renderApp("/admin/districts");
  await screen.findByText("Western Cape");
  await userEvent.type(screen.getByLabelText("Search"), "gau");
  expect(screen.queryByText("Western Cape")).toBeNull();
  expect(screen.getByText("Gauteng")).toBeInTheDocument();
});
```

Run it and watch it fail (no "Search" field), then in `DistrictsPage.tsx` add the state, pass it to the hook, and render the input:

```tsx
  const [search, setSearch] = useState("");
```

```tsx
    search,
    searchText: (d) => `${d.name} ${d.abbreviation}`,
```

```tsx
      <label className="mb-3 block text-sm">
        Search
        <input
          aria-label="Search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ml-2 rounded border border-gray-300 p-1"
        />
      </label>
```

- [ ] **Step 9: Run the full admin suite — pilot tests still unchanged**

Run: `npm test -- --run test/features/admin`
Expected: PASS, 28 tests (25 + 2 `useResourceList` + 1 districts search).

- [ ] **Step 10: Typecheck, full suite, commit**

```bash
npm run build && npm test -- --run
git add frontend/src frontend/test
git commit -m "refactor: extract useResourceList, useResourceDelete and FkSelect"
```

**Stage B is complete.** Before starting Stage C, re-read `ResourceTable`, `FormDialog`, `useResourceList`, `useResourceDelete` and `FkSelect`. If any of them grew a parameter that only one pilot uses, simplify it now — Stage C will multiply that awkwardness by three.

---

## Stage C — Roll out

Each remaining resource is one task: list + create + edit + delete on the extracted layer. They are structurally identical; the differences are called out per task.

### Task 11: Clubs

Club is District plus a required `district_id` FK and a district filter.

**Files:**
- Create: `frontend/src/features/admin/clubs/ClubsPage.tsx`
- Create: `frontend/src/features/admin/clubs/ClubForm.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/test/features/admin/clubs/ClubsPage.test.tsx`

**Interfaces:**
- Consumes: `ResourceTable`, `Column`, `FormDialog`, `FkSelect`, `useResourceList`, `useResourceDelete`, `ClubRead`, `DistrictRead`, `makeClub`, `makeDistrict`
- Produces: `ClubsPage`, `ClubForm`, `ClubBody = { name?: string; abbreviation?: string; district_id?: number }`

- [ ] **Step 1: Write the failing tests**

Create `frontend/test/features/admin/clubs/ClubsPage.test.tsx`:

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeClub, makeDistrict } from "../../../fixtures";
import { api, server } from "../../../msw/server";
import { renderApp } from "../../../utils";

function mockBase(clubs: unknown[] = []) {
  server.use(
    http.get(api("/clubs/"), () => HttpResponse.json(clubs)),
    http.get(api("/districts/"), () =>
      HttpResponse.json([makeDistrict({ id: 1, name: "Western Cape" })]),
    ),
  );
}

test("lists clubs with their district name", async () => {
  mockBase([makeClub({ id: 5, name: "Star Gymnastics", abbreviation: "STAR", district_id: 1 })]);
  renderApp("/admin/clubs");
  expect(await screen.findByText("Star Gymnastics")).toBeInTheDocument();
  expect(screen.getByText("Western Cape")).toBeInTheDocument();
});

test("creates a club", async () => {
  mockBase();
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/clubs/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeClub(), { status: 201 });
    }),
  );
  renderApp("/admin/clubs");
  await userEvent.click(await screen.findByRole("button", { name: "New club" }));
  await userEvent.type(screen.getByLabelText("Name"), "Acro Academy");
  await userEvent.type(screen.getByLabelText("Abbreviation"), "ACRO");
  await userEvent.selectOptions(screen.getByLabelText("District"), "1");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toEqual({ name: "Acro Academy", abbreviation: "ACRO", district_id: 1 }),
  );
});

test("requires a district", async () => {
  mockBase();
  let called = false;
  server.use(
    http.post(api("/clubs/"), () => {
      called = true;
      return HttpResponse.json(makeClub(), { status: 201 });
    }),
  );
  renderApp("/admin/clubs");
  await userEvent.click(await screen.findByRole("button", { name: "New club" }));
  await userEvent.type(screen.getByLabelText("Name"), "Acro Academy");
  await userEvent.type(screen.getByLabelText("Abbreviation"), "ACRO");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Pick a district")).toBeInTheDocument();
  expect(called).toBe(false);
});

test("edits a club, sending only the changed field", async () => {
  mockBase([makeClub({ id: 5, name: "Star Gymnastics", abbreviation: "STAR", district_id: 1 })]);
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/clubs/:clubId"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeClub({ id: 5 }));
    }),
  );
  renderApp("/admin/clubs");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Star Gymnastics" }));
  const abbr = screen.getByLabelText("Abbreviation");
  await userEvent.clear(abbr);
  await userEvent.type(abbr, "STARS");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ abbreviation: "STARS" }));
});

test("surfaces a 409 when a club still has dependents", async () => {
  mockBase([makeClub({ id: 5, name: "Star Gymnastics", district_id: 1 })]);
  server.use(
    http.delete(api("/clubs/:clubId"), () =>
      HttpResponse.json({ detail: "Cannot delete club with existing gymnasts" }, { status: 409 }),
    ),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/admin/clubs");
  await userEvent.click(await screen.findByRole("button", { name: "Delete Star Gymnastics" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("existing gymnasts");
  confirmSpy.mockRestore();
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm test -- --run test/features/admin/clubs`
Expected: FAIL — no `/admin/clubs` route.

- [ ] **Step 3: Write `ClubForm`**

Create `frontend/src/features/admin/clubs/ClubForm.tsx`:

```tsx
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { ClubRead, DistrictRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FkSelect } from "../components/FkSelect";

const clubSchema = z.object({
  name: z.string().trim().min(1, "Name is required"),
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
    if (dirtyFields.district_id) body.district_id = full.district_id;
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
        Abbreviation
        <input {...register("abbreviation")} aria-label="Abbreviation" className={fieldClass} />
        {errors.abbreviation && (
          <span className="text-xs text-red-700">{errors.abbreviation.message}</span>
        )}
      </label>
      <div>
        <FkSelect
          label="District"
          noneLabel="— pick —"
          options={districts.map((d) => ({ id: d.id, label: d.name }))}
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
```

- [ ] **Step 4: Write `ClubsPage`**

Create `frontend/src/features/admin/clubs/ClubsPage.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiDetail, client } from "../../../api/client";
import type { ClubRead, DistrictRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FormDialog } from "../components/FormDialog";
import { ResourceTable } from "../components/ResourceTable";
import { useResourceDelete } from "../hooks/useResourceDelete";
import { useResourceList } from "../hooks/useResourceList";
import { ClubForm, type ClubBody } from "./ClubForm";

export function ClubsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [dialog, setDialog] = useState<{ row: ClubRead | null } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const districtsQuery = useQuery({
    queryKey: ["districts"],
    queryFn: async (): Promise<DistrictRead[]> => {
      const { data, error } = await client.GET("/districts/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const list = useResourceList<ClubRead>({
    queryKey: ["clubs", {}],
    fetchRows: async () => {
      const { data, error } = await client.GET("/clubs/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    search,
    searchText: (c) => `${c.name} ${c.abbreviation}`,
  });

  const { confirmDelete, error: deleteError } = useResourceDelete<ClubRead>({
    queryKey: ["clubs"],
    describe: (c) => `club "${c.name}"`,
    remove: async (c) => {
      const { error } = await client.DELETE("/clubs/{club_id}", {
        params: { path: { club_id: c.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
  });

  const saveMutation = useMutation({
    mutationFn: async (body: ClubBody) => {
      const editingRow = dialog?.row ?? null;
      if (editingRow) {
        const { data, error } = await client.PATCH("/clubs/{club_id}", {
          params: { path: { club_id: editingRow.id } },
          body,
        });
        if (error) throw new Error(apiDetail(error));
        return data;
      }
      const { data, error } = await client.POST("/clubs/", {
        body: body as { name: string; abbreviation: string; district_id: number },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["clubs"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });

  const districtName = (id: number) =>
    districtsQuery.data?.find((d) => d.id === id)?.name ?? "—";

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-xl font-bold">Clubs</h1>
        <button
          type="button"
          onClick={() => {
            setFormError(null);
            setDialog({ row: null });
          }}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New club
        </button>
      </div>
      <label className="mb-3 block text-sm">
        Search
        <input
          aria-label="Search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ml-2 rounded border border-gray-300 p-1"
        />
      </label>
      <ErrorBanner message={list.error ?? deleteError} />
      {list.loaded && (
        <ResourceTable
          rows={list.rows}
          columns={[
            { header: "Name", render: (c) => c.name },
            { header: "Abbreviation", render: (c) => c.abbreviation },
            { header: "District", render: (c) => districtName(c.district_id) },
          ]}
          rowLabel={(c) => c.name}
          onEdit={(c) => {
            setFormError(null);
            setDialog({ row: c });
          }}
          onDelete={confirmDelete}
          emptyMessage="No clubs yet."
        />
      )}
      <FormDialog open={dialog !== null} title={dialog?.row ? "Edit club" : "New club"}>
        {dialog && (
          <ClubForm
            key={dialog.row?.id ?? "new"}
            initial={dialog.row}
            districts={districtsQuery.data ?? []}
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

- [ ] **Step 5: Add the route**

In `frontend/src/App.tsx`, import `ClubsPage` and add `<Route path="clubs" element={<ClubsPage />} />` inside the `/admin` route.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `npm test -- --run test/features/admin/clubs`
Expected: PASS, 5 tests.

- [ ] **Step 7: Commit**

```bash
git add frontend/src frontend/test
git commit -m "feat: clubs admin screen"
```

---

### Task 12: Coaches

Coach is Club-shaped but with two name fields, a boolean, and no abbreviation. `club_id` is required.

**Files:**
- Create: `frontend/src/features/admin/coaches/CoachesPage.tsx`
- Create: `frontend/src/features/admin/coaches/CoachForm.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/test/fixtures.ts`
- Test: `frontend/test/features/admin/coaches/CoachesPage.test.tsx`

**Interfaces:**
- Consumes: the Stage B layer; `ClubRead`, `makeClub`
- Produces: `CoachesPage`, `CoachForm`, `CoachRead` type export, `makeCoach`, `CoachBody = { first_name?: string; last_name?: string; club_id?: number; is_head_coach?: boolean }`

- [ ] **Step 1: Write the failing tests**

Create `frontend/test/features/admin/coaches/CoachesPage.test.tsx`:

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeClub, makeCoach } from "../../../fixtures";
import { api, server } from "../../../msw/server";
import { renderApp } from "../../../utils";

function mockBase(coaches: unknown[] = []) {
  server.use(
    http.get(api("/coaches/"), () => HttpResponse.json(coaches)),
    http.get(api("/clubs/"), () =>
      HttpResponse.json([makeClub({ id: 1, name: "Star Gymnastics" })]),
    ),
  );
}

test("lists coaches with club and head-coach status", async () => {
  mockBase([
    makeCoach({ id: 7, first_name: "Thabo", last_name: "Mokoena", club_id: 1, is_head_coach: true }),
  ]);
  renderApp("/admin/coaches");
  expect(await screen.findByText("Thabo Mokoena")).toBeInTheDocument();
  expect(screen.getByText("Star Gymnastics")).toBeInTheDocument();
  expect(screen.getByText("Head coach")).toBeInTheDocument();
});

test("creates a coach with the head-coach flag", async () => {
  mockBase();
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/coaches/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeCoach(), { status: 201 });
    }),
  );
  renderApp("/admin/coaches");
  await userEvent.click(await screen.findByRole("button", { name: "New coach" }));
  await userEvent.type(screen.getByLabelText("First name"), "Thabo");
  await userEvent.type(screen.getByLabelText("Last name"), "Mokoena");
  await userEvent.selectOptions(screen.getByLabelText("Club"), "1");
  await userEvent.click(screen.getByLabelText("Head coach"));
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(posted).toEqual({
      first_name: "Thabo",
      last_name: "Mokoena",
      club_id: 1,
      is_head_coach: true,
    }),
  );
});

test("edits a coach, sending only the toggled flag", async () => {
  mockBase([
    makeCoach({ id: 7, first_name: "Thabo", last_name: "Mokoena", club_id: 1, is_head_coach: false }),
  ]);
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/coaches/:coachId"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeCoach({ id: 7 }));
    }),
  );
  renderApp("/admin/coaches");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Thabo Mokoena" }));
  await userEvent.click(screen.getByLabelText("Head coach"));
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ is_head_coach: true }));
});

test("surfaces a duplicate-identity 409", async () => {
  mockBase();
  server.use(
    http.post(api("/coaches/"), () =>
      HttpResponse.json({ detail: "Coach already exists in this club" }, { status: 409 }),
    ),
  );
  renderApp("/admin/coaches");
  await userEvent.click(await screen.findByRole("button", { name: "New coach" }));
  await userEvent.type(screen.getByLabelText("First name"), "Thabo");
  await userEvent.type(screen.getByLabelText("Last name"), "Mokoena");
  await userEvent.selectOptions(screen.getByLabelText("Club"), "1");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("already exists");
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm test -- --run test/features/admin/coaches`
Expected: FAIL — `makeCoach` not exported.

- [ ] **Step 3: Add the type export and fixture**

Append to `frontend/src/api/types.ts`:

```ts
export type CoachRead = components["schemas"]["CoachRead"];
```

Append to `frontend/test/fixtures.ts` (adding `CoachRead` to the top import block):

```ts
export function makeCoach(overrides: Partial<CoachRead> = {}): CoachRead {
  return {
    id: id(),
    club_id: 1,
    first_name: "Thabo",
    last_name: "Mokoena",
    is_head_coach: false,
    ...overrides,
  };
}
```

- [ ] **Step 4: Write `CoachForm`**

Create `frontend/src/features/admin/coaches/CoachForm.tsx`:

```tsx
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { ClubRead, CoachRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FkSelect } from "../components/FkSelect";

const coachSchema = z.object({
  first_name: z.string().trim().min(1, "First name is required"),
  last_name: z.string().trim().min(1, "Last name is required"),
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
    if (dirtyFields.club_id) body.club_id = full.club_id;
    if (dirtyFields.is_head_coach) body.is_head_coach = full.is_head_coach;
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
      <div>
        <FkSelect
          label="Club"
          noneLabel="— pick —"
          options={clubs.map((c) => ({ id: c.id, label: c.name }))}
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
```

- [ ] **Step 5: Write `CoachesPage`**

Create `frontend/src/features/admin/coaches/CoachesPage.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiDetail, client } from "../../../api/client";
import type { ClubRead, CoachRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FormDialog } from "../components/FormDialog";
import { ResourceTable } from "../components/ResourceTable";
import { useResourceDelete } from "../hooks/useResourceDelete";
import { useResourceList } from "../hooks/useResourceList";
import { CoachForm, type CoachBody } from "./CoachForm";

export function CoachesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [dialog, setDialog] = useState<{ row: CoachRead | null } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const clubsQuery = useQuery({
    queryKey: ["clubs", {}],
    queryFn: async (): Promise<ClubRead[]> => {
      const { data, error } = await client.GET("/clubs/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const list = useResourceList<CoachRead>({
    queryKey: ["coaches", {}],
    fetchRows: async () => {
      const { data, error } = await client.GET("/coaches/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    search,
    searchText: (c) => `${c.first_name} ${c.last_name}`,
  });

  const { confirmDelete, error: deleteError } = useResourceDelete<CoachRead>({
    queryKey: ["coaches"],
    describe: (c) => `coach "${c.first_name} ${c.last_name}"`,
    remove: async (c) => {
      const { error } = await client.DELETE("/coaches/{coach_id}", {
        params: { path: { coach_id: c.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
  });

  const saveMutation = useMutation({
    mutationFn: async (body: CoachBody) => {
      const editingRow = dialog?.row ?? null;
      if (editingRow) {
        const { data, error } = await client.PATCH("/coaches/{coach_id}", {
          params: { path: { coach_id: editingRow.id } },
          body,
        });
        if (error) throw new Error(apiDetail(error));
        return data;
      }
      const { data, error } = await client.POST("/coaches/", {
        body: body as {
          first_name: string;
          last_name: string;
          club_id: number;
          is_head_coach: boolean;
        },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["coaches"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });

  const clubName = (id: number) => clubsQuery.data?.find((c) => c.id === id)?.name ?? "—";

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-xl font-bold">Coaches</h1>
        <button
          type="button"
          onClick={() => {
            setFormError(null);
            setDialog({ row: null });
          }}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New coach
        </button>
      </div>
      <label className="mb-3 block text-sm">
        Search
        <input
          aria-label="Search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ml-2 rounded border border-gray-300 p-1"
        />
      </label>
      <ErrorBanner message={list.error ?? deleteError} />
      {list.loaded && (
        <ResourceTable
          rows={list.rows}
          columns={[
            { header: "Name", render: (c) => `${c.first_name} ${c.last_name}` },
            { header: "Club", render: (c) => clubName(c.club_id) },
            { header: "Role", render: (c) => (c.is_head_coach ? "Head coach" : "Assistant") },
          ]}
          rowLabel={(c) => `${c.first_name} ${c.last_name}`}
          onEdit={(c) => {
            setFormError(null);
            setDialog({ row: c });
          }}
          onDelete={confirmDelete}
          emptyMessage="No coaches yet."
        />
      )}
      <FormDialog open={dialog !== null} title={dialog?.row ? "Edit coach" : "New coach"}>
        {dialog && (
          <CoachForm
            key={dialog.row?.id ?? "new"}
            initial={dialog.row}
            clubs={clubsQuery.data ?? []}
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

- [ ] **Step 6: Add the route, run the tests, commit**

Add `<Route path="coaches" element={<CoachesPage />} />` to `App.tsx`.

Run: `npm test -- --run test/features/admin/coaches`
Expected: PASS, 4 tests.

```bash
git add frontend/src frontend/test
git commit -m "feat: coaches admin screen"
```

---

### Task 13: Groups

Group is the simplest FK resource: `club_id` + `name`.

**Files:**
- Create: `frontend/src/features/admin/groups/GroupsPage.tsx`
- Create: `frontend/src/features/admin/groups/GroupForm.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/test/features/admin/groups/GroupsPage.test.tsx`

**Interfaces:**
- Consumes: the Stage B layer; `GroupRead` (already exported), `makeGroup` (already exists), `makeClub`
- Produces: `GroupsPage`, `GroupForm`, `GroupBody = { name?: string; club_id?: number }`

- [ ] **Step 1: Write the failing tests**

Create `frontend/test/features/admin/groups/GroupsPage.test.tsx`:

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { makeClub, makeGroup } from "../../../fixtures";
import { api, server } from "../../../msw/server";
import { renderApp } from "../../../utils";

function mockBase(groups: unknown[] = []) {
  server.use(
    http.get(api("/groups/"), () => HttpResponse.json(groups)),
    http.get(api("/clubs/"), () =>
      HttpResponse.json([makeClub({ id: 1, name: "Star Gymnastics" })]),
    ),
  );
}

test("lists groups with their club", async () => {
  mockBase([makeGroup({ id: 3, name: "Zvezda RG", club_id: 1 })]);
  renderApp("/admin/groups");
  expect(await screen.findByText("Zvezda RG")).toBeInTheDocument();
  expect(screen.getByText("Star Gymnastics")).toBeInTheDocument();
});

test("creates a group", async () => {
  mockBase();
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/groups/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGroup(), { status: 201 });
    }),
  );
  renderApp("/admin/groups");
  await userEvent.click(await screen.findByRole("button", { name: "New group" }));
  await userEvent.type(screen.getByLabelText("Name"), "Junior Ensemble");
  await userEvent.selectOptions(screen.getByLabelText("Club"), "1");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(posted).toEqual({ name: "Junior Ensemble", club_id: 1 }));
});

test("edits a group name", async () => {
  mockBase([makeGroup({ id: 3, name: "Zvezda RG", club_id: 1 })]);
  let patched: Record<string, unknown> | null = null;
  server.use(
    http.patch(api("/groups/:groupId"), async ({ request }) => {
      patched = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGroup({ id: 3 }));
    }),
  );
  renderApp("/admin/groups");
  await userEvent.click(await screen.findByRole("button", { name: "Edit Zvezda RG" }));
  const name = screen.getByLabelText("Name");
  await userEvent.clear(name);
  await userEvent.type(name, "Zvezda Seniors");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(patched).toEqual({ name: "Zvezda Seniors" }));
});

test("surfaces a 409 when the group still has members", async () => {
  mockBase([makeGroup({ id: 3, name: "Zvezda RG", club_id: 1 })]);
  server.use(
    http.delete(api("/groups/:groupId"), () =>
      HttpResponse.json({ detail: "Cannot delete group with existing members" }, { status: 409 }),
    ),
  );
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/admin/groups");
  await userEvent.click(await screen.findByRole("button", { name: "Delete Zvezda RG" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("existing members");
  confirmSpy.mockRestore();
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm test -- --run test/features/admin/groups`
Expected: FAIL — no `/admin/groups` route.

- [ ] **Step 3: Write `GroupForm`**

Create `frontend/src/features/admin/groups/GroupForm.tsx`:

```tsx
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { ClubRead, GroupRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FkSelect } from "../components/FkSelect";

const groupSchema = z.object({
  name: z.string().trim().min(1, "Name is required"),
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

  const buildBody = (v: GroupFormValues): GroupBody => {
    const full: GroupBody = { name: v.name, club_id: Number(v.club_id) };
    if (!initial) return full;
    const body: GroupBody = {};
    if (dirtyFields.name) body.name = full.name;
    if (dirtyFields.club_id) body.club_id = full.club_id;
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
```

- [ ] **Step 4: Write `GroupsPage`**

Create `frontend/src/features/admin/groups/GroupsPage.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiDetail, client } from "../../../api/client";
import type { ClubRead, GroupRead } from "../../../api/types";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FormDialog } from "../components/FormDialog";
import { ResourceTable } from "../components/ResourceTable";
import { useResourceDelete } from "../hooks/useResourceDelete";
import { useResourceList } from "../hooks/useResourceList";
import { GroupForm, type GroupBody } from "./GroupForm";

export function GroupsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [dialog, setDialog] = useState<{ row: GroupRead | null } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const clubsQuery = useQuery({
    queryKey: ["clubs", {}],
    queryFn: async (): Promise<ClubRead[]> => {
      const { data, error } = await client.GET("/clubs/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
  });

  const list = useResourceList<GroupRead>({
    queryKey: ["groups", {}],
    fetchRows: async () => {
      const { data, error } = await client.GET("/groups/");
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    search,
    searchText: (g) => g.name,
  });

  const { confirmDelete, error: deleteError } = useResourceDelete<GroupRead>({
    queryKey: ["groups"],
    describe: (g) => `group "${g.name}"`,
    remove: async (g) => {
      const { error } = await client.DELETE("/groups/{group_id}", {
        params: { path: { group_id: g.id } },
      });
      if (error) throw new Error(apiDetail(error));
    },
  });

  const saveMutation = useMutation({
    mutationFn: async (body: GroupBody) => {
      const editingRow = dialog?.row ?? null;
      if (editingRow) {
        const { data, error } = await client.PATCH("/groups/{group_id}", {
          params: { path: { group_id: editingRow.id } },
          body,
        });
        if (error) throw new Error(apiDetail(error));
        return data;
      }
      const { data, error } = await client.POST("/groups/", {
        body: body as { name: string; club_id: number },
      });
      if (error) throw new Error(apiDetail(error));
      return data;
    },
    onSuccess: () => {
      setFormError(null);
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });

  const clubName = (id: number) => clubsQuery.data?.find((c) => c.id === id)?.name ?? "—";

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-xl font-bold">Groups</h1>
        <button
          type="button"
          onClick={() => {
            setFormError(null);
            setDialog({ row: null });
          }}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New group
        </button>
      </div>
      <label className="mb-3 block text-sm">
        Search
        <input
          aria-label="Search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ml-2 rounded border border-gray-300 p-1"
        />
      </label>
      <ErrorBanner message={list.error ?? deleteError} />
      {list.loaded && (
        <ResourceTable
          rows={list.rows}
          columns={[
            { header: "Name", render: (g) => g.name },
            { header: "Club", render: (g) => clubName(g.club_id) },
          ]}
          rowLabel={(g) => g.name}
          onEdit={(g) => {
            setFormError(null);
            setDialog({ row: g });
          }}
          onDelete={confirmDelete}
          emptyMessage="No groups yet."
        />
      )}
      <FormDialog open={dialog !== null} title={dialog?.row ? "Edit group" : "New group"}>
        {dialog && (
          <GroupForm
            key={dialog.row?.id ?? "new"}
            initial={dialog.row}
            clubs={clubsQuery.data ?? []}
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

- [ ] **Step 5: Add the route**

Add `<Route path="groups" element={<GroupsPage />} />` to `App.tsx`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `npm test -- --run test/features/admin/groups`
Expected: PASS, 4 tests.

- [ ] **Step 7: Full verification**

Run: `npm run build && npm test -- --run`
Expected: build succeeds; all frontend tests pass (78 pre-existing + ~44 new).

Then drive the real app end-to-end before declaring Phase 2 done: `make dev`, `make frontend`, and walk the dependency chain in the browser — create a district, a club in it, a coach, a group, a gymnast; edit one of each; try deleting the district while the club still exists and confirm the 409 message appears.

- [ ] **Step 8: Commit**

```bash
git add frontend/src frontend/test
git commit -m "feat: groups admin screen"
```

---

## Done criteria

- `/admin` reachable from the top nav; sidebar lists five resources in dependency order.
- Each of Districts, Clubs, Coaches, Groups, Gymnasts supports list, search, create, edit and delete.
- Edits send only dirty fields; an untouched nullable FK is never sent as `null`.
- Every 409 shows the API's own `detail` — inside the dialog for saves, on the list for deletes.
- `npm run build` clean; `npm test -- --run` green; the browser walkthrough above completed.
