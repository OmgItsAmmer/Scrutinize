import { AccountSettingsView } from "./components/AccountSettingsView";
import { useApp } from "./context/AppContext";
import { MobileHeader } from "./components/MobileHeader";
import { MobileNav } from "./components/MobileNav";
import { ConversationChatView } from "./components/ConversationChatView";
import { ProjectWorkspace } from "./components/ProjectWorkspace";
import { Sidebar } from "./components/Sidebar";
import { AuthView } from "./components/AuthView";

function MainView() {
  const { state } = useApp();

  switch (state.view) {
    case "account-settings":
      return <AccountSettingsView />;
    case "general-chat":
      return <ConversationChatView scope="general" />;
    case "project":
    default:
      return <ProjectWorkspace />;
  }
}

export default function App() {
  const { state } = useApp();

  if (!state.project) {
    return <AuthView />;
  }

  return (
    <div className="flex h-[100dvh] bg-[var(--chatly-bg)] text-[var(--chatly-text-primary)]">
      <Sidebar compact={state.pdfDrawer.open} />
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileHeader />
        {!state.apiConnected && (
          <div className="border-b border-[var(--app-border)] bg-[var(--app-warning-bg)] px-4 py-2 text-center text-xs text-[var(--app-warning)] backdrop-blur-xl sm:px-6 sm:text-sm">
            API unavailable{state.healthError ? ` — ${state.healthError}` : ""}. Some actions are
            disabled until the backend reconnects.
          </div>
        )}
        {state.apiConnected && state.health?.status === "degraded" && (
          <div className="border-b border-[var(--app-border)] bg-[var(--app-warning-bg)] px-4 py-2 text-center text-xs text-[var(--app-warning)] backdrop-blur-xl sm:px-6 sm:text-sm">
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
