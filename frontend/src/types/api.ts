export type FileModality = "text" | "audio" | "video";
export type FileStatus = "uploaded" | "processing" | "indexed" | "failed";
export type JobStatus = "pending" | "running" | "done" | "failed";

export type DependencyCheck = {
  status: string;
  detail?: string | null;
};

export type HealthResponse = {
  status: string;
  service: string;
  version: string;
  checks: Record<string, DependencyCheck>;
};

export type UploadResponse = {
  file_id: string;
  job_id: string;
  filename: string;
  modality: FileModality;
  status: JobStatus;
  message: string;
};

export type JobStatusResponse = {
  id: string;
  file_id: string;
  stage: string;
  status: JobStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type SearchSource = {
  segment_id: string;
  file_id: string;
  modality: FileModality;
  title: string;
  content: string;
  source_path: string;
  start_time: number | null;
  end_time: number | null;
  score: number;
  page_number: number | null;
  section_path: string | null;
};

export type SearchResponse = {
  query: string;
  search_query: string;
  modality_filter: FileModality | null;
  answer: string;
  sources: SearchSource[];
};

export type SearchV2Route = "generic" | "rag";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  timestamp?: string | null;
};

export type ConversationState = {
  messages: ChatMessage[];
};

export type SearchV2Response = {
  query: string;
  rewritten_query: string;
  route: SearchV2Route;
  gate_reason: string;
  modality_filter: FileModality | null;
  answer: string;
  sources: SearchSource[];
  attempts: number;
  confidence: number | null;
  disclaimer_appended: boolean;
  conversation: ConversationState;
};

export type PdfDrawerState = {
  open: boolean;
  url: string | null;
  title: string | null;
  filename: string | null;
};

export type LibraryFileItem = {
  id: string;
  filename: string;
  modality: FileModality;
  status: FileStatus;
  segment_count: number;
  uploaded_at: string;
  duration_seconds: number | null;
  size_bytes: number | null;
  storage_url: string;
  thumbnail_url: string | null;
};

export type LibraryResponse = {
  files: LibraryFileItem[];
  total: number;
};

export type DeleteFileResponse = {
  file_id: string;
  message: string;
};

export type ModalityFilter = FileModality | "all";

export type AppView = "general-chat" | "project" | "account-settings";

export type ConversationScope = "general" | "project";
export type ConversationItem = {
  id: string;
  owner_user_id: string;
  project_id: string | null;
  scope: ConversationScope;
  retrieval_policy: "web_only" | "project_rag";
  title: string;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
};

export type PersistedMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  status: "pending" | "streaming" | "completed" | "failed" | "cancelled";
  citations: Array<Record<string, unknown>>;
  pipeline_run_id?: string | null;
  created_at: string;
  completed_at: string | null;
};

export type PipelineStepDto = {
  id: string;
  step_type: "rewrite" | "gate" | "retrieval" | "synthesis" | "evaluation" | "assess_evidence" | "verify_citations" | "evaluate_groundedness" | string;
  attempt: number;
  model_name: string | null;
  model_input: { system?: string; user?: string } | Record<string, unknown> | null;
  raw_thinking: string | null;
  model_output: string | null;
  structured_output: Record<string, unknown> | null;
  retrieved_sources: Array<Record<string, unknown>> | null;
  has_candidates: boolean;
  candidate_count: number;
  latency_ms: number | null;
  status: "success" | "failure" | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  cached_tokens: number | null;
  cost_usd: number | null;
  created_at: string;
};

export type PipelineTraceDto = {
  id: string;
  original_query: string;
  modality_filter: string | null;
  conversation_context: string | null;
  start_time: string;
  end_time: string | null;
  final_route: string | null;
  final_answer: string | null;
  final_confidence: number | null;
  attempts_count: number;
  disclaimer_appended: boolean;
  total_cost_usd: number | null;
  total_tokens: number | null;
  created_at: string;
  steps: PipelineStepDto[];
};

export type RetrievalCandidateMatch = "all" | "semantic" | "keyword" | "both";

export type RetrievalCandidatesDto = {
  step_id: string;
  attempt: number;
  total_candidates: number;
  matched_count: number;
  match: RetrievalCandidateMatch;
  candidates: Array<Record<string, unknown>>;
};

export type UploadJobState = {
  jobId: string;
  fileId: string;
  filename: string;
  modality: FileModality;
  status: JobStatus;
  errorMessage: string | null;
};

export type ProjectAuthResponse = {
  project_id: string;
  api_key: string;
  client_key: string;
};

export type AuthTokenResponse = { access_token: string; token_type: string };
export type UserProject = { project_id: string; name: string; role: string; client_key: string; created_at: string; api_key?: string; settings?: Record<string, any> };

export type ProjectInfo = {
  project_id: string;
  name: string;
  api_key: string;
  client_key: string;
  settings: Record<string, any>;
};

