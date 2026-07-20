# Gymnast Ethnicity + GSA Number Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two optional fields to `Gymnast` — `ethnicity` (native Postgres enum) and `gsa_number` (unique nullable string) — through model, migration, schemas, router and frontend form.

**Architecture:** Follows the repo's existing per-resource shape: enum in `app/models.py` beside the other `StrEnum`s, columns on `Gymnast`, fields added to all three Pydantic schemas, no new router handlers (the existing `model_dump()` write path carries new fields automatically), and the two fields added to the shared create/edit `GymnastForm.tsx`.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Postgres, pytest; React 19 + React Hook Form + Zod + Vitest/Testing Library.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-20-gymnast-ethnicity-gsa-number-design.md`.
- Branch: `feature/gymnast-ethnicity-gsa` (already created, spec already committed).
- Commit subjects MUST start with `feat:` / `fix:` / `chore:` / `docs:` / `test:`.
- Backend commands run from `backend/` with the venv active; `make` targets run from the repo root.
- The schema is NEVER auto-created on startup. `alembic upgrade head` is the only way to build it. Backend tests therefore FAIL until the migration exists and is applied — the migration ships in Task 1, not at the end.
- Ethnicity values, exactly: `white`, `black`, `coloured`, `indian`, `prefer_not_to_say`.
- `ethnicity` is NOT displayed in the gymnasts roster table. It is form-only.
- Do not modify `make_gymnast` in `test/conftest.py` — both new columns are nullable and existing callers must keep working unchanged.

---

### Task 1: Model, enum, and migration

**Files:**
- Modify: `backend/app/models.py` (enum block ~line 29-96; `Gymnast` class ~line 331-365)
- Create: `backend/migrations/versions/<generated>_add_ethnicity_and_gsa_number_to_gymnasts.py`
- Test: `backend/test/test_models/test_gymnast.py`

**Interfaces:**
- Produces: `app.models.Ethnicity` (a `StrEnum` with members `white`, `black`, `coloured`, `indian`, `prefer_not_to_say`); `Gymnast.ethnicity: Ethnicity | None`; `Gymnast.gsa_number: str | None`; unique constraint named `uq_gymnast_gsa_number`.

- [ ] **Step 1: Add the enum to `app/models.py`**

Place it immediately after the existing `PenaltyJudgeRole` enum (ends ~line 96), before `class Judge(Base)`:

```python
class Ethnicity(StrEnum):
    """
    South African statutory demographic categories, plus an explicit decline option.

    NULL and `prefer_not_to_say` are different states: NULL means the question was
    never asked or the answer is unknown, `prefer_not_to_say` means the gymnast was
    asked and declined. Adding a value here later needs a hand-written
    `ALTER TYPE ethnicity ADD VALUE ...` migration -- autogenerate will not see it.
    """

    white = "white"
    black = "black"
    coloured = "coloured"
    indian = "indian"
    prefer_not_to_say = "prefer_not_to_say"
```

- [ ] **Step 2: Add the two columns to `Gymnast`**

In `class Gymnast(Base)`, after the `country_code` column (~line 353):

```python
    ethnicity: Mapped[Ethnicity | None] = mapped_column(Enum(Ethnicity), nullable=True)
    gsa_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
```

Then add to the existing `__table_args__` tuple, after `uq_gymnast_identity`:

```python
        UniqueConstraint("gsa_number", name="uq_gymnast_gsa_number"),
```

And append to the `Gymnast` class docstring, after the existing "Identity is ..." sentence:

```
    gsa_number is an optional Gymnastics SA membership number. It is unique when
    present but does NOT replace uq_gymnast_identity -- many gymnasts have no GSA
    number, and NULLs do not collide under a Postgres unique constraint.
```

- [ ] **Step 3: Generate the migration**

From the repo root:

```bash
make migration name="add_ethnicity_and_gsa_number_to_gymnasts"
```

- [ ] **Step 4: Read the generated migration before applying it**

Open the new file under `backend/migrations/versions/`. Confirm `upgrade()` contains
roughly:

