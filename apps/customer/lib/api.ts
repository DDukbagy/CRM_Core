// lib/api.ts
import { config } from "./config";
import { supabase } from "./supabase";

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export class ApiError extends Error {
  status: number;
  body?: unknown;

  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function _getAccessToken(): Promise<string | null> {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

async function _doFetch(path: string, method: HttpMethod, headers: Record<string, string>, body?: unknown) {
  return fetch(`${config.apiBaseUrl}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
}

export async function apiFetch<T>(
  path: string,
  options?: {
    method?: HttpMethod;
    body?: unknown;
    headers?: Record<string, string>;
    requireAuth?: boolean;
  }
): Promise<T> {
  const method = options?.method ?? "GET";
  const requireAuth = options?.requireAuth ?? true;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers ?? {}),
  };

  if (requireAuth) {
    const token = await _getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let res = await _doFetch(path, method, headers, options?.body);

  // 토큰 만료(401) 시 한 번 갱신 후 재시도
  if (res.status === 401 && requireAuth) {
    const { data, error } = await supabase.auth.refreshSession();
    if (!error && data.session?.access_token) {
      headers.Authorization = `Bearer ${data.session.access_token}`;
      res = await _doFetch(path, method, headers, options?.body);
    } else {
      await supabase.auth.signOut();
      throw new ApiError("Session expired", 401);
    }
  }

  const text = await res.text();
  let json: unknown = undefined;
  try {
    json = text ? JSON.parse(text) : undefined;
  } catch {
    json = text;
  }

  if (!res.ok) {
    throw new ApiError(`API Error (${res.status})`, res.status, json);
  }

  return json as T;
}
