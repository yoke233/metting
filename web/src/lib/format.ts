// formatTimestamp: render backend millisecond timestamps for UI display.
export function formatTimestamp(value?: number | null) {
  if (!value) return "—"
  return new Date(value).toLocaleString("zh-CN", { hour12: false })
}

// shortId: keep IDs readable inside tight UI elements.
export function shortId(value: string, size = 6) {
  if (!value) return ""
  return value.length > size ? value.slice(0, size) : value
}

// clampText: keep preview snippets compact.
export function clampText(value: string, max = 120) {
  if (!value) return ""
  return value.length > max ? `${value.slice(0, max)}…` : value
}

// tryParseJson: parse JSON safely for config previews.
export function tryParseJson<T>(value: string): T | null {
  if (!value) return null
  try {
    return JSON.parse(value) as T
  } catch {
    return null
  }
}