```python
    op.add_column("gymnasts", sa.Column("ethnicity", sa.Enum("white", "black", "coloured", "indian", "prefer_not_to_say", name="ethnicity"), nullable=True))
    op.add_column("gymnasts", sa.Column("gsa_number", sa.String(length=32), nullable=True))
    op.create_unique_constraint("uq_gymnast_gsa_number", "gymnasts", ["gsa_number"])
```

Two things to fix by hand if autogenerate got them wrong:
1. If `downgrade()` drops the columns but does NOT drop the enum type, add as the last
   line of `downgrade()`:
   ```python
   sa.Enum(name="ethnicity").drop(op.get_bind(), checkfirst=False)
   ```
   Postgres leaves an orphaned type otherwise, and a later re-upgrade fails with
   "type ethnicity already exists".
2. If the file contains unrelated diffs (drift from other work), delete those lines —
   this migration touches only the `gymnasts` table.

- [ ] **Step 5: Apply the migration**

From the repo root:

```bash
make dev
```

Expected: alembic runs and ends at the new revision, no error.

- [ ] **Step 6: Write the failing model tests**

Append to `backend/test/test_models/test_gymnast.py`. Add `Ethnicity` to the existing
`from app.models import ...` line so it reads
`from app.models import Ethnicity, Gymnast, Meet, MeetEntry, Routine`:

```python
@pytest.mark.parametrize("value", list(Ethnicity))
def test_gymnast_accepts_every_ethnicity_value(db_session, value):
    gymnast = Gymnast(
        first_name="Ethni",
        last_name=f"City{value.name}",
        date_of_birth=date(2010, 1, 1),
        ethnicity=value,
    )
    db_session.add(gymnast)
    db_session.commit()

    stored = db_session.query(Gymnast).filter_by(last_name=f"City{value.name}").one()
    assert stored.ethnicity is value


def test_gymnast_ethnicity_and_gsa_number_default_to_null(db_session):
    gymnast = make_gymnast(db_session, first_name="Nulla", last_name="Fields")

    assert gymnast.ethnicity is None
    assert gymnast.gsa_number is None


def test_gymnast_gsa_number_persists(db_session):
    gymnast = make_gymnast(db_session, first_name="Member", last_name="One")
    gymnast.gsa_number = "GSA-12345"
    db_session.commit()

    assert db_session.query(Gymnast).filter_by(gsa_number="GSA-12345").one().id == gymnast.id


def test_gymnast_duplicate_gsa_number_raises_error(db_session):
    make_gymnast(db_session, first_name="First", last_name="Holder")
    db_session.query(Gymnast).filter_by(last_name="Holder").one().gsa_number = "GSA-999"
    db_session.flush()

    second = make_gymnast(db_session, first_name="Second", last_name="Holder")
    second.gsa_number = "GSA-999"
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_gymnast_multiple_null_gsa_numbers_allowed(db_session):
    make_gymnast(db_session, first_name="Anon", last_name="OneNull")
    make_gymnast(db_session, first_name="Anon", last_name="TwoNull")
    db_session.commit()

    assert db_session.query(Gymnast).filter_by(gsa_number=None).count() >= 2
```

- [ ] **Step 7: Run the model tests**

```bash
cd backend && pytest test/test_models/test_gymnast.py -v
```

Expected: all PASS (the migration from Step 5 is already applied). If
`test_gymnast_accepts_every_ethnicity_value` errors with `type "ethnicity" does not
exist`, the migration did not apply — re-check Step 5.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models.py backend/migrations/versions/ backend/test/test_models/test_gymnast.py
git commit -m "feat: add ethnicity and gsa_number columns to gymnasts

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Pydantic schemas

**Files:**
- Modify: `backend/app/schemas/gymnast.py`
- Test: `backend/test/test_schemas/test_gymnast_schema.py`

**Interfaces:**
- Consumes: `app.models.Ethnicity` from Task 1.
- Produces: `ethnicity: Ethnicity | None` and `gsa_number: str | None` on `GymnastCreate`, `GymnastUpdate` and `GymnastRead`; a `normalize_gsa_number` validator on Create and Update that strips and maps `""` to `None`.

