/// <reference types="vite/client" />

export type RuntimeEnv = { VITE_API_BASE_URL?: string; [key: string]: unknown };

export function apiBaseUrl(
  env: RuntimeEnv = import.meta.env,
  origin: string = window.location.origin,
): string {
  return env.VITE_API_BASE_URL?.trim() || origin;
}

export async function apiFetch<T>(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<T> {
  const raw = typeof input === "string" ? input : input.toString();
  const url = raw.startsWith("/") ? new URL(raw, apiBaseUrl()).toString() : raw;
  const response = await fetch(url, init);
  const body = [204, 205, 304].includes(response.status)
    ? null
    : await response.text();
  return {
    data: body ? JSON.parse(body) : {},
    status: response.status,
    headers: response.headers,
  } as T;
}
