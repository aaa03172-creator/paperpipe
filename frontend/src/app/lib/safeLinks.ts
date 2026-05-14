const ALLOWED_EXTERNAL_SCHEMES = new Set(["http:", "https:", "file:", "zotero:"]);
const ALLOWED_INTERNAL_PREFIXES = ["/papers/"];

export function sanitizeRenderableHref(value?: string | null): string | null {
  const text = String(value ?? "").trim();
  if (!text) {
    return null;
  }
  if (ALLOWED_INTERNAL_PREFIXES.some((prefix) => text.startsWith(prefix))) {
    return text;
  }
  try {
    const parsed = new URL(text);
    return ALLOWED_EXTERNAL_SCHEMES.has(parsed.protocol.toLowerCase()) ? text : null;
  } catch {
    return null;
  }
}
