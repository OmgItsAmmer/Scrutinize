import { useApp } from "./context/AppContext";
import { LibraryView } from "./components/LibraryView";
import { MobileHeader } from "./components/MobileHeader";
import { MobileNav } from "./components/MobileNav";
import { SearchView } from "./components/SearchView";
import { Sidebar } from "./components/Sidebar";
import { UploadView } from "./components/UploadView";

function MainView() {
  const { state } = useApp();

  switch (state.view) {
    case "library":
      return <LibraryView />;
    case "upload":
      return <UploadView />;
    case "search":
    default:
      return <SearchView />;
  }
}

export default function App() {
  const { state } = useApp();

  return (
    <div className="flex h-[100dvh] bg-[var(--chatly-bg)] text-[var(--chatly-text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileHeader />
        {!state.apiConnected && (
          <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-xs text-amber-800 sm:px-6 sm:text-sm">
            API unavailable{state.healthError ? ` — ${state.healthError}` : ""}. Some actions are
            disabled until the backend reconnects.
          </div>
        )}
        {state.apiConnected && state.health?.status === "degraded" && (
          <div className="border-b border-yellow-200 bg-yellow-50 px-4 py-2 text-center text-xs text-yellow-800 sm:px-6 sm:text-sm">
            Some backend services are degraded. Search and uploads may fail until dependencies
            recover.
          </div>
        )}
        <main className="relative min-h-0 flex-1 overflow-hidden pb-[calc(4.25rem+env(safe-area-inset-bottom,0px))] lg:pb-0">
          <MainView />
        </main>
        <MobileNav />
      </div>
    </div>
  );
}
