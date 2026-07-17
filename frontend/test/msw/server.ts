import { setupServer } from "msw/node";

export const server = setupServer();

/** Absolute test URL for an API path: api("/meets/") */
export const api = (path: string) => `http://localhost/api${path}`;