- [ ] **Step 1: Write the failing schema tests**

Append to `backend/test/test_schemas/test_gymnast_schema.py`. Make sure the file's
imports include `pytest`, `ValidationError` from `pydantic`, `Ethnicity` from
`app.models`, and `GymnastCreate` / `GymnastUpdate` from `app.schemas.gymnast`:

```python
def test_gymnast_create_accepts_ethnicity_and_gsa_number():
    schema = GymnastCreate(
        first_name="Dina",
        last_name="Averina",
        ethnicity="coloured",
        gsa_number="GSA-42",
    )

    assert schema.ethnicity is Ethnicity.coloured
    assert schema.gsa_number == "GSA-42"


def test_gymnast_create_defaults_new_fields_to_none():
    schema = GymnastCreate(first_name="Dina", last_name="Averina")

    assert schema.ethnicity is None
    assert schema.gsa_number is None


def test_gymnast_create_rejects_unknown_ethnicity():
    with pytest.raises(ValidationError):
        GymnastCreate(first_name="Dina", last_name="Averina", ethnicity="martian")


def test_gymnast_create_blank_gsa_number_becomes_none():
    schema = GymnastCreate(first_name="Dina", last_name="Averina", gsa_number="   ")

    assert schema.gsa_number is None


def test_gymnast_create_strips_gsa_number_whitespace():
    schema = GymnastCreate(first_name="Dina", last_name="Averina", gsa_number="  GSA-7 ")

    assert schema.gsa_number == "GSA-7"


def test_gymnast_update_blank_gsa_number_becomes_none():
    schema = GymnastUpdate(gsa_number="")

    assert schema.gsa_number is None


def test_gymnast_update_omits_untouched_new_fields():
    schema = GymnastUpdate(first_name="Dina")

    assert schema.model_dump(exclude_unset=True) == {"first_name": "Dina"}
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && pytest test/test_schemas/test_gymnast_schema.py -v
```

Expected: FAIL. The new-field tests fail because Pydantic ignores unknown kwargs, so
`schema.ethnicity` raises `AttributeError`, and `rejects_unknown_ethnicity` fails
because no `ValidationError` is raised.

- [ ] **Step 3: Add the fields and validator to the schemas**

In `backend/app/schemas/gymnast.py`, extend the imports:

```python
from app.models import Ethnicity
```

Add to **`GymnastCreate`**, after `country_code`:

```python
    # Optional demographic field; None means never asked, Ethnicity.prefer_not_to_say
    # means asked and declined.
    ethnicity: Ethnicity | None = None
    # Optional Gymnastics SA membership number; unique when present.
    gsa_number: str | None = Field(None, max_length=32)
```

Add the identical two field declarations to **`GymnastUpdate`** and to **`GymnastRead`**
(on `GymnastRead` the comments are unnecessary — just the two annotated fields).

The normalisation is shared by `GymnastCreate` and `GymnastUpdate` via a mixin, NOT
copied into both classes. Define it above `GymnastCreate`:

```python
class _GsaNumberNormalizer:
    """
    Shared by GymnastCreate and GymnastUpdate.

    "" would otherwise be stored literally and collide with the next blank entry
    under uq_gymnast_gsa_number, so empty input becomes NULL.
    """

    @field_validator("gsa_number", mode="before")
    @classmethod
    def normalize_gsa_number(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v
```

Then change both class declarations, mixin first in the MRO:

```python
class GymnastCreate(_GsaNumberNormalizer, BaseModel):
class GymnastUpdate(_GsaNumberNormalizer, BaseModel):
```

`GymnastRead` does NOT get the mixin — it reads already-normalised values out of the
database.

This idiom is verified working on the repo's Pydantic 2.13.4: a plain (non-`BaseModel`)
mixin holding a decorated `field_validator` is collected during model construction.

