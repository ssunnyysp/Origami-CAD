import type { FlasherGeometry, FlasherParams, FlasherPreset } from "../model/types";

// Same-origin paths: the Vite dev server proxies /api to the Python backend
// (see vite.config.ts), so no base URL or CORS handling is needed here.

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(`${init?.method ?? "GET"} ${url} failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchPresets(): Promise<FlasherPreset[]> {
  return getJson("/api/presets");
}

export function fetchGeometry(params: FlasherParams): Promise<FlasherGeometry> {
  return getJson("/api/flasher/geometry", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}
