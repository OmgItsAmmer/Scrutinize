import { useState } from "react";
import { AccountSettingsView } from "./components/AccountSettingsView";
import { useApp } from "./context/AppContext";
import { MobileHeader } from "./components/MobileHeader";
import { MobileNav } from "./components/MobileNav";
import { ConversationChatView } from "./components/ConversationChatView";
import { ProjectWorkspace } from "./components/ProjectWorkspace";
import { Sidebar } from "./components/Sidebar";
import { AuthView } from "./components/AuthView";
import { LandingPage } from "./components/LandingPage";

function MainView() {
  const { state } = useApp();

  switch (state.view) {
    case "account-settings":
      return <AccountSettingsView />;
    case "general-chat":
      return <ConversationChatView scope="general" />;
    case "project":
    default:
      if (!state.project) {
        return <ConversationChatView scope="general" />;
      }
      return <ProjectWorkspace />;
  }
}

export default function App() {
  const { state } = useApp();
  const [showAuth, setShowAuth] = useState(false);

  if (!state.isAuthenticated) {
    if (!showAuth) {
      return <LandingPage onEnter={() => setShowAuth(true)} />;
    }
    return <AuthView />;
  }

  return (
    <div className="flex h-[100dvh] bg-[var(--chatly-bg)] text-[var(--chatly-text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileHeader />
        
        {/* Floating Notifications Container */}
        <div className="fixed top-4 right-4 z-50 flex flex-col gap-3 w-80 sm:w-96 pointer-events-none">
          {!state.apiConnected && (
            <div className="glass-panel pointer-events-auto animate-slide-in-right flex items-start gap-3 rounded-xl p-4 shadow-[var(--app-shadow)]">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-500/10 text-amber-500">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <h4 className="font-semibold text-xs text-[var(--app-text)]">API Connection Lost</h4>
                <p className="mt-1 text-[11px] leading-relaxed text-[var(--app-text-soft)]">
                  API unavailable{state.healthError ? ` — ${state.healthError}` : ""}. Some actions are
                  disabled until the backend reconnects.
                </p>
              </div>
            </div>
          )}
          {state.apiConnected && state.health?.status === "degraded" && (
            <div className="glass-panel pointer-events-auto animate-slide-in-right flex items-start gap-3 rounded-xl p-4 shadow-[var(--app-shadow)]">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-500/10 text-amber-500">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <h4 className="font-semibold text-xs text-[var(--app-text)]">Degraded Performance</h4>
                <p className="mt-1 text-[11px] leading-relaxed text-[var(--app-text-soft)]">
                  Some backend services are degraded. Search and uploads may fail until dependencies
                  recover.
                </p>
              </div>
            </div>
          )}
        </div>

        <main className="relative min-h-0 flex-1 overflow-hidden pb-[calc(4.25rem+env(safe-area-inset-bottom,0px))] lg:pb-0">
          <MainView />
        </main>
        <MobileNav />
      </div>
    </div>
  );
}