Note this deliberately departs from the surrounding `strip_whitespace` /
`validate_country_code` validators, which ARE duplicated across Create and Update. Do not
"fix" those to match, and do not fold them into the mixin — that refactor is out of scope
for this feature. See the DECISION line in the progress ledger.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd backend && pytest test/test_schemas/test_gymnast_schema.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/gymnast.py backend/test/test_schemas/test_gymnast_schema.py
git commit -m "feat: accept ethnicity and gsa_number in gymnast schemas

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Router 409 message and router tests

**Files:**
- Modify: `backend/app/routers/gymnast.py` (docstring; the two `except IntegrityError` blocks at ~line 56-61 and ~line 130-135)
- Test: `backend/test/test_routers/test_gymnast_router.py`

**Interfaces:**
- Consumes: schemas from Task 2.
- Produces: no new symbols. Create and update handlers stay otherwise unchanged.

**Why this task exists:** both `except IntegrityError` blocks hardcode the detail
`"Gymnast with name '<first> <last>' already exists"`. A duplicate `gsa_number` now also
raises `IntegrityError`, so without this change the API returns a 409 whose message
blames the name — and the frontend renders `detail` verbatim in its error banner. The
handler must tell the two constraints apart.

- [ ] **Step 1: Write the failing router tests**

Append to `backend/test/test_routers/test_gymnast_router.py`:

```python
def test_create_gymnast_with_ethnicity_and_gsa_number(client, db_session):
    response = client.post(
        "/gymnasts",
        json={
            "first_name": "Dina",
            "last_name": "Averina",
            "date_of_birth": "2008-12-01",
            "ethnicity": "indian",
            "gsa_number": "GSA-1001",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["ethnicity"] == "indian"
    assert body["gsa_number"] == "GSA-1001"


def test_create_gymnast_without_new_fields_returns_nulls(client, db_session):
    response = client.post(
        "/gymnasts",
        json={"first_name": "Dina", "last_name": "Averina", "date_of_birth": "2008-12-01"},
    )

    assert response.status_code == 201
    assert response.json()["ethnicity"] is None
    assert response.json()["gsa_number"] is None


def test_create_gymnast_rejects_unknown_ethnicity(client, db_session):
    response = client.post(
        "/gymnasts",
        json={"first_name": "Dina", "last_name": "Averina", "ethnicity": "martian"},
    )

    assert response.status_code == 422


def test_update_gymnast_ethnicity_and_gsa_number(client, db_session):
    gymnast = make_gymnast(db_session, first_name="Patch", last_name="Target")

    response = client.patch(
        f"/gymnasts/{gymnast.id}",
        json={"ethnicity": "prefer_not_to_say", "gsa_number": "GSA-2002"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ethnicity"] == "prefer_not_to_say"
    assert body["gsa_number"] == "GSA-2002"


def test_update_gymnast_can_clear_gsa_number(client, db_session):
    gymnast = make_gymnast(db_session, first_name="Clear", last_name="Target")

    response = client.patch(f"/gymnasts/{gymnast.id}", json={"gsa_number": ""})

    assert response.status_code == 200
    assert response.json()["gsa_number"] is None
```

The duplicate case gets its own test function. The router-test fixture shares one
transaction, so the router's `db.rollback()` on the 409 path would undo any commits made
earlier in the same test — this test therefore asserts only on the 409 response:

```python
def test_create_gymnast_duplicate_gsa_number_returns_409(client, db_session):
    first = client.post(
        "/gymnasts",
        json={"first_name": "Owner", "last_name": "OfNumber", "gsa_number": "GSA-DUP"},
    )
    assert first.status_code == 201

    response = client.post(
        "/gymnasts",
        json={"first_name": "Other", "last_name": "Person", "gsa_number": "GSA-DUP"},
    )

    assert response.status_code == 409
    assert "GSA" in response.json()["detail"]
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && pytest test/test_routers/test_gymnast_router.py -v
```

Expected: the create/update tests PASS already (the schemas from Task 2 flow through
`model_dump()` untouched). `test_create_gymnast_duplicate_gsa_number_returns_409` FAILS
on the last assertion — the status is 409, but the detail reads
`Gymnast with name 'Other Person' already exists`, which contains no "GSA".

- [ ] **Step 3: Make the 409 detail identify the violated constraint**

