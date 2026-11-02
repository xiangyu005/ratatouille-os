/**
 * Typed CORE client.
 *
 * Contract rules (`docs/22-01` §7.1, `docs/22` §2):
 * - CORE's OpenAPI is the only source of types (`./schema.d.ts`, generated).
 * - Every request carries `x-request-id`.
 * - Errors are mapped to `CoreError` with CORE's stable `code`, never a raw
 *   traceback.
 */

import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";

const DEFAULT_BASE = "http://127.0.0.1:8001";

export const CORE_HTTP = (import.meta.env.VITE_CORE_BASE ?? DEFAULT_BASE).replace(/\/$/, "");
export const CORE_WS = `${CORE_HTTP.replace(/^http/, "ws")}/ws/events`;

const requestIdMiddleware: Middleware = {
  onRequest({ request }) {
    if (!request.headers.has("x-request-id")) {
      request.headers.set("x-request-id", crypto.randomUUID());
    }
    return request;
  },
};

export const core = createClient<paths>({ baseUrl: CORE_HTTP });
core.use(requestIdMiddleware);

export class CoreError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;

  constructor(
    code: string,
    message: string,
    status: number,
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "CoreError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

interface ErrorEnvelope {
  error?: { code?: string; message?: string; details?: Record<string, unknown> };
  detail?: unknown;
}

function toCoreError(result: { error?: unknown; response: Response }): CoreError {
  const body = (result.error ?? {}) as ErrorEnvelope;
  const code = body.error?.code ?? "HTTP_ERROR";
  const message = body.error?.message ?? `CORE responded with ${result.response.status}`;
  return new CoreError(code, message, result.response.status, body.error?.details ?? {});
}

/** Return the payload or throw a `CoreError` carrying CORE's error code. */
export function unwrap<T>(result: { data?: unknown; error?: unknown; response: Response }): T {
  if (result.response.ok && result.data !== undefined) {
    return result.data as T;
  }
  throw toCoreError(result);
}
