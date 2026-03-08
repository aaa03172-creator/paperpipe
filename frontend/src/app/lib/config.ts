const envBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
const envApiKey = (import.meta.env.VITE_API_KEY as string | undefined)?.trim();
const forceMockRaw = (import.meta.env.VITE_FORCE_MOCK as string | undefined)?.trim();
const strictApiRaw = (import.meta.env.VITE_STRICT_API as string | undefined)?.trim();
const autoMockFallbackRaw = (import.meta.env.VITE_AUTO_MOCK_FALLBACK as string | undefined)?.trim();

function parseBooleanEnv(raw: string | undefined): boolean {
  const value = (raw ?? "").toLowerCase();
  return value === "1" || value === "true" || value === "yes" || value === "on";
}

const forceMock = parseBooleanEnv(forceMockRaw);
const strictApi = parseBooleanEnv(strictApiRaw);
const autoMockFallback = autoMockFallbackRaw === undefined ? true : parseBooleanEnv(autoMockFallbackRaw);

export const APP_CONFIG = {
  apiBaseUrl: envBase && envBase.length > 0 ? envBase.replace(/\/$/, "") : "http://localhost:8000",
  apiKey: envApiKey && envApiKey.length > 0 ? envApiKey : undefined,
  forceMock,
  strictApi,
  autoMockFallback,
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