In `backend/app/routers/gymnast.py`, add this helper below the `router = APIRouter(...)`
line:

```python
def _conflict_detail(exc: IntegrityError, payload: GymnastCreate | GymnastUpdate) -> str:
    """Name the constraint the write actually violated, not just the identity one."""
    if "uq_gymnast_gsa_number" in str(exc.orig):
        return f"A gymnast with GSA number '{payload.gsa_number}' already exists"
    return f"Gymnast with name '{payload.first_name} {payload.last_name}' already exists"
```

Then change **both** `except IntegrityError:` blocks (create ~line 56, update ~line 130)
to capture the exception and use the helper:

```python
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_conflict_detail(exc, payload),
        ) from None
```

Leave the DELETE handler's `except IntegrityError:` block (~line 150) exactly as it is —
it has a different message and no payload.

- [ ] **Step 4: Document it in the router docstring**

Add to the "Design notes" list in the module docstring at the top of
`backend/app/routers/gymnast.py`:

```
- 409s: two different unique constraints can fire (identity and gsa_number), so
  _conflict_detail inspects the IntegrityError to report the right one. The
  frontend renders `detail` verbatim, so a wrong message is user-visible.
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd backend && pytest test/test_routers/test_gymnast_router.py -v
```

Expected: all PASS.

- [ ] **Step 6: Run the whole backend suite and the linter**

```bash
cd backend && pytest && ruff check . && ruff format .
```

Expected: full suite green, ruff reports no remaining issues.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/gymnast.py backend/test/test_routers/test_gymnast_router.py
git commit -m "feat: report the violated constraint in gymnast 409 responses

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Regenerate types and add the fields to the gymnast form

**Files:**
- Modify: `frontend/src/api/schema.d.ts` (generated — do not hand-edit)
- Modify: `frontend/src/features/admin/gymnasts/GymnastForm.tsx`
- Modify: `frontend/test/fixtures.ts`
- Test: `frontend/test/features/admin/gymnasts/GymnastsPage.test.tsx`

**Interfaces:**
- Consumes: the OpenAPI schema produced by Tasks 1-3.
- Produces: `GymnastBody` gains `ethnicity?: GymnastRead["ethnicity"]` and `gsa_number?: string | null`; the form renders controls with accessible names `Ethnicity` and `GSA number`.

**Test-file conventions in this repo — follow them exactly:**
- Tests are top-level `test("...", async () => {})`, NOT wrapped in `describe`.
- Rendering is `renderApp("/admin/gymnasts")` from `frontend/test/utils`. There is no
  `createWrapper` helper and the page component is not rendered directly.
- API mocking is MSW via `server.use(http.get(api("/gymnasts/"), ...))`; `mockBase()` at
  the top of the file sets up the gymnasts/clubs/groups GETs.
- Row fixtures come from `makeGymnast({...})` in `frontend/test/fixtures.ts`.

- [ ] **Step 1: Regenerate the API types**

The backend must be importable for this. From the repo root:

```bash
make types
```

Verify:

```bash
grep -n "gsa_number" frontend/src/api/schema.d.ts
```

Expected: at least three hits (Create, Update, Read). Also confirm the generated
`ethnicity` type is a union of the five string literals plus `null`.

- [ ] **Step 2: Add the new fields to the test fixture**

In `frontend/test/fixtures.ts`, add to the object returned by `makeGymnast` (after
`country_code: null`, ~line 41), before the `...overrides` spread:

```ts
    ethnicity: null,
    gsa_number: null,
```

- [ ] **Step 3: Write the failing form test**

Append to `frontend/test/features/admin/gymnasts/GymnastsPage.test.tsx`. This captures
the POST body through MSW, matching how the file already mocks endpoints:

