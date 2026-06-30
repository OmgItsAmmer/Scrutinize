import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  type ReactNode,
} from "react";
import {
  ApiError,
  fetchHealth,
  fetchHealthWake,
  fetchJobStatus,
  fetchLibrary,
  deleteLibraryFile as deleteLibraryFileRequest,
  getApiUrl,
  isLocalDevApi,
  searchContent,
  uploadFile,
} from "../api/client";
import type {
  AppView,
  ConversationState,
  HealthResponse,
  JobStatus,
  LibraryFileItem,
  ModalityFilter,
  SearchV2Response,
  UploadJobState,
} from "../types/api";

type SearchState = {
  query: string;
  modalityFilter: ModalityFilter;
  loading: boolean;
  error: string | null;
  result: SearchV2Response | null;
  conversation: ConversationState;
};

const emptyConversation = (): ConversationState => ({ messages: [] });

type UploadState = {
  uploading: boolean;
  error: string | null;
  activeJobs: UploadJobState[];
  dragActive: boolean;
};

type LibraryState = {
  loading: boolean;
  error: string | null;
  files: LibraryFileItem[];
};

type ProjectSessionState = {
  projectId: string;
  projectName: string;
  apiKey: string;
  clientKey: string;
} | null;

type AppState = {
  view: AppView;
  apiConnected: boolean;
  health: HealthResponse | null;
  healthError: string | null;
  search: SearchState;
  upload: UploadState;
  library: LibraryState;
  project: ProjectSessionState;
};

type Action =
  | { type: "SET_VIEW"; view: AppView }
  | { type: "SET_HEALTH"; health: HealthResponse | null; error: string | null }
  | { type: "SET_SEARCH_QUERY"; query: string }
  | { type: "SET_MODALITY_FILTER"; filter: ModalityFilter }
  | { type: "SEARCH_START" }
  | { type: "SEARCH_SUCCESS"; result: SearchV2Response }
  | { type: "SEARCH_ERROR"; error: string }
  | { type: "CLEAR_SEARCH" }
  | { type: "UPLOAD_START" }
  | { type: "UPLOAD_ERROR"; error: string }
  | { type: "UPLOAD_QUEUED"; job: UploadJobState }
  | { type: "UPLOAD_JOB_UPDATE"; jobId: string; status: JobStatus; errorMessage: string | null }
  | { type: "UPLOAD_JOB_REMOVE"; jobId: string }
  | { type: "SET_DRAG_ACTIVE"; active: boolean }
  | { type: "LIBRARY_START" }
  | { type: "LIBRARY_SUCCESS"; files: LibraryFileItem[] }
  | { type: "LIBRARY_ERROR"; error: string }
  | { type: "LIBRARY_FILE_REMOVED"; fileId: string }
  | { type: "AUTH_SUCCESS"; project: NonNullable<ProjectSessionState> }
  | { type: "AUTH_LOGOUT" };

