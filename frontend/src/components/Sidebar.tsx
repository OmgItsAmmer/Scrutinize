import { useEffect, useState } from "react";
import { fetchUserProjects, createUserProject, fetchCurrentUser, fetchConversations } from "../api/client";
import { useApp } from "../context/AppContext";
import type { ConversationItem, UserProject } from "../types/api";
import { IconChevronDown, IconPlus, IconSettings, IconX } from "./icons";

export function Sidebar({ compact = false }: { compact?: boolean }) {
  const { state, setView, logout, selectProject, selectConversation } = useApp();
  const [projects, setProjects] = useState<UserProject[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [chatsExpanded, setChatsExpanded] = useState(true);
  const [chats, setChats] = useState<ConversationItem[]>([]);
  const [expandedProjects, setExpandedProjects] = useState<Record<string, boolean>>({});
  const [projectChats, setProjectChats] = useState<Record<string, ConversationItem[]>>({});
  const [projectChatsLoading, setProjectChatsLoading] = useState<Record<string, boolean>>({});
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

  async function loadGeneralChats() {
    try {
      const result = await fetchConversations("general");
      setChats(result.conversations);
    } catch {
      setChats([]);
    }
  }
  
  useEffect(() => {
    void loadProjects();
    void loadGeneralChats();
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

  useEffect(() => {
    function handleConversationChange(event: Event) {
      const detail = (event as CustomEvent<{ scope?: string; projectId?: string }>).detail;
      if (detail?.scope === "project" && detail.projectId) {
        void loadProjectChats(detail.projectId);
        return;
      }
      void loadGeneralChats();
    }

    window.addEventListener("scrutinize:conversations-changed", handleConversationChange);
    return () => {
      window.removeEventListener("scrutinize:conversations-changed", handleConversationChange);
    };
  }, []);

  useEffect(() => {
    if (!state.project?.projectId) return;
    setExpandedProjects((current) => ({ ...current, [state.project!.projectId]: true }));
    void loadProjectChats(state.project.projectId);
  }, [state.project?.projectId]);

  const shown = expanded ? projects : projects.slice(0, 3);

  async function loadProjectChats(projectId: string) {
    if (projectChatsLoading[projectId]) return;
    setProjectChatsLoading((current) => ({ ...current, [projectId]: true }));
    try {
      const result = await fetchConversations("project", projectId);
      setProjectChats((current) => ({ ...current, [projectId]: result.conversations }));
    } catch {
      setProjectChats((current) => ({ ...current, [projectId]: [] }));
    } finally {
      setProjectChatsLoading((current) => ({ ...current, [projectId]: false }));
    }
  }

  function toggleProject(project: UserProject) {
    const nextExpanded = !expandedProjects[project.project_id];
    setExpandedProjects((current) => ({ ...current, [project.project_id]: nextExpanded }));
    selectProject(project);
    if (nextExpanded || !projectChats[project.project_id]) {
      void loadProjectChats(project.project_id);
    }
  }

  function openProjectChat(project: UserProject, conversationId: string | null) {
    selectProject(project);
    selectConversation(conversationId, "project");
    setExpandedProjects((current) => ({ ...current, [project.project_id]: true }));
    if (!projectChats[project.project_id]) {
      void loadProjectChats(project.project_id);
    }
  }

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
      <aside className={`hidden h-full shrink-0 flex-col border-r border-[var(--app-border)] bg-[var(--app-bg-glass)] backdrop-blur-3xl lg:flex ${compact ? "w-24" : "w-64"}`}>
        <div className="flex items-center gap-2 px-5 py-5"><div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--app-primary)] font-bold text-[var(--app-primary-text)]">S</div>{!compact && <div><b className="block text-sm text-[var(--app-text)]">Scrutinize</b><span className="block max-w-40 truncate text-[11px] text-[var(--app-text-muted)]">{state.project?.projectName}</span></div>}</div>
        {!compact && <div className="glass-sidebar-scroll min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        <section className="mt-2">
          <div className="flex items-center justify-between px-3 pb-2">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--app-text-faint)]">Projects</p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex h-5 w-5 items-center justify-center rounded bg-[var(--app-primary)] text-[var(--app-primary-text)] transition-colors hover:bg-[var(--app-primary-hover)]"
              title="Create New Project"
            >
              <IconPlus className="h-3 w-3 stroke-[2.5]" />
            </button>
          </div>
          <div className="space-y-1">
            {shown.map((project) => {
              const selected = state.project?.projectId === project.project_id;
              const projectOpen = Boolean(expandedProjects[project.project_id]);
              const recent = projectChats[project.project_id] ?? [];
              const chatsLoading = Boolean(projectChatsLoading[project.project_id]);

              return (
                <div key={project.project_id} className="rounded-xl">
                  <div
                    className={`flex items-center gap-1 rounded-xl ${
                      selected ? "bg-[var(--app-primary)] text-[var(--app-primary-text)]" : "text-[var(--app-text-soft)] hover:bg-[var(--app-bg-glass-strong)]"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => toggleProject(project)}
                      className="flex min-w-0 flex-1 items-center gap-2 px-3 py-2 text-left text-sm"
                    >
                      <IconChevronDown
                        className={`h-3.5 w-3.5 shrink-0 transition-transform ${
                          projectOpen ? "rotate-0" : "-rotate-90"
                        }`}
                      />
                      <span className="truncate">{project.name}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => openProjectChat(project, null)}
                      className={`mr-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg ${
                        selected ? "text-[var(--app-primary-text)] hover:bg-white/10" : "text-[var(--app-text-muted)] hover:bg-[var(--app-bg-glass-strong)]"
                      }`}
                      title="New project chat"
                    >
                      <IconPlus className="h-3.5 w-3.5" />
                    </button>
                  </div>

                  {projectOpen && (
                    <div className="ml-6 mt-1 space-y-0.5 border-l border-[var(--app-border-strong)] pl-2">
                      {chatsLoading && (
                        <p className="px-2 py-1.5 text-xs text-[var(--app-text-faint)]">Loading chats...</p>
                      )}
                      {!chatsLoading && recent.length === 0 && (
                        <button
                          type="button"
                          onClick={() => openProjectChat(project, null)}
                          className="w-full truncate rounded-lg px-2 py-1.5 text-left text-xs text-[var(--app-text-muted)] hover:bg-[var(--app-bg-glass-strong)]"
                        >
                          New chat
                        </button>
                      )}
                      {recent.slice(0, 8).map((chat) => (
                        <button
                          key={chat.id}
                          type="button"
                          onClick={() => openProjectChat(project, chat.id)}
                          className={`w-full truncate rounded-lg px-2 py-1.5 text-left text-xs ${
                            state.activeConversationId === chat.id && selected
                              ? "bg-white/15 text-[var(--app-primary-text)]"
                              : "text-[var(--app-text-muted)] hover:bg-[var(--app-bg-glass-strong)] hover:text-[var(--app-text)]"
                          }`}
                        >
                          {chat.title}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {projects.length > 3 && <button onClick={() => { const next=!expanded; setExpanded(next); if(next) void loadProjects(); }} className="w-full px-3 py-2 text-left text-xs font-medium text-[var(--app-text-muted)]">{loading ? "Loading..." : expanded ? "Show less" : "Expand all"}</button>}
        </section>
        <section className="mt-5 border-t border-[var(--app-border)] pt-4">
          <div className="flex items-center justify-between px-3 pb-2">
            <button onClick={() => setChatsExpanded((value) => !value)} aria-expanded={chatsExpanded} className="text-[11px] font-semibold uppercase tracking-wider text-[var(--app-text-faint)]">Chats {chatsExpanded ? "Open" : "Closed"}</button>
            <button onClick={() => selectConversation(null, "general-chat")} className="flex h-5 w-5 items-center justify-center rounded bg-[var(--app-primary)] text-[var(--app-primary-text)]" title="New web chat"><IconPlus className="h-3 w-3" /></button>
          </div>
          {chatsExpanded && <div className="space-y-1">
            <button onClick={() => selectConversation(null, "general-chat")} className="w-full rounded-xl px-3 py-2 text-left text-sm font-medium text-[var(--app-text-soft)] hover:bg-[var(--app-bg-glass-strong)]">New chat</button>
            {chats.map((chat) => <button key={chat.id} onClick={() => selectConversation(chat.id, "general-chat")} className={`w-full truncate rounded-xl px-3 py-2 text-left text-sm ${state.activeConversationId === chat.id && state.view === "general-chat" ? "bg-[var(--app-primary)] text-[var(--app-primary-text)]" : "text-[var(--app-text-muted)] hover:bg-[var(--app-bg-glass-strong)]"}`}>{chat.title}</button>)}
          </div>}
        </section>
        </div>}
        <div className="mt-auto border-t border-[var(--app-border)] p-4">
          {!compact && (
            <div className="mb-3 flex items-center justify-between gap-2 rounded-xl border border-[var(--app-border)] bg-[var(--app-bg-glass-strong)] p-2">
              <span className="truncate text-xs font-medium text-[var(--app-text-soft)]" title={userEmail}>
                {userEmail || "Loading profile..."}
              </span>
              <button
                onClick={() => setView("account-settings")}
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-transparent text-[var(--app-primary)] transition-colors hover:bg-black/5"
                title="Account settings"
              >
                <IconSettings className="h-4 w-4 stroke-[2.5]" />
              </button>
            </div>
          )}
          <button onClick={logout} className="w-full rounded-xl border border-[var(--app-border)] bg-[var(--app-bg-glass-strong)] py-2 text-xs font-semibold text-[var(--app-text)] transition-colors hover:bg-white/70">Sign out</button>
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
