import { getSearchApiPath } from "../api/client";
import { useApp } from "../context/AppContext";
import { ChatInput } from "./ChatInput";
import { ModalityChips } from "./ModalityChips";
import { SearchResults } from "./SourceCard";

export function SearchView() {
  const { state, setSearchQuery, setModalityFilter, runSearch } = useApp();
  const { search, apiConnected } = state;
  const isEmptyState = !search.result && !search.loading && !search.error;
  const isV2Search = getSearchApiPath() === "/v2/search";
  function handleSubmit() {
    void runSearch();
  }

  return (
    <div className="flex h-full flex-col bg-[var(--chatly-bg)]">
      

      <div className="flex flex-1 flex-col overflow-y-auto px-4 sm:px-6">
        {isEmptyState && (
          <div className="flex flex-1 flex-col items-center justify-center pb-4 sm:pb-8">
            <div className="mb-6 w-full max-w-2xl text-center sm:mb-10">
              <h1 className="text-2xl font-bold leading-tight tracking-tight text-[var(--chatly-text-primary)] sm:text-[2rem] md:text-[2.5rem]">
                Hey, What&apos;s on your mind today?
              </h1>
            </div>

            <div className="w-full max-w-2xl space-y-6 sm:space-y-8">
              <ChatInput
                value={search.query}
                onChange={setSearchQuery}
                onSubmit={handleSubmit}
                disabled={!apiConnected}
                loading={search.loading}
              />
              <ModalityChips
                value={search.modalityFilter}
                onChange={setModalityFilter}
                disabled={!apiConnected || search.loading}
              />
            </div>
          </div>
        )}

        {search.loading && (
          <div className="flex flex-1 items-center justify-center">
            <div className="flex max-w-md flex-col items-center gap-3 rounded-2xl border border-[var(--chatly-border)] bg-[var(--chatly-panel)] px-5 py-4 text-center text-sm text-[var(--chatly-text-secondary)] shadow-sm">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900" />
              <span>
                {isV2Search
                  ? "Running local AI pipeline… Generic replies are quick; library search may take longer."
                  : "Searching your index…"}
              </span>
            </div>
          </div>
        )}

        {search.error && (
          <div className="mx-auto mb-6 w-full max-w-3xl rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {search.error}
          </div>
        )}

        {search.result && !search.loading && (
          <div className="mx-auto mb-8 w-full max-w-3xl flex-1">
            <SearchResults result={search.result} />
          </div>
        )}
      </div>

      {!isEmptyState && (
        <div className="border-t border-[var(--chatly-border)] bg-[var(--chatly-panel)]/90 px-4 py-4 backdrop-blur sm:px-6 sm:py-5">
          <div className="mx-auto w-full max-w-2xl space-y-4">
            <ChatInput
              value={search.query}
              onChange={setSearchQuery}
              onSubmit={handleSubmit}
              disabled={!apiConnected}
              loading={search.loading}
            />
            <ModalityChips
              value={search.modalityFilter}
              onChange={setModalityFilter}
              disabled={!apiConnected || search.loading}
            />
          </div>
        </div>
      )}

      <p className="px-4 pb-3 text-center text-xs text-[var(--chatly-text-muted)] sm:px-6 sm:pb-5">
        Scrutinize uses AI to search indexed content. Verify important details in source files.
      </p>
    </div>
  );
}
