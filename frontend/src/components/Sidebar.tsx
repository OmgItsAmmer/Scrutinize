import { useApp } from "../context/AppContext";
import type { AppView } from "../types/api";
import { IconLibrary, IconPlus, IconUpload, IconSettings } from "./icons";

const NAV_ITEMS: {
  id: AppView;
  label: string;
  icon: typeof IconPlus;
  clearSearch?: boolean;
}[] = [
  { id: "search", label: "Chat", icon: IconPlus },
  { id: "upload", label: "Upload", icon: IconUpload },
  { id: "library", label: "My Library", icon: IconLibrary },
  { id: "settings", label: "Settings", icon: IconSettings },
];

type SidebarProps = {
  compact?: boolean;
};

export function Sidebar({ compact = false }: SidebarProps) {
  const { state, setView, clearSearch, apiUrl, logout } = useApp();

  function handleNav(view: AppView, clear?: boolean) {
    if (clear) {
      clearSearch();
    }
    setView(view);
  }

  return (
    <aside
      className={`hidden h-full shrink-0 flex-col border-r border-white/60 bg-white/20 backdrop-blur-3xl saturate-150 transition-all duration-500 ease-out lg:flex ${
        compact ? "w-24" : "w-64"
      }`}
    >
      <div className={`flex items-center gap-2 px-5 py-5 ${compact ? "justify-center" : ""}`}>
        <div className="flex h-8 w-8 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,rgba(17,17,17,0.95),rgba(59,59,59,0.8))] text-sm font-bold text-white shadow-md">
          S
        </div>
        <div
          className={`flex min-w-0 flex-col transition-all duration-500 ${
            compact ? "w-0 overflow-hidden opacity-0" : "opacity-100"
          }`}
        >
          <span className="text-sm font-semibold tracking-tight text-zinc-900">Scrutinize</span>
          {state.project && (
            <span className="max-w-[140px] truncate text-[11px] font-medium text-zinc-500">
              {state.project.projectName}
            </span>
          )}
        </div>
      </div>

      <nav className={`flex flex-1 flex-col gap-1 px-3 ${compact ? "items-center" : ""}`}>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = state.view === item.id;
          return (
            <button
              key={item.label}
              type="button"
              onClick={() => handleNav(item.id, item.clearSearch)}
              className={`group flex items-center rounded-2xl px-3 py-2.5 text-sm font-medium transition-all duration-300 border ${
                active
                  ? "bg-white/50 text-zinc-950 border-white/65 shadow-[0_8px_24px_rgba(0,0,0,0.02)] scale-[1.02] backdrop-blur-md"
                  : "text-zinc-600 border-transparent hover:bg-white/30 hover:border-white/40 hover:text-zinc-900 hover:scale-[1.01]"
              } ${compact ? "w-12 justify-center gap-0 px-0" : "gap-3"}`}
            >
              <Icon className="h-4 w-4 shrink-0 transition-transform duration-300 group-hover:scale-110" />
              <span
                className={`whitespace-nowrap transition-all duration-300 ${
                  compact ? "w-0 overflow-hidden opacity-0" : "opacity-100"
                }`}
              >
                {item.label}
              </span>
            </button>
          );
        })}
      </nav>

      <div
        className={`border-t border-white/30 px-4 py-4 space-y-3 transition-all duration-500 ${
          compact ? "pointer-events-none opacity-0" : "opacity-100"
        }`}
      >
        <div className="rounded-2xl border border-white/60 bg-white/20 p-3 text-xs text-zinc-700 shadow-[0_8px_24px_rgba(0,0,0,0.02)] backdrop-blur-xl">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-semibold text-zinc-800">API</span>
            <span
              className={`rounded-full px-2 py-0.5 font-medium ${
                state.apiConnected
                  ? "bg-emerald-100/70 text-emerald-700"
                  : "bg-rose-100/70 text-rose-700"
              }`}
            >
              {state.apiConnected ? "Connected" : "Offline"}
            </span>
          </div>
          <p className="truncate font-mono text-[11px] text-zinc-600">{apiUrl}</p>
          {state.health && <p className="mt-1 text-[11px] text-zinc-600">v{state.health.version}</p>}
        </div>

        <button
          type="button"
          onClick={logout}
          className="flex w-full items-center justify-center gap-2 rounded-2xl border border-white/60 bg-white/35 px-3 py-2 text-xs font-semibold text-zinc-700 shadow-sm transition hover:bg-white/55 hover:text-zinc-950 active:scale-98"
        >
          Sign Out
        </button>
      </div>
    </aside>
  );
}
