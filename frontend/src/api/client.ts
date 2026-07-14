import type {
  ConversationState,
  ConversationItem,
  ConversationScope,
  DeleteFileResponse,
  HealthResponse,
  JobStatusResponse,
  LibraryResponse,
  ModalityFilter,
  ProjectAuthResponse,
  ProjectInfo,
  AuthTokenResponse,
  UserProject,
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

async function parseBlobError(response: Response): Promise<string> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return parseError(response);
  }
  try {
    const text = await response.text();
    return text || `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

function getProjectKey(path: string): string | null {
  if (
    path.includes("/v2/projects/login")
    || path.includes("/v2/projects/signup")
    || path === "/v2/projects"
    || path === "/v2/projects/mine"
    || /^\/v2\/projects\/[0-9a-f-]{36}$/i.test(path)
    || path.startsWith("/v3/conversations")
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
  const token = localStorage.getItem("scrutinize_access_token");
  const projectId = localStorage.getItem("scrutinize_project_id");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (token && projectId) headers.set("X-Project-Id", projectId);
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    throw new ApiError(await parseError(response), response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export function getApiUrl(): string {
  return API_URL;
}

export async function fetchPdfBlob(url: string): Promise<Blob> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new ApiError(await parseBlobError(response), response.status);
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/pdf")) {
    throw new ApiError(
      `Expected a PDF response, received ${contentType || "unknown content"}.`,
      response.status,
    );
  }

  return response.blob();
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
  webSearchMode: "auto" | "always" | "never",
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const path = "/v2/search/stream";
  const key = getProjectKey(path);
  const headers = new Headers();
  headers.set("Content-Type", "application/json");
  if (key) {
    headers.set("X-Project-Key", key);
  }
  const token = localStorage.getItem("scrutinize_access_token");
  const projectId = localStorage.getItem("scrutinize_project_id");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (token && projectId) headers.set("X-Project-Id", projectId);

  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      query,
      modality_filter: modalityFilter === "all" ? null : modalityFilter,
      conversation: conversation ?? { messages: [] },
      web_search_mode: webSearchMode,
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
  return request<UploadResponse>("/v2/projects/files", {
    method: "POST",
    body: formData,
  });
}

export function loginWithGoogle(idToken: string): Promise<AuthTokenResponse> {
  return request("/v2/auth/google", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
  });
}

export function fetchCurrentUser(): Promise<{ id: string; email: string }> {
  return request<{ id: string; email: string }>("/v2/auth/me");
}

export function fetchUserProjects(): Promise<{ projects: UserProject[] }> {
  return request("/v2/projects");
}

export function createUserProject(name: string, description: string, settings: Record<string, any> = {}): Promise<UserProject> {
  return request<UserProject>("/v2/projects/mine", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description, settings }),
  });
}

export function deleteUserProject(projectId: string): Promise<void> {
  return request<void>(`/v2/projects/${projectId}`, { method: "DELETE" });
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

export function fetchProjectInfo(): Promise<ProjectInfo> {
  return request<ProjectInfo>("/v2/projects/me");
}

export function updateProjectSettings(settings: Record<string, any>): Promise<ProjectInfo> {
  return request<ProjectInfo>("/v2/projects/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
}

export function fetchConversations(scope: ConversationScope, projectId?: string): Promise<{ conversations: ConversationItem[]; total: number }> {
  const params = new URLSearchParams({ scope });
  if (projectId) params.set("project_id", projectId);
  return request(`/v3/conversations?${params.toString()}`);
}

export function createConversation(scope: ConversationScope, projectId?: string): Promise<ConversationItem> {
  return request("/v3/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scope, project_id: projectId ?? null }),
  });
}

export function deleteConversation(conversationId: string): Promise<void> {
  return request<void>(`/v3/conversations/${conversationId}`, { method: "DELETE" });
}

export function fetchConversationMessages(conversationId: string): Promise<{ messages: import("../types/api").PersistedMessage[]; total: number }> {
  return request(`/v3/conversations/${conversationId}/messages`);
}

export type ConversationSource = {
  file_id: string;
  filename: string;
  modality: string;
  status: string;
  uploaded_at: string;
};

export function fetchConversationSources(conversationId: string): Promise<{ sources: ConversationSource[]; total: number }> {
  return request(`/v3/conversations/${conversationId}/sources`);
}

export async function uploadConversationSource(conversationId: string, file: File): Promise<{ file_id: string; job_id: string; filename: string; status: string }> {
  const form = new FormData();
  form.append("file", file);
  const token = localStorage.getItem("scrutinize_access_token");
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_URL}/v3/conversations/${conversationId}/sources`, {
    method: "POST",
    headers,
    body: form,
  });
  if (!response.ok) throw new ApiError(await parseError(response), response.status);
  return response.json();
}

export type ConversationStreamEvent =
  | { event: "message.accepted"; data: { user_message?: import("../types/api").PersistedMessage } }
  | { event: "status"; data: { phase?: string; label?: string; step?: string; message?: string; model?: string | null; route?: string; rewritten?: string; sources_count?: number; sources?: Array<{ title?: string }>; confidence?: number; verdict?: string; feedback?: string } }
  | { event: "delta"; data: { assistant_message_id: string; text: string } }
  | { event: "message.completed"; data: { assistant_message: import("../types/api").PersistedMessage; conversation: ConversationItem } }
  | { event: "error"; data: { code: string; retryable: boolean; message: string } };

export async function streamConversationMessage(
  conversationId: string,
  content: string,
  clientMessageId: string,
  onEvent: (event: ConversationStreamEvent) => void,
  options?: { requestedTool?: string },
): Promise<void> {
  const headers = new Headers({ "Content-Type": "application/json" });
  const token = localStorage.getItem("scrutinize_access_token");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const body: Record<string, unknown> = { content, client_message_id: clientMessageId };
  if (options?.requestedTool) {
    body.requested_tool = options.requestedTool;
  }
  const response = await fetch(`${API_URL}/v3/conversations/${conversationId}/messages/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new ApiError(await parseError(response), response.status);
  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response stream available");
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const eventName = block.split("\n").find((line) => line.startsWith("event: "))?.slice(7);
      const dataLine = block.split("\n").find((line) => line.startsWith("data: "))?.slice(6);
      if (eventName && dataLine) onEvent({ event: eventName, data: JSON.parse(dataLine) } as ConversationStreamEvent);
    }
    if (done) break;
  }
}

