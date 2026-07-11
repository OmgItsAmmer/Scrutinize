import type {
  ConversationState,
  DeleteFileResponse,
  HealthResponse,
  JobStatusResponse,
  LibraryResponse,
  ModalityFilter,
  ProjectAuthResponse,
  SearchV2Response,
  UploadResponse,
} from "../types/api";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const SEARCH_API_PATH = import.meta.env.VITE_SEARCH_API ?? "/v2/search";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body.detail)) {
      return body.detail.map((item: { msg?: string }) => item.msg ?? "Validation error").join(", ");
    }
  } catch {
    // ignore JSON parse failures
  }
  return `Request failed (${response.status})`;
}

function getProjectKey(path: string): string | null {
  if (
    path.includes("/v2/projects/login")
    || path.includes("/v2/projects/signup")
    || path.includes("/v2/projects/reset-password")
  ) {
    return null;
  }
  if (path.includes("/search")) {
    return localStorage.getItem("scrutinize_client_key");
  }
  return localStorage.getItem("scrutinize_admin_key") ?? localStorage.getItem("scrutinize_client_key");
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const key = getProjectKey(path);
  const headers = new Headers(init?.headers);
  if (key) {
    headers.set("X-Project-Key", key);
  }
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    throw new ApiError(await parseError(response), response.status);
  }
  return response.json() as Promise<T>;
}

export function getApiUrl(): string {
  return API_URL;
}

export function isLocalDevApi(): boolean {
  try {
    const host = new URL(API_URL).hostname;
    return host === "localhost" || host === "127.0.0.1";
  } catch {
    return false;
  }
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

/** Wakes Fly API only — does not ping Redis or Qdrant. */
export function fetchHealthWake(): Promise<HealthResponse> {
  return request<HealthResponse>("/health/wake");
}

export function getSearchApiPath(): string {
  return SEARCH_API_PATH;
}

export function searchContent(
  query: string,
  modalityFilter: ModalityFilter,
  conversation?: ConversationState,
): Promise<SearchV2Response> {
  return request<SearchV2Response>(SEARCH_API_PATH, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      modality_filter: modalityFilter === "all" ? null : modalityFilter,
      conversation: conversation ?? { messages: [] },
    }),
  });
}

export type StreamEvent =
  | { event: "status"; data: { step: string; model?: string; message: string; route?: string; rewritten?: string; confidence?: number; verdict?: string; correct_route?: string; feedback?: string; sources_count?: number; sources?: any[] } }
  | { event: "chunk"; data: { text: string } }
  | { event: "result"; data: SearchV2Response }
  | { event: "error"; data: { message: string } };

function parseSseChunk(chunk: string, onEvent: (event: StreamEvent) => void): boolean {
  const trimmedLine = chunk.trim();
  if (!trimmedLine.startsWith("data: ")) {
    return false;
  }

  const rawJson = trimmedLine.slice(6).trim();
  if (!rawJson) {
    return false;
  }

  const parsed = JSON.parse(rawJson) as StreamEvent;
  onEvent(parsed);
  return parsed.event === "result" || parsed.event === "error";
}

export async function searchContentStream(
  query: string,
  modalityFilter: ModalityFilter,
  conversation: ConversationState | undefined,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const path = "/v2/search/stream";
  const key = getProjectKey(path);
  const headers = new Headers();
  headers.set("Content-Type", "application/json");
  if (key) {
    headers.set("X-Project-Key", key);
  }

  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      query,
      modality_filter: modalityFilter === "all" ? null : modalityFilter,
      conversation: conversation ?? { messages: [] },
    }),
  });

  if (!response.ok) {
    throw new ApiError(await parseError(response), response.status);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("No response body reader available.");
  }

  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let sawResult = false;

  const consumeBuffer = () => {
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      try {
        if (parseSseChunk(part, onEvent)) {
          sawResult = true;
        }
      } catch (e) {
        console.error("Error parsing stream SSE line:", part, e);
      }
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (value) {
      buffer += decoder.decode(value, { stream: true });
      consumeBuffer();
    }
    if (done) {
      break;
    }
  }

  buffer += decoder.decode();
  consumeBuffer();

  if (!sawResult) {
    throw new Error("Search stream ended before a final result was received.");
  }
}


export function uploadFile(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return request<UploadResponse>("/upload", {
    method: "POST",
    body: formData,
  });
}

export function fetchJobStatus(jobId: string): Promise<JobStatusResponse> {
  return request<JobStatusResponse>(`/status/${jobId}`);
}

export function fetchLibrary(): Promise<LibraryResponse> {
  return request<LibraryResponse>("/library");
}

export function deleteLibraryFile(fileId: string): Promise<DeleteFileResponse> {
  return request<DeleteFileResponse>(`/library/${fileId}`, {
    method: "DELETE",
  });
}

export function libraryFileContentUrl(fileId: string, download = false): string {
  const key = localStorage.getItem("scrutinize_admin_key") ?? localStorage.getItem("scrutinize_client_key");
  const params = new URLSearchParams();
  if (download) {
    params.set("download", "true");
  }
  if (key) {
    params.set("project_key", key);
  }
  const query = params.toString();
  return `${API_URL}/library/${fileId}/content${query ? "?" + query : ""}`;
}

export function loginProject(name: string, password: string): Promise<ProjectAuthResponse> {
  return request<ProjectAuthResponse>("/v2/projects/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, password }),
  });
}

export function signupProject(name: string, password: string, settings: Record<string, any> = {}): Promise<ProjectAuthResponse> {
  return request<ProjectAuthResponse>("/v2/projects/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, password, settings }),
  });
}

export function fetchProjectInfo(): Promise<{ project_id: string; name: string; settings: Record<string, any> }> {
  return request<{ project_id: string; name: string; settings: Record<string, any> }>("/v2/projects/me");
}

export function updateProjectSettings(settings: Record<string, any>): Promise<{ project_id: string; name: string; settings: Record<string, any> }> {
  return request<{ project_id: string; name: string; settings: Record<string, any> }>("/v2/projects/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
}

export function changeProjectPassword(
  newPassword: string,
  currentPassword?: string,
): Promise<{ message: string }> {
  const body: { new_password: string; current_password?: string } = {
    new_password: newPassword,
  };
  if (currentPassword) {
    body.current_password = currentPassword;
  }
  return request<{ message: string }>("/v2/projects/me/password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function resetProjectPassword(
  name: string,
  apiKey: string,
  newPassword: string,
): Promise<{ message: string }> {
  return request<{ message: string }>("/v2/projects/reset-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      api_key: apiKey,
      new_password: newPassword,
    }),
  });
}

