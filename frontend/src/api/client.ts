import type {
  ConversationState,
  DeleteFileResponse,
  HealthResponse,
  JobStatusResponse,
  LibraryResponse,
  ModalityFilter,
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
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
  const params = download ? "?download=true" : "";
  return `${API_URL}/library/${fileId}/content${params}`;
}
