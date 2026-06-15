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
  fetchJobStatus,
  fetchLibrary,
  getApiUrl,
  searchContent,
  uploadFile,
} from "../api/client";
import type {
  AppView,
  HealthResponse,
  JobStatus,
  LibraryFileItem,
  ModalityFilter,
  SearchResponse,
  UploadJobState,
} from "../types/api";

type SearchState = {
  query: string;
  modalityFilter: ModalityFilter;
  loading: boolean;
  error: string | null;
  result: SearchResponse | null;
};

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

type AppState = {
  view: AppView;
  apiConnected: boolean;
  health: HealthResponse | null;
  healthError: string | null;
  search: SearchState;
  upload: UploadState;
  library: LibraryState;
};

type Action =
  | { type: "SET_VIEW"; view: AppView }
  | { type: "SET_HEALTH"; health: HealthResponse | null; error: string | null }
  | { type: "SET_SEARCH_QUERY"; query: string }
  | { type: "SET_MODALITY_FILTER"; filter: ModalityFilter }
  | { type: "SEARCH_START" }
  | { type: "SEARCH_SUCCESS"; result: SearchResponse }
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
  | { type: "LIBRARY_ERROR"; error: string };

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
};

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "SET_VIEW":
      return { ...state, view: action.view };
    case "SET_HEALTH":
      return {
        ...state,
        health: action.health,
        healthError: action.error,
        apiConnected: action.health?.status === "ok",
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
  dismissUploadJob: (jobId: string) => void;
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

    async function pollHealth() {
      try {
        const health = await fetchHealth();
        if (!cancelled) {
          dispatch({ type: "SET_HEALTH", health, error: null });
        }
      } catch (error) {
        if (!cancelled) {
          dispatch({
            type: "SET_HEALTH",
            health: null,
            error: formatError(error),
          });
        }
      }
    }

    pollHealth();
    const interval = setInterval(pollHealth, 15000);
    return () => {
      cancelled = true;
      clearInterval(interval);
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
      const result = await searchContent(query, state.search.modalityFilter);
      dispatch({ type: "SEARCH_SUCCESS", result });
    } catch (error) {
      dispatch({ type: "SEARCH_ERROR", error: formatError(error) });
    }
  }, [state.apiConnected, state.search.modalityFilter, state.search.query]);

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
      dismissUploadJob: (jobId) => dispatch({ type: "UPLOAD_JOB_REMOVE", jobId }),
    }),
    [refreshLibrary, runSearch, state, uploadFilesHandler],
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
