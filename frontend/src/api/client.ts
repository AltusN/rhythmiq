import createClient from "openapi-fetch";
import type { paths } from "./schema";

/** Vitest runs in Node, where fetch needs absolute URLs (and MSW matches them). */
export const API_BASE =
  import.meta.env.MODE === "test" ? "http://localhost/api" : "/api";

export const client = createClient<paths>({ baseUrl: API_BASE });

/** Pydantic v2 serializes Decimal fields as JSON strings ("7.30"); normalize. */
export function toNum(v: number | string | null | undefined): number {
  if (v === null || v === undefined || v === "") return 0;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isNaN(n) ? 0 : n;
}

/** Format a number for a Decimal field ("7.3" -> "7.30"). */
export function toDec(n: number): string {
  return n.toFixed(2);
}

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
