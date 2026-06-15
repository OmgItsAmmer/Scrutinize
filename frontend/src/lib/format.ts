/** Pakistan locale and timezone for dates and durations in the UI. */
export const PAKISTAN_LOCALE = "en-PK";
export const PAKISTAN_TIMEZONE = "Asia/Karachi";

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(PAKISTAN_LOCALE, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: PAKISTAN_TIMEZONE,
  }).format(new Date(value));
}

/** Media timestamp: 00:42 or 1:05:30 for seek labels and segment ranges. */
export function formatTimestampSeconds(seconds: number | null): string {
  if (seconds == null) {
    return "";
  }
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

/** File duration for library and metadata (supports hours). */
export function formatDurationSeconds(seconds: number | null): string {
  if (seconds == null) {
    return "—";
  }
  return formatTimestampSeconds(seconds) || "—";
}
