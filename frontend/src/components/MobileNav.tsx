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
  { id: "library", label: "Library", icon: IconLibrary },
  { id: "settings", label: "Settings", icon: IconSettings },
];

export function MobileNav() {
  const { state, setView, clearSearch } = useApp();

  function handleNav(view: AppView, clear?: boolean) {
    if (clear) {
      clearSearch();
    }
    setView(view);
  }

  return (
    <nav
      className="fixed bottom-4 inset-x-4 z-40 rounded-2xl border border-white/60 bg-white/20 backdrop-blur-3xl saturate-150 shadow-[0_8px_32px_rgba(0,0,0,0.03)] lg:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
      aria-label="Main navigation"
    >
      <div className="flex items-stretch justify-around px-2 py-1.5">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = state.view === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => handleNav(item.id, item.clearSearch)}
              className={`flex min-w-0 flex-1 flex-col items-center gap-1 rounded-xl px-2 py-2 text-[11px] font-semibold transition active:scale-95 ${
                active ? "text-zinc-950" : "text-zinc-500 hover:text-zinc-700"
              }`}
              aria-current={active ? "page" : undefined}
            >
              <span
                className={`flex h-8 w-8 items-center justify-center rounded-xl border transition duration-300 ${
                  active ? "bg-white/70 border-white/80 text-zinc-950 shadow-sm" : "bg-transparent border-transparent text-zinc-500"
                }`}
              >
                <Icon className="h-4 w-4" />
              </span>
              <span className="truncate">{item.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
