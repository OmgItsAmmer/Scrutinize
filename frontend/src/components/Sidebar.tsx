import { useEffect, useState } from "react";
import { fetchUserProjects, createUserProject, fetchCurrentUser } from "../api/client";
import { useApp } from "../context/AppContext";
import type { AppView, UserProject } from "../types/api";
import { IconLibrary, IconPlus, IconSettings, IconUpload, IconX } from "./icons";

const NAV: Array<{ id: AppView; label: string; icon: typeof IconPlus }> = [
  { id: "search", label: "Chat", icon: IconPlus }, { id: "upload", label: "Upload", icon: IconUpload },
  { id: "library", label: "Library", icon: IconLibrary },
];

export function Sidebar({ compact = false }: { compact?: boolean }) {
  const { state, setView, logout, selectProject } = useApp();
  const [projects, setProjects] = useState<UserProject[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [userEmail, setUserEmail] = useState("");

  // Project Creation Modal State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  async function loadProjects() {
    setLoading(true);
    try { setProjects((await fetchUserProjects()).projects); } finally { setLoading(false); }
  }
  
  useEffect(() => {
    void loadProjects();
    async function loadUser() {
      try {
        const u = await fetchCurrentUser();
        setUserEmail(u.email);
      } catch (err) {
        console.error("Failed to load user info", err);
      }
    }
    void loadUser();
  }, []);

  const shown = expanded ? projects : projects.slice(0, 3);

  async function handleCreateProject(e: React.FormEvent) {
    e.preventDefault();
    if (!newProjectName.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      const newProj = await createUserProject(newProjectName.trim());
      // Refresh project list
      await loadProjects();
      // Select the new project
      selectProject(newProj);
      // Reset and close
      setNewProjectName("");
      setShowCreateModal(false);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setCreating(false);
    }
  }

  return (
    <>
      <aside className={`hidden h-full shrink-0 flex-col border-r border-white/60 bg-white/20 backdrop-blur-3xl lg:flex ${compact ? "w-24" : "w-64"}`}>
        <div className="flex items-center gap-2 px-5 py-5"><div className="flex h-8 w-8 items-center justify-center rounded-xl bg-zinc-900 font-bold text-white">S</div>{!compact && <div><b className="block text-sm">Scrutinize</b><span className="block max-w-40 truncate text-[11px] text-zinc-500">{state.project?.projectName}</span></div>}</div>
        <nav className="space-y-1 px-3">{NAV.map(item => { const Icon=item.icon; return <button key={item.id} onClick={() => setView(item.id)} className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm ${state.view === item.id ? "bg-white/55 text-zinc-950" : "text-zinc-600 hover:bg-white/30"}`}><Icon className="h-4 w-4" />{!compact && item.label}</button>; })}</nav>
        {!compact && <section className={`glass-sidebar-scroll mt-5 min-h-0 px-3 ${expanded ? "flex-1 overflow-y-auto" : ""}`}>
          <div className="flex items-center justify-between px-3 pb-2">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Projects</p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex h-5 w-5 items-center justify-center rounded bg-zinc-900 text-white hover:bg-black transition-colors"
              title="Create New Project"
            >
              <IconPlus className="h-3 w-3 stroke-[2.5]" />
            </button>
          </div>
          {shown.map(project => <button key={project.project_id} onClick={() => selectProject(project)} className={`mb-1 w-full truncate rounded-xl px-3 py-2 text-left text-sm ${state.project?.projectId === project.project_id ? "bg-zinc-900 text-white" : "hover:bg-white/40"}`}>{project.name}</button>)}
          {projects.length > 3 && <button onClick={() => { const next=!expanded; setExpanded(next); if(next) void loadProjects(); }} className="w-full px-3 py-2 text-left text-xs font-medium text-zinc-500">{loading ? "Loading…" : expanded ? "⌃ Show less" : "⌄ Expand all"}</button>}
        </section>}
        <div className="mt-auto border-t border-white/30 p-4">
          {!compact && (
            <div className="mb-3 flex items-center justify-between gap-2 rounded-xl bg-white/40 p-2 border border-white/60">
              <span className="truncate text-xs font-medium text-zinc-700" title={userEmail}>
                {userEmail || "Loading profile..."}
              </span>
              <button
                onClick={() => setView("settings")}
                className="flex h-6 w-6 shrink-0 items-center justify-center bg-transparent text-black hover:bg-black/5 rounded-lg transition-colors"
                title="Settings"
              >
                <IconSettings className="h-4 w-4 stroke-[2.5]" />
              </button>
            </div>
          )}
          <button onClick={logout} className="w-full rounded-xl bg-white/40 py-2 text-xs font-semibold hover:bg-white/60 transition-colors">Sign out</button>
        </div>
      </aside>  

      {/* Create Project Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-white/20 bg-zinc-950 p-6 text-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="text-lg font-bold">Create New Project</h3>
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setNewProjectName("");
                  setCreateError(null);
                }}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-900 hover:text-white"
              >
                <IconX className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreateProject} className="mt-4 space-y-4">
              <div>
                <label htmlFor="projectName" className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                  Project Name
                </label>
                <input
                  type="text"
                  id="projectName"
                  required
                  placeholder="e.g. Financial Report Analysis"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  className="mt-2 w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
                  disabled={creating}
                  autoFocus
                />
              </div>

              {createError && (
                <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-3 text-xs text-red-400">
                  {createError}
                </div>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false);
                    setNewProjectName("");
                    setCreateError(null);
                  }}
                  className="rounded-lg border border-zinc-800 px-4 py-2 text-xs font-semibold hover:bg-zinc-900 transition-colors"
                  disabled={creating}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-white px-4 py-2 text-xs font-semibold text-black hover:bg-zinc-200 transition-colors flex items-center gap-1.5"
                  disabled={creating || !newProjectName.trim()}
                >
                  {creating ? (
                    <>
                      <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-black border-t-transparent"></div>
                      Creating...
                    </>
                  ) : (
                    "Create Project"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