const initialState: AppState = {
  view: "search",
  apiConnected: false,
  health: null,
  healthError: null,
  search: {
    query: "",
    modalityFilter: "all",
    loading: false,
    error: null,
    result: null,
    conversation: emptyConversation(),
  },
  upload: {
    uploading: false,
    error: null,
    activeJobs: [],
    dragActive: false,
  },
  library: {
    loading: false,
    error: null,
    files: [],
  },
  project: localStorage.getItem("scrutinize_project_id")
    ? {
        projectId: localStorage.getItem("scrutinize_project_id")!,
        projectName: localStorage.getItem("scrutinize_project_name")!,
        apiKey: localStorage.getItem("scrutinize_admin_key")!,
        clientKey: localStorage.getItem("scrutinize_client_key")!,
      }
    : null,
};

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "AUTH_SUCCESS":
      return {
        ...state,
        project: action.project,
        search: {
          ...initialState.search,
          conversation: emptyConversation(),
        },
        library: {
          ...initialState.library,
        },
        upload: {
          ...initialState.upload,
        },
      };
    case "AUTH_LOGOUT":
      return {
        ...state,
        project: null,
        search: {
          ...initialState.search,
          conversation: emptyConversation(),
        },
        library: {
          ...initialState.library,
        },
        upload: {
          ...initialState.upload,
        },
      };
    case "SET_VIEW":
      return { ...state, view: action.view };
    case "SET_HEALTH":
      return {
        ...state,
        health: action.health,
        healthError: action.error,
        apiConnected: action.health !== null,
      };
    case "SET_SEARCH_QUERY":
      return { ...state, search: { ...state.search, query: action.query } };
    case "SET_MODALITY_FILTER":
      return { ...state, search: { ...state.search, modalityFilter: action.filter } };
    case "SEARCH_START":
      return {
        ...state,
        search: { ...state.search, loading: true, error: null },
      };
    case "SEARCH_SUCCESS":
      return {
        ...state,
        search: {
          ...state.search,
          loading: false,
          error: null,
          result: action.result,
          conversation: action.result.conversation,
        },
      };
    case "SEARCH_ERROR":
      return {
        ...state,
        search: { ...state.search, loading: false, error: action.error },
      };
    case "CLEAR_SEARCH":
      return {
        ...state,
        search: {
          ...state.search,
          query: "",
          modalityFilter: "all",
          error: null,
          result: null,
          loading: false,
          conversation: emptyConversation(),
        },
      };
    case "UPLOAD_START":
      return {
        ...state,
        upload: { ...state.upload, uploading: true, error: null },
      };
    case "UPLOAD_ERROR":
      return {
        ...state,
        upload: { ...state.upload, uploading: false, error: action.error },
      };
    case "UPLOAD_QUEUED":
      return {
        ...state,
        upload: {
          ...state.upload,
          uploading: false,
          error: null,
          activeJobs: [action.job, ...state.upload.activeJobs],
        },
      };
    case "UPLOAD_JOB_UPDATE":
      return {
        ...state,
        upload: {
          ...state.upload,
          activeJobs: state.upload.activeJobs.map((job) =>
            job.jobId === action.jobId
              ? { ...job, status: action.status, errorMessage: action.errorMessage }
              : job,
          ),
        },
      };
    case "UPLOAD_JOB_REMOVE":
      return {
        ...state,
        upload: {
          ...state.upload,
          activeJobs: state.upload.activeJobs.filter((job) => job.jobId !== action.jobId),
        },
      };
    case "SET_DRAG_ACTIVE":
      return {
        ...state,
        upload: { ...state.upload, dragActive: action.active },
      };
    case "LIBRARY_START":
      return {
        ...state,
        library: { ...state.library, loading: true, error: null },
      };
    case "LIBRARY_SUCCESS":
      return {
        ...state,
        library: { ...state.library, loading: false, files: action.files },
      };
    case "LIBRARY_ERROR":
      return {
        ...state,
        library: { ...state.library, loading: false, error: action.error },
      };
    case "LIBRARY_FILE_REMOVED":
      return {
        ...state,
        library: {
          ...state.library,
          files: state.library.files.filter((file) => file.id !== action.fileId),
        },
      };
    default:
      return state;
  }
}

type AppContextValue = {
  state: AppState;
  apiUrl: string;
  setView: (view: AppView) => void;
  setSearchQuery: (query: string) => void;
  setModalityFilter: (filter: ModalityFilter) => void;
  runSearch: () => Promise<void>;
  clearSearch: () => void;
  uploadFiles: (files: FileList | File[]) => Promise<void>;
  setDragActive: (active: boolean) => void;
  refreshLibrary: () => Promise<void>;
  deleteLibraryFile: (fileId: string) => Promise<void>;
  dismissUploadJob: (jobId: string) => void;
  login: (projectName: string, apiKey: string, clientKey: string, projectId: string) => void;
  logout: () => void;
};

const AppContext = createContext<AppContextValue | null>(null);