```tsx
test("submits ethnicity and GSA number when creating a gymnast", async () => {
  mockBase([]);
  let posted: Record<string, unknown> | null = null;
  server.use(
    http.post(api("/gymnasts/"), async ({ request }) => {
      posted = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(makeGymnast({ id: 99 }), { status: 201 });
    }),
  );
  renderApp("/admin/gymnasts");

  await userEvent.click(await screen.findByRole("button", { name: "New gymnast" }));
  await userEvent.type(screen.getByLabelText("First name"), "Dina");
  await userEvent.type(screen.getByLabelText("Last name"), "Averina");
  await userEvent.selectOptions(screen.getByLabelText("Ethnicity"), "indian");
  await userEvent.type(screen.getByLabelText("GSA number"), "GSA-1001");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() =>
    expect(posted).toMatchObject({ ethnicity: "indian", gsa_number: "GSA-1001" }),
  );
});

test("ethnicity defaults to a blank not-set option", async () => {
  mockBase([]);
  renderApp("/admin/gymnasts");

  await userEvent.click(await screen.findByRole("button", { name: "New gymnast" }));

  const select = screen.getByLabelText("Ethnicity") as HTMLSelectElement;
  expect(select.value).toBe("");
  // 5 enum values + the blank "not set" option
  expect(within(select).getAllByRole("option")).toHaveLength(6);
});
```

Before running: confirm the accessible names `"New gymnast"` and `"Save"` against
`GymnastsPage.tsx` / `GymnastForm.tsx` and adjust the two `name:` strings if they differ.

- [ ] **Step 4: Run the tests to verify they fail**

```bash
cd frontend && npm test -- --run GymnastsPage
```

Expected: FAIL with "Unable to find a label with the text of: Ethnicity".

- [ ] **Step 5: Add both fields to `GymnastForm.tsx`**

Extend `gymnastSchema` (after `country_code`, ~line 23). Using `z.enum` rather than
`z.string()` means the form value narrows to the generated union without a cast:

```tsx
  ethnicity: z.enum(["", "white", "black", "coloured", "indian", "prefer_not_to_say"]),
  gsa_number: z.string().trim().max(32, "At most 32 characters"),
```

Extend the `GymnastBody` type (~line 33). `ethnicity` MUST be typed from the generated
schema, not as `string`: `body` is handed straight to the typed `client.PATCH` call in
`GymnastsPage.tsx`, and a plain `string` will not assign to the generated literal union:

```tsx
  ethnicity?: GymnastRead["ethnicity"];
  gsa_number?: string | null;
```

Extend `defaultValues` (~line 64):

```tsx
      ethnicity: initial?.ethnicity ?? "",
      gsa_number: initial?.gsa_number ?? "",
```

Extend the `full` object inside `buildBody` (~line 110):

```tsx
      ethnicity: v.ethnicity === "" ? null : v.ethnicity,
      gsa_number: toText(v.gsa_number),
```

Add the option list above the `GymnastForm` component, beside the other module-level
constants:

```tsx
/** Mirrors app.models.Ethnicity. "" means not set (NULL); prefer_not_to_say is a real
 *  stored value meaning the gymnast was asked and declined. */
const ETHNICITY_OPTIONS = [
  { value: "white", label: "White" },
  { value: "black", label: "Black" },
  { value: "coloured", label: "Coloured" },
  { value: "indian", label: "Indian" },
  { value: "prefer_not_to_say", label: "Prefer not to say" },
] as const;
```

Add the two controls in the JSX, immediately after the closing `</label>` of the country
code field (~line 181) and before `<div className="flex justify-end gap-2">`:

```tsx
      <label className="text-sm">
        Ethnicity
        <select {...register("ethnicity")} aria-label="Ethnicity" className={fieldClass}>
          <option value="">— not set —</option>
          {ETHNICITY_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      <label className="text-sm">
        GSA number
        <input {...register("gsa_number")} aria-label="GSA number" className={fieldClass} />
        {errors.gsa_number && (
          <span className="text-xs text-red-700">{errors.gsa_number.message}</span>
        )}
      </label>
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd frontend && npm test -- --run GymnastsPage
```

Expected: PASS.

- [ ] **Step 7: Typecheck and build**

```bash
cd frontend && npm run build
```

