import { useApp } from "../context/AppContext";

export function MobileHeader() {
  const { state } = useApp();

  return (
    <header
      className="flex shrink-0 items-center justify-between border-b border-zinc-200 bg-white px-4 py-3 lg:hidden"
      style={{ paddingTop: "max(0.75rem, env(safe-area-inset-top, 0px))" }}
    >
      <div className="flex items-center gap-2 min-w-0">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-zinc-900 text-xs font-bold text-white">
          S
        </div>
        <span className="truncate text-base font-semibold tracking-tight text-zinc-900">Scrutinize</span>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <span
          className={`h-2 w-2 rounded-full ${
            state.apiConnected ? "bg-emerald-500" : "bg-rose-500"
          }`}
          aria-hidden="true"
        />
        <span className="text-xs font-medium text-zinc-600">
          {state.apiConnected ? "Online" : "Offline"}
        </span>
      </div>
    </header>
  );
}
