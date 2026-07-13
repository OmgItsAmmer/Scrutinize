import { useEffect, useState } from "react";
import { fetchCurrentUser, fetchUserProjects } from "../api/client";
import { useApp } from "../context/AppContext";
import type { UserProject } from "../types/api";

export function AccountSettingsView() {
  const { state, selectProject } = useApp();
  const [email, setEmail] = useState("");
  const [projects, setProjects] = useState<UserProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [user, projectList] = await Promise.all([fetchCurrentUser(), fetchUserProjects()]);
        if (cancelled) return;
        setEmail(user.email);
        setProjects(projectList.projects);
      } catch (reason) {
        if (cancelled) return;
        setError(reason instanceof Error ? reason.message : "Failed to load account settings.");
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="flex h-full min-h-0 flex-col overflow-y-auto bg-zinc-50/50 p-6 lg:p-8">
      <div className="mx-auto w-full max-w-5xl space-y-8">
        <header className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-zinc-400">
            Account settings
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-zinc-950">
            Your workspace identity
          </h1>
          <p className="max-w-2xl text-sm leading-6 text-zinc-500">
            Account-level settings live here. Project prompts, API keys, and source behavior now
            live inside each project&apos;s own settings tab.
          </p>
        </header>

        <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
          <article className="rounded-[28px] border border-white/70 bg-white/55 p-6 shadow-[0_20px_80px_rgba(15,23,42,0.08)] backdrop-blur-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-400">
              Profile
            </p>
            <div className="mt-5 flex items-center gap-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-zinc-950 text-lg font-semibold text-white">
                {(email || state.project?.projectName || "S").slice(0, 1).toUpperCase()}
              </div>
              <div className="min-w-0">
                <h2 className="truncate text-lg font-semibold text-zinc-950">
                  {loading ? "Loading account..." : email || "Unknown account"}
                </h2>
                <p className="text-sm text-zinc-500">
                  Signed in to manage projects, chats, sources, and project-level prompts.
                </p>
              </div>
            </div>
          </article>

          <article className="rounded-[28px] border border-white/70 bg-white/40 p-6 shadow-[0_20px_80px_rgba(15,23,42,0.06)] backdrop-blur-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-400">
              Summary
            </p>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <div className="rounded-2xl border border-white/80 bg-white/70 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-400">
                  Projects
                </p>
                <p className="mt-2 text-2xl font-semibold text-zinc-950">{projects.length}</p>
              </div>
              <div className="rounded-2xl border border-white/80 bg-white/70 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-400">
                  Active
                </p>
                <p className="mt-2 truncate text-sm font-semibold text-zinc-950">
                  {state.project?.projectName ?? "No project"}
                </p>
              </div>
            </div>
          </article>
        </div>

        <article className="rounded-[28px] border border-white/70 bg-white/55 p-6 shadow-[0_20px_80px_rgba(15,23,42,0.08)] backdrop-blur-3xl">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-400">
                Projects
              </p>
              <h2 className="mt-2 text-xl font-semibold text-zinc-950">Jump into a project</h2>
            </div>
            {error && <p className="text-sm text-rose-600">{error}</p>}
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-2">
            {projects.map((project) => {
              const selected = state.project?.projectId === project.project_id;
              return (
                <button
                  key={project.project_id}
                  type="button"
                  onClick={() => selectProject(project)}
                  className={`rounded-3xl border px-5 py-4 text-left transition duration-200 ${
                    selected
                      ? "border-zinc-900 bg-zinc-900 text-white shadow-[0_16px_40px_rgba(15,23,42,0.22)]"
                      : "border-white/80 bg-white/70 text-zinc-800 hover:-translate-y-0.5 hover:bg-white"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold">{project.name}</p>
                      <p
                        className={`mt-1 text-xs ${
                          selected ? "text-white/70" : "text-zinc-500"
                        }`}
                      >
                        {project.role}
                      </p>
                    </div>
                    <span
                      className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                        selected ? "bg-white/12 text-white" : "bg-zinc-900/6 text-zinc-600"
                      }`}
                    >
                      {selected ? "Current" : "Open"}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          {!loading && projects.length === 0 && (
            <p className="mt-5 text-sm text-zinc-500">No projects found for this account yet.</p>
          )}
        </article>
      </div>
    </section>
  );
}
