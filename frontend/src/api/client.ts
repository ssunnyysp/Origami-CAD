import type {
  CreasePattern,
  FlasherGeometry,
  FlasherParams,
  FlasherPreset,
  FoldImportResponse,
} from "../model/types";

// Same-origin paths: the Vite dev server proxies /api to the Python backend
// (see vite.config.ts), so no base URL or CORS handling is needed here.

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    // Both /api/fold/* endpoints put a human-readable message in `detail` on
    // a 422; surface that instead of just the status code where possible.
    let detail: string | undefined;
    try {
      detail = (await response.json())?.detail;
    } catch {
      // response wasn't JSON (or already consumed) — fall through to the generic message
    }
    throw new Error(detail ?? `${init?.method ?? "GET"} ${url} failed: ${response.status}`);
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

export function importFold(document: unknown, frameIndex?: number): Promise<FoldImportResponse> {
  return getJson("/api/fold/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document, frameIndex: frameIndex ?? null }),
  });
}

export function exportFold(
  pattern: CreasePattern,
  positions: Float32Array,
  title: string,
): Promise<object> {
  return getJson("/api/fold/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pattern, positions: Array.from(positions), title }),
  });
}