function formatError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong";
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  useEffect(() => {
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let retries = 0;
    const MAX_WAKE_RETRIES = 12;
    const localDev = isLocalDevApi();

    async function checkHealth() {
      try {
        const health = localDev ? await fetchHealth() : await fetchHealthWake();
        if (!cancelled) {
          dispatch({ type: "SET_HEALTH", health, error: null });
        }
        retries = 0;
      } catch (error) {
        if (!cancelled) {
          dispatch({
            type: "SET_HEALTH",
            health: null,
            error: formatError(error),
          });
          if (!localDev && retries < MAX_WAKE_RETRIES) {
            retries += 1;
            retryTimer = setTimeout(() => void checkHealth(), 5_000);
          }
        }
      }
    }

    function onVisibilityChange() {
      if (localDev || document.visibilityState !== "visible") {
        return;
      }
      void checkHealth();
    }

    void checkHealth();
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      cancelled = true;
      if (retryTimer) {
        clearTimeout(retryTimer);
      }
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, []);

  useEffect(() => {
    const pendingJobs = state.upload.activeJobs.filter(
      (job) => job.status === "pending" || job.status === "running",
    );
    if (pendingJobs.length === 0) {
      return;
    }

    const interval = setInterval(async () => {
      for (const job of pendingJobs) {
        try {
          const status = await fetchJobStatus(job.jobId);
          dispatch({
            type: "UPLOAD_JOB_UPDATE",
            jobId: job.jobId,
            status: status.status,
            errorMessage: status.error_message,
          });
        } catch (error) {
          dispatch({
            type: "UPLOAD_JOB_UPDATE",
            jobId: job.jobId,
            status: "failed",
            errorMessage: formatError(error),
          });
        }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [state.upload.activeJobs]);

  const refreshLibrary = useCallback(async () => {
    dispatch({ type: "LIBRARY_START" });
    try {
      const response = await fetchLibrary();
      dispatch({ type: "LIBRARY_SUCCESS", files: response.files });
    } catch (error) {
      dispatch({ type: "LIBRARY_ERROR", error: formatError(error) });
    }
  }, []);

  const deleteLibraryFile = useCallback(async (fileId: string) => {
    try {
      await deleteLibraryFileRequest(fileId);
      dispatch({ type: "LIBRARY_FILE_REMOVED", fileId });
    } catch (error) {
      dispatch({ type: "LIBRARY_ERROR", error: formatError(error) });
      throw error;
    }
  }, []);

  useEffect(() => {
    if (state.view === "library") {
      void refreshLibrary();
    }
  }, [refreshLibrary, state.view]);

  const runSearch = useCallback(async () => {
    const query = state.search.query.trim();
    if (!query) {
      return;
    }
    if (!state.apiConnected) {
      dispatch({ type: "SEARCH_ERROR", error: "API is unavailable. Check your connection." });
      return;
    }

    dispatch({ type: "SEARCH_START" });
    try {
      const result = await searchContent(
        query,
        state.search.modalityFilter,
        state.search.conversation,
      );
      dispatch({ type: "SEARCH_SUCCESS", result });
    } catch (error) {
      dispatch({ type: "SEARCH_ERROR", error: formatError(error) });
    }
  }, [state.apiConnected, state.search.conversation, state.search.modalityFilter, state.search.query]);

  const uploadFilesHandler = useCallback(async (files: FileList | File[]) => {
    if (!state.apiConnected) {
      dispatch({
        type: "UPLOAD_ERROR",
        error: "API is unavailable. Cannot upload until the backend is connected.",
      });
      return;
    }

    const fileArray = Array.from(files);
    if (fileArray.length === 0) {
      return;
    }

    dispatch({ type: "UPLOAD_START" });
    try {
      for (const file of fileArray) {
        const response = await uploadFile(file);
        dispatch({
          type: "UPLOAD_QUEUED",
          job: {
            jobId: response.job_id,
            fileId: response.file_id,
            filename: response.filename,
            modality: response.modality,
            status: response.status,
            errorMessage: null,
          },
        });
      }
    } catch (error) {
      dispatch({ type: "UPLOAD_ERROR", error: formatError(error) });
    }
  }, [state.apiConnected]);

  const login = useCallback((projectName: string, apiKey: string, clientKey: string, projectId: string) => {
    localStorage.setItem("scrutinize_project_id", projectId);
    localStorage.setItem("scrutinize_project_name", projectName);
    localStorage.setItem("scrutinize_admin_key", apiKey);
    localStorage.setItem("scrutinize_client_key", clientKey);
    dispatch({
      type: "AUTH_SUCCESS",
      project: { projectId, projectName, apiKey, clientKey },
    });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("scrutinize_project_id");
    localStorage.removeItem("scrutinize_project_name");
    localStorage.removeItem("scrutinize_admin_key");
    localStorage.removeItem("scrutinize_client_key");
    dispatch({ type: "AUTH_LOGOUT" });
  }, []);

  const value = useMemo<AppContextValue>(
    () => ({
      state,
      apiUrl: getApiUrl(),
      setView: (view) => dispatch({ type: "SET_VIEW", view }),
      setSearchQuery: (query) => dispatch({ type: "SET_SEARCH_QUERY", query }),
      setModalityFilter: (filter) => dispatch({ type: "SET_MODALITY_FILTER", filter }),
      runSearch,
      clearSearch: () => dispatch({ type: "CLEAR_SEARCH" }),
      uploadFiles: uploadFilesHandler,
      setDragActive: (active) => dispatch({ type: "SET_DRAG_ACTIVE", active }),
      refreshLibrary,
      deleteLibraryFile,
      dismissUploadJob: (jobId) => dispatch({ type: "UPLOAD_JOB_REMOVE", jobId }),
      login,
      logout,
    }),
    [deleteLibraryFile, refreshLibrary, runSearch, state, uploadFilesHandler, login, logout],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used within AppProvider");
  }
  return context;
}
