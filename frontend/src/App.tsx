import { useApp } from "./context/AppContext";
import { LibraryView } from "./components/LibraryView";
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
    <div className="flex h-screen bg-[var(--chatly-bg)] text-[var(--chatly-text-primary)]">
      <Sidebar />
      <main className="relative min-w-0 flex-1">
        {!state.apiConnected && (
          <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-center text-sm text-amber-800">
            API unavailable{state.healthError ? ` — ${state.healthError}` : ""}. Some actions are
            disabled until the backend reconnects.
          </div>
        )}
        <MainView />
      </main>
    </div>
  );
}
