import { useEffect, useState } from "react";

type DependencyCheck = {
  status: string;
  detail?: string | null;
};

type HealthResponse = {
  status: string;
  service: string;
  version: string;
  checks: Record<string, DependencyCheck>;
};

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchHealth() {
      try {
        const response = await fetch(`${API_URL}/health`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data: HealthResponse = await response.json();
        if (!cancelled) {
          setHealth(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setHealth(null);
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const connected = health?.status === "ok";

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center gap-8 px-6">
      <div className="text-center">
        <p className="text-sm uppercase tracking-[0.3em] text-slate-400">Scrutinize</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">
          Multi-modal search, one question
        </h1>
        <p className="mt-3 text-slate-400">
          Upload text, audio, and video — then search across everything.
        </p>
      </div>

      <div className="w-full rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl">
        <div className="flex items-center justify-between gap-4">
          <span className="text-sm font-medium text-slate-300">API status</span>
          {loading ? (
            <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-400">
              Checking…
            </span>
          ) : connected ? (
            <span className="rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-medium text-emerald-400">
              API connected
            </span>
          ) : (
            <span className="rounded-full bg-rose-500/15 px-3 py-1 text-xs font-medium text-rose-400">
              API unavailable
            </span>
          )}
        </div>

        {error && (
          <p className="mt-4 text-sm text-rose-300">
            Could not reach {API_URL}/health — {error}
          </p>
        )}

        {health && (
          <dl className="mt-4 grid gap-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-slate-400">Service</dt>
              <dd className="font-mono text-slate-200">{health.service}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-400">Version</dt>
              <dd className="font-mono text-slate-200">{health.version}</dd>
            </div>
            {Object.entries(health.checks).map(([name, check]) => (
              <div key={name} className="flex justify-between gap-4">
                <dt className="capitalize text-slate-400">{name}</dt>
                <dd className={check.status === "ok" ? "text-emerald-400" : "text-amber-400"}>
                  {check.status}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </main>
  );
}
