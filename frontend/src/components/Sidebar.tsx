import { useEffect, useState } from "react";
import { fetchUserProjects } from "../api/client";
import { useApp } from "../context/AppContext";
import type { AppView, UserProject } from "../types/api";
import { IconLibrary, IconPlus, IconSettings, IconUpload } from "./icons";

const NAV: Array<{ id: AppView; label: string; icon: typeof IconPlus }> = [
  { id: "search", label: "Chat", icon: IconPlus }, { id: "upload", label: "Upload", icon: IconUpload },
  { id: "library", label: "Library", icon: IconLibrary }, { id: "settings", label: "Settings", icon: IconSettings },
];

export function Sidebar({ compact = false }: { compact?: boolean }) {
  const { state, setView, apiUrl, logout, selectProject } = useApp();
  const [projects, setProjects] = useState<UserProject[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);

  async function loadProjects() {
    setLoading(true);
    try { setProjects((await fetchUserProjects()).projects); } finally { setLoading(false); }
  }
  useEffect(() => { void loadProjects(); }, []);
  const shown = expanded ? projects : projects.slice(0, 3);

  return <aside className={`hidden h-full shrink-0 flex-col border-r border-white/60 bg-white/20 backdrop-blur-3xl lg:flex ${compact ? "w-24" : "w-64"}`}>
    <div className="flex items-center gap-2 px-5 py-5"><div className="flex h-8 w-8 items-center justify-center rounded-xl bg-zinc-900 font-bold text-white">S</div>{!compact && <div><b className="block text-sm">Scrutinize</b><span className="block max-w-40 truncate text-[11px] text-zinc-500">{state.project?.projectName}</span></div>}</div>
    <nav className="space-y-1 px-3">{NAV.map(item => { const Icon=item.icon; return <button key={item.id} onClick={() => setView(item.id)} className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm ${state.view === item.id ? "bg-white/55 text-zinc-950" : "text-zinc-600 hover:bg-white/30"}`}><Icon className="h-4 w-4" />{!compact && item.label}</button>; })}</nav>
    {!compact && <section className={`glass-sidebar-scroll mt-5 min-h-0 px-3 ${expanded ? "flex-1 overflow-y-auto" : ""}`}>
      <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Projects</p>
      {shown.map(project => <button key={project.project_id} onClick={() => selectProject(project)} className={`mb-1 w-full truncate rounded-xl px-3 py-2 text-left text-sm ${state.project?.projectId === project.project_id ? "bg-zinc-900 text-white" : "hover:bg-white/40"}`}>{project.name}</button>)}
      {projects.length > 3 && <button onClick={() => { const next=!expanded; setExpanded(next); if(next) void loadProjects(); }} className="w-full px-3 py-2 text-left text-xs font-medium text-zinc-500">{loading ? "Loading…" : expanded ? "⌃ Show less" : "⌄ Expand all"}</button>}
    </section>}
    <div className="mt-auto border-t border-white/30 p-4">{!compact && <p className="mb-3 truncate font-mono text-[10px] text-zinc-400">{apiUrl}</p>}<button onClick={logout} className="w-full rounded-xl bg-white/40 py-2 text-xs font-semibold">Sign out</button></div>
  </aside>;
}
