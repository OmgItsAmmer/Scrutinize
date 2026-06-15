import { useApp } from "../context/AppContext";
import { ChatInput } from "./ChatInput";
import { ModalityChips } from "./ModalityChips";
import { SearchResults } from "./SourceCard";

export function SearchView() {
  const { state, setSearchQuery, setModalityFilter, runSearch } = useApp();
  const { search, apiConnected } = state;
  const isEmptyState = !search.result && !search.loading && !search.error;
  function handleSubmit() {
    void runSearch();
  }

  return (
    <div className="flex h-full flex-col bg-[var(--chatly-bg)]">
      

      <div className="flex flex-1 flex-col overflow-y-auto px-6">
        {isEmptyState && (
          <div className="flex flex-1 flex-col items-center justify-center pb-8">
            <div className="mb-10 w-full max-w-2xl text-center">
              
              <h1 className="text-[2rem] font-bold leading-tight tracking-tight text-[var(--chatly-text-primary)] sm:text-[2.5rem]">
               Hey,  What&apos;s on your mind today?
              </h1>
            </div>

            <div className="w-full max-w-2xl space-y-8">
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
            <div className="flex items-center gap-3 rounded-full border border-[var(--chatly-border)] bg-[var(--chatly-panel)] px-5 py-3 text-sm text-[var(--chatly-text-secondary)] shadow-sm">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900" />
              Searching your index…
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
            <SearchResults
              answer={search.result.answer}
              sources={search.result.sources}
              searchQuery={search.result.search_query}
            />
          </div>
        )}
      </div>

      {!isEmptyState && (
        <div className="border-t border-[var(--chatly-border)] bg-[var(--chatly-panel)]/90 px-6 py-5 backdrop-blur">
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

      <p className="px-6 pb-5 text-center text-xs text-[var(--chatly-text-muted)]">
        Scrutinize uses AI to search indexed content. Verify important details in source files.
      </p>
    </div>
  );
}
