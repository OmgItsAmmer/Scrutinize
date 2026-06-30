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

export function Sidebar() {
  const { state, setView, clearSearch, apiUrl, logout } = useApp();

  function handleNav(view: AppView, clear?: boolean) {
    if (clear) {
      clearSearch();
    }
    setView(view);
  }

  return (
    <aside className="hidden h-full w-64 shrink-0 flex-col border-r border-zinc-200 bg-white lg:flex">
      <div className="flex items-center gap-2 px-5 py-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-zinc-900 text-sm font-bold text-white">
          S
        </div>
        <div className="flex flex-col min-w-0">
          <span className="text-sm font-semibold tracking-tight text-zinc-900">Scrutinize</span>
          {state.project && (
            <span className="text-[11px] text-zinc-500 truncate font-medium max-w-[140px]">
              {state.project.projectName}
            </span>
          )}
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-3">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = state.view === item.id;
          return (
            <button
              key={item.label}
              type="button"
              onClick={() => handleNav(item.id, item.clearSearch)}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                active
                  ? "bg-zinc-100 text-zinc-900"
                  : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900"
              }`}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </button>
          );
        })}
      </nav>

      <div className="border-t border-zinc-200 px-4 py-4 space-y-3">
        <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-600">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-medium text-zinc-800">API</span>
            <span
              className={`rounded-full px-2 py-0.5 font-medium ${
                state.apiConnected
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-rose-100 text-rose-700"
              }`}
            >
              {state.apiConnected ? "Connected" : "Offline"}
            </span>
          </div>
          <p className="truncate font-mono text-[11px] text-zinc-500">{apiUrl}</p>
          {state.health && (
            <p className="mt-1 text-[11px] text-zinc-500">v{state.health.version}</p>
          )}
        </div>

        <button
          type="button"
          onClick={logout}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-zinc-200 bg-white px-3 py-2 text-xs font-semibold text-zinc-700 shadow-sm hover:bg-zinc-50 hover:text-zinc-950 transition"
        >
          Sign Out
        </button>
      </div>
    </aside>
  );
}
