const envBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
const forceMockRaw = (import.meta.env.VITE_FORCE_MOCK as string | undefined)?.trim().toLowerCase();
const forceMock = forceMockRaw === "1" || forceMockRaw === "true" || forceMockRaw === "yes" || forceMockRaw === "on";

export const APP_CONFIG = {
  apiBaseUrl: envBase && envBase.length > 0 ? envBase.replace(/\/$/, "") : "http://localhost:8000",
  forceMock,
  requestTimeoutMs: 5000,
  mockBannerLabel: "Mock mode",
  sseBackoffMs: [800, 1500, 2500, 4000, 6000],
};

export const API_PREFIX = "/api";

export function apiPath(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (import.meta.env.DEV) {
    return `${API_PREFIX}${normalized}`;
  }
  return `${APP_CONFIG.apiBaseUrl}${normalized}`;
}
