import { useEffect, useState } from "react";
import { deleteConversation, deleteUserProject, fetchUserProjects, createUserProject, fetchCurrentUser, fetchConversations } from "../api/client";
import { useApp } from "../context/AppContext";
import type { ConversationItem, UserProject } from "../types/api";
import { IconPlus, IconSettings, IconTrash, IconX } from "./icons";
import { ProjectSidebarCard } from "./ProjectSidebarCard";
import { useConfirm } from "./ConfirmDialogProvider";

function notifyConversationsChanged(scope?: "general" | "project", projectId?: string) {
  window.dispatchEvent(
    new CustomEvent("scrutinize:conversations-changed", {
      detail: { scope, projectId },
    }),
  );
}

export function Sidebar({ compact = false }: { compact?: boolean }) {
  const { state, setView, setProjectChoice, logout, selectProject, selectConversation, clearProject } = useApp();
  const confirm = useConfirm();
  const [projects, setProjects] = useState<UserProject[]>([]);
  const [chatsExpanded, setChatsExpanded] = useState(true);
  const [chats, setChats] = useState<ConversationItem[]>([]);
  const [projectChats, setProjectChats] = useState<Record<string, ConversationItem[]>>({});
  const [projectChatsLoading, setProjectChatsLoading] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [userEmail, setUserEmail] = useState("");

  // Project Creation Modal State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectDescription, setNewProjectDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [deletingProjectId, setDeletingProjectId] = useState<string | null>(null);
  const [deletingChatId, setDeletingChatId] = useState<string | null>(null);

  async function loadProjects() {
    setLoading(true);
    try {
      setProjects((await fetchUserProjects()).projects);
    } catch (err) {
      console.error("Failed to load projects", err);
    } finally {
      setLoading(false);
    }
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
    void loadProjectChats(state.project.projectId);
  }, [state.project?.projectId]);

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

  function openProjectChat(project: UserProject, conversationId: string | null) {
    selectProject(project);
    selectConversation(conversationId, "project");
    if (!projectChats[project.project_id]) {
      void loadProjectChats(project.project_id);
    }
  }

  async function handleDeleteProject(projectId: string, projectName: string) {
    if (deletingProjectId) return;
    const confirmed = await confirm({
      title: "Delete project",
      description: `Delete "${projectName}"? This removes the project, its chats, and all uploaded sources. This cannot be undone.`,
      confirmLabel: "Delete project",
      tone: "danger",
    });
    if (!confirmed) return;

    setDeletingProjectId(projectId);
    try {
      await deleteUserProject(projectId);
      const refreshed = await fetchUserProjects();
      setProjects(refreshed.projects);
      setProjectChats((current) => {
        const next = { ...current };
        delete next[projectId];
        return next;
      });
      await loadGeneralChats();

      if (state.project?.projectId === projectId) {
        const remaining = refreshed.projects;
        if (remaining.length > 0) {
          selectProject(remaining[0]);
        } else {
          clearProject();
          selectConversation(null, "general-chat");
        }
      }
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Failed to delete project");
      await loadProjects();
      await loadGeneralChats();
    } finally {
      setDeletingProjectId(null);
    }
  }

  async function handleDeleteGeneralChat(conversationId: string, title: string) {
    if (deletingChatId) return;
    const confirmed = await confirm({
      title: "Delete chat",
      description: `Delete "${title}"? This chat will be removed from your history.`,
      confirmLabel: "Delete chat",
      tone: "danger",
    });
    if (!confirmed) return;

    setDeletingChatId(conversationId);
    try {
      await deleteConversation(conversationId);
      setChats((current) => current.filter((chat) => chat.id !== conversationId));
      if (state.activeConversationId === conversationId) {
        selectConversation(null, "general-chat");
      }
      notifyConversationsChanged("general");
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Failed to delete chat");
    } finally {
      setDeletingChatId(null);
    }
  }

  async function handleDeleteProjectChat(projectId: string, conversationId: string) {
    if (deletingChatId) return;
    const chat = projectChats[projectId]?.find((item) => item.id === conversationId);
    const confirmed = await confirm({
      title: "Delete chat",
      description: `Delete "${chat?.title ?? "this chat"}"? This chat will be removed from your project history.`,
      confirmLabel: "Delete chat",
      tone: "danger",
    });
    if (!confirmed) return;

    setDeletingChatId(conversationId);
    try {
      await deleteConversation(conversationId);
      setProjectChats((current) => ({
        ...current,
        [projectId]: (current[projectId] ?? []).filter((chat) => chat.id !== conversationId),
      }));
      if (state.activeConversationId === conversationId && state.project?.projectId === projectId) {
        selectConversation(null, "project");
      }
      notifyConversationsChanged("project", projectId);
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Failed to delete chat");
    } finally {
      setDeletingChatId(null);
    }
  }

  async function handleCreateProject(e: React.FormEvent) {
    e.preventDefault();
    if (!newProjectName.trim() || !newProjectDescription.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      const newProj = await createUserProject(
        newProjectName.trim(),
        newProjectDescription.trim()
      );
      // Refresh project list
      await loadProjects();
      // Select the new project
      selectProject(newProj);
      setProjectChoice("settings");
      // Reset and close
      setNewProjectName("");
      setNewProjectDescription("");
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
          <div className="project-hover-card-list">
            {projects.map((project) => {
              const selected = state.project?.projectId === project.project_id;
              const recent = projectChats[project.project_id] ?? [];
              const chatsLoading = Boolean(projectChatsLoading[project.project_id]);

              return (
                <ProjectSidebarCard
                  key={project.project_id}
                  project={project}
                  selected={selected}
                  chats={recent}
                  chatsLoading={chatsLoading}
                  activeConversationId={state.activeConversationId}
                  deletingProjectId={deletingProjectId}
                  deletingChatId={deletingChatId}
                  onHover={() => {
                    if (!projectChats[project.project_id] && !projectChatsLoading[project.project_id]) {
                      void loadProjectChats(project.project_id);
                    }
                  }}
                  onSelectProject={() => selectProject(project)}
                  onOpenChat={(conversationId) => openProjectChat(project, conversationId)}
                  onDeleteProject={(projectId) => handleDeleteProject(projectId, project.name)}
                  onDeleteChat={handleDeleteProjectChat}
                />
              );
            })}
            {loading && projects.length === 0 && (
              <p className="px-3 py-2 text-xs text-[var(--app-text-faint)]">Loading projects...</p>
            )}
            {!loading && projects.length === 0 && (
              <p className="px-3 py-2 text-xs text-[var(--app-text-faint)]">No projects yet</p>
            )}
          </div>
        </section>
        <section className="mt-5 border-t border-[var(--app-border)] pt-4">
          <div className="flex items-center justify-between px-3 pb-2">
            <button onClick={() => setChatsExpanded((value) => !value)} aria-expanded={chatsExpanded} className="text-[11px] font-semibold uppercase tracking-wider text-[var(--app-text-faint)]">Chats {chatsExpanded ? "Open" : "Closed"}</button>
            <button onClick={() => selectConversation(null, "general-chat")} className="flex h-5 w-5 items-center justify-center rounded bg-[var(--app-primary)] text-[var(--app-primary-text)]" title="New web chat"><IconPlus className="h-3 w-3" /></button>
          </div>
          {chatsExpanded && <div className="space-y-1">
            <button onClick={() => selectConversation(null, "general-chat")} className="w-full rounded-xl px-3 py-2 text-left text-sm font-medium text-[var(--app-text-soft)] hover:bg-[var(--app-bg-glass-strong)]">New chat</button>
            {chats.map((chat) => {
              const selected = state.activeConversationId === chat.id && state.view === "general-chat";
              return (
                <div key={chat.id} className="sidebar-chat-row group/chat">
                  <button
                    onClick={() => selectConversation(chat.id, "general-chat")}
                    className={`sidebar-chat-row__title ${selected ? "sidebar-chat-row__title--active" : ""}`}
                  >
                    {chat.title}
                  </button>
                  <button
                    type="button"
                    className="sidebar-chat-row__delete"
                    aria-label={`Delete chat ${chat.title}`}
                    title="Delete chat"
                    disabled={deletingChatId === chat.id}
                    onClick={() => void handleDeleteGeneralChat(chat.id, chat.title)}
                  >
                    <IconTrash className="h-3.5 w-3.5" />
                  </button>
                </div>
              );
            })}
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
                  setNewProjectDescription("");
                  setCreateError(null);
                }}
                disabled={creating}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-900 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
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

              <div>
                <label htmlFor="projectDescription" className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                  Project Description
                </label>
                <textarea
                  id="projectDescription"
                  required
                  rows={2}
                  placeholder="e.g. Analysis of tech news and AI research. Only answer questions related to AI trends, startup funding, and engineering news."
                  value={newProjectDescription}
                  onChange={(e) => setNewProjectDescription(e.target.value)}
                  className="mt-2 w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 resize-none"
                  disabled={creating}
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
                    setNewProjectDescription("");
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
                  disabled={creating || !newProjectName.trim() || !newProjectDescription.trim()}
                >
                  {creating ? (
                    <>
                      <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-black border-t-transparent"></div>
                      Generating Project...
                    </>
                  ) : (
                    "Generate Project"
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
