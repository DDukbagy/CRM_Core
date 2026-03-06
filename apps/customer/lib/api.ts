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
    const {
      data: { session },
    } = await supabase.auth.getSession();
    const token = session?.access_token;
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${config.apiBaseUrl}${path}`, {
    method,
    headers,
    body: options?.body ? JSON.stringify(options.body) : undefined,
  });

  const text = await res.text();
  let json: unknown = undefined;
  try {
    json = text ? JSON.parse(text) : undefined;
  } catch {
    json = text;
  }

  if (res.status === 401) {
    await supabase.auth.signOut();
  }

  if (!res.ok) {
    throw new ApiError(`API Error (${res.status})`, res.status, json);
  }

  return json as T;
}
