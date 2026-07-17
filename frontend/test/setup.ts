import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach } from "vitest";
import { server } from "./msw/server";

// NOTE: listen() runs at module-eval time (not inside beforeAll). openapi-fetch's
// createClient() captures `globalThis.fetch` as a default parameter when
// `src/api/client.ts` is first imported (module-collection phase, which happens
// before Vitest runs any beforeAll hook). If listen() ran inside beforeAll, MSW
// would patch `globalThis.fetch` too late: the already-created `client` singleton
// would keep holding the pre-patch fetch reference and its requests would hit the
// real network (ECONNREFUSED) instead of MSW handlers. Calling listen() here,
// synchronously during setupFiles evaluation, guarantees the patch is in place
// before any test file (and therefore api/client.ts) is imported.
server.listen({ onUnhandledRequest: "error" });
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