Expected: no TypeScript errors. If `ethnicity` reports a type mismatch on the PATCH
`body`, the `GymnastBody` field was typed as `string` instead of
`GymnastRead["ethnicity"]` — fix that rather than casting at the call site.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api/schema.d.ts frontend/src/features/admin/gymnasts/GymnastForm.tsx frontend/test/fixtures.ts frontend/test/features/admin/gymnasts/GymnastsPage.test.tsx
git commit -m "feat: capture ethnicity and GSA number on the gymnast form

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: GSA number column in the roster table

**Files:**
- Modify: `frontend/src/features/admin/gymnasts/GymnastsPage.tsx` (columns array, ~line 153-158)
- Test: `frontend/test/features/admin/gymnasts/GymnastsPage.test.tsx`

**Interfaces:**
- Consumes: `GymnastRead.gsa_number` from Task 4's regenerated types.
- Produces: nothing consumed by later tasks.

**Known regression this task must fix:** the existing test `"shows an em dash for a
gymnast with no club"` asserts `screen.getByText("—")` finds exactly one em dash, and its
comment says dob and country are filled in so the club cell is the only one. Adding a GSA
column puts a second em dash on that row, so `getByText` throws "found multiple
elements". Step 1 fixes that fixture in the same change that introduces the column.

- [ ] **Step 1: Update the existing em-dash test's fixture**

In `frontend/test/features/admin/gymnasts/GymnastsPage.test.tsx`, in the test
`"shows an em dash for a gymnast with no club"`, add `gsa_number` to the `makeGymnast`
call so the club cell remains the only em dash, and extend the comment:

```tsx
  // dob, country and GSA number are filled in so the club cell is the only em dash.
  mockBase([
    makeGymnast({
      id: 11,
      first_name: "Mia",
      last_name: "Nel",
      club_id: null,
      date_of_birth: "2012-08-19",
      country_code: "RSA",
      gsa_number: "GSA-311",
    }),
  ]);
```

- [ ] **Step 2: Write the failing column tests**

Append to the same file:

```tsx
test("shows the GSA number column, with an em dash when unset", async () => {
  mockBase([
    makeGymnast({ id: 10, first_name: "Anna", last_name: "Botha", gsa_number: "GSA-500" }),
  ]);
  renderApp("/admin/gymnasts");

  expect(
    await screen.findByRole("columnheader", { name: "GSA number" }),
  ).toBeInTheDocument();
  expect(screen.getByText("GSA-500")).toBeInTheDocument();
});

test("does not show ethnicity in the roster table", async () => {
  mockBase([makeGymnast({ id: 10, first_name: "Anna", last_name: "Botha" })]);
  renderApp("/admin/gymnasts");

  await screen.findByRole("columnheader", { name: "GSA number" });
  expect(
    screen.queryByRole("columnheader", { name: /ethnicity/i }),
  ).not.toBeInTheDocument();
});
```

The second test guards the spec's deliberate decision that ethnicity is demographic data
with no place on a screen visible around a meet venue.

- [ ] **Step 3: Run the tests to verify they fail**

```bash
cd frontend && npm test -- --run GymnastsPage
```

Expected: FAIL — no columnheader named "GSA number".

- [ ] **Step 4: Add the column**

In `frontend/src/features/admin/gymnasts/GymnastsPage.tsx`, add to the `columns` array
immediately after the existing Country entry (~line 157):

```tsx
            { header: "GSA number", render: (g) => g.gsa_number ?? "—" },
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd frontend && npm test -- --run GymnastsPage
```

Expected: PASS, including the pre-existing em-dash test fixed in Step 1.

- [ ] **Step 6: Run the full frontend suite and build**

```bash
cd frontend && npm test -- --run && npm run build
```

Expected: all tests pass, build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/admin/gymnasts/GymnastsPage.tsx frontend/test/features/admin/gymnasts/GymnastsPage.test.tsx
git commit -m "feat: show GSA number in the gymnasts roster table

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final verification

- [ ] From the repo root: `make test` — full backend suite green.
- [ ] From `frontend/`: `npm test -- --run` — full frontend suite green.
- [ ] From `backend/`: `ruff check .` — clean.
- [ ] `git status` — no uncommitted changes, no stray migration files.
