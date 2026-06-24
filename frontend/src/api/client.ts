// Thin, typed wrapper around the backend REST API + a small data-fetching hook.
// Base URL comes from Vite env (VITE_API_BASE_URL); defaults to "/api" so you
// can proxy to the Python backend in dev.

import { useCallback, useEffect, useRef, useState, type DependencyList } from "react";
import type {
  DashboardData,
  DataHealth,
  Run,
  RunConfig,
  RunSummary,
  Shortlist,
  UniverseId,
} from "./types";

const API_BASE =
  (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env
    ?.VITE_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  status: number;
  body?: unknown;
  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      ...init,
    });
  } catch (err) {
    throw new ApiError(
      "Could not reach the backend. Is the API server running?",
      0,
      err,
    );
  }

  const text = await res.text();
  const data = text ? safeJson(text) : undefined;

  if (!res.ok) {
    const detail =
      data && typeof data === "object" && data !== null && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : "";
    throw new ApiError(detail || res.statusText || `Request failed (${res.status})`, res.status, data);
  }
  return data as T;
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export const api = {
  getDashboard: () => request<DashboardData>("/dashboard"),

  listRuns: () => request<RunSummary[]>("/runs"),
  getRun: (id: string) => request<Run>(`/runs/${encodeURIComponent(id)}`),
  createRun: (config: RunConfig) =>
    request<Run>("/runs", { method: "POST", body: JSON.stringify(config) }),
  cancelRun: (id: string) =>
    request<RunSummary>(`/runs/${encodeURIComponent(id)}/cancel`, { method: "POST" }),

  getShortlist: (params?: { universe?: UniverseId; top?: number }) => {
    const q = new URLSearchParams();
    if (params?.universe) q.set("universe", params.universe);
    if (params?.top) q.set("top", String(params.top));
    const qs = q.toString();
    return request<Shortlist>(`/shortlist${qs ? `?${qs}` : ""}`);
  },

  getDataHealth: () => request<DataHealth>("/data-health"),
};

// ---------------------------------------------------------------------------
// useApi: minimal async-data hook (loading / error / data / refetch)
// ---------------------------------------------------------------------------

export interface AsyncState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  refetch: () => void;
}

export function useApi<T>(fn: () => Promise<T>, deps: DependencyList = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  // Keep the latest fn without forcing it into the dependency array.
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    fnRef
      .current()
      .then((res) => {
        if (active) setData(res);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err : new Error(String(err)));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const refetch = useCallback(() => setNonce((n) => n + 1), []);
  return { data, error, loading, refetch };
}
