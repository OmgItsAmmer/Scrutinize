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

export const V2_LOW_CONFIDENCE_DISCLAIMER =
  "Note: answer may vary — retrieval confidence was low.";

export function formatConfidencePercent(confidence: number | null): string | null {
  if (confidence == null) {
    return null;
  }
  return `${Math.round(confidence * 100)}% confidence`;
}

/** Strip backend disclaimer from answer body when shown as a separate footnote. */
export function displayV2Answer(answer: string, disclaimerAppended: boolean): string {
  if (!disclaimerAppended) {
    return answer;
  }
  const suffix = `\n\n${V2_LOW_CONFIDENCE_DISCLAIMER}`;
  if (answer.endsWith(suffix)) {
    return answer.slice(0, -suffix.length).trimEnd();
  }
  if (answer.includes(V2_LOW_CONFIDENCE_DISCLAIMER)) {
    return answer.replace(V2_LOW_CONFIDENCE_DISCLAIMER, "").trim();
  }
  return answer;
}
