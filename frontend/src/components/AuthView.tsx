import React, { useState } from "react";
import { useApp } from "../context/AppContext";
import { loginProject, signupProject } from "../api/client";

export function AuthView() {
  const { login } = useApp();
  const [isSignUp, setIsSignUp] = useState(false);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !password) {
      setError("Please fill in all fields.");
      return;
    }
    setError(null);
    setLoading(true);

    try {
      if (isSignUp) {
        // Register the new project namespace
        const response = await signupProject(name.trim(), password);
        login(name.trim(), response.api_key, response.client_key, response.project_id);
      } else {
        // Authenticate into the project namespace
        const response = await loginProject(name.trim(), password);
        login(name.trim(), response.api_key, response.client_key, response.project_id);
      }
    } catch (err: any) {
      setError(err.message || "Authentication failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-zinc-50 px-4 py-12 text-zinc-900 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8 rounded-2xl border border-zinc-200 bg-white p-8 shadow-sm">
        <div className="text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-900 text-lg font-bold text-white shadow-sm">
            S
          </div>
          <h2 className="mt-6 text-3xl font-bold tracking-tight text-zinc-900">
            {isSignUp ? "Create a Scrutinize Project" : "Sign in to your Project"}
          </h2>
          <p className="mt-2 text-sm text-zinc-600">
            Scrutinize hosts your private documents and search index under your project namespace.
          </p>
        </div>

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            <span className="font-semibold">Error:</span> {error}
          </div>
        )}

        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-4 rounded-md">
            <div>
              <label htmlFor="project-name" className="block text-sm font-medium text-zinc-700">
                Project Name
              </label>
              <input
                id="project-name"
                name="name"
                type="text"
                required
                disabled={loading}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. support-chatbot"
                className="mt-1 block w-full rounded-xl border border-zinc-300 bg-white px-3.5 py-2.5 text-zinc-900 shadow-sm placeholder:text-zinc-400 focus:border-zinc-900 focus:outline-none focus:ring-1 focus:ring-zinc-900 disabled:opacity-50 sm:text-sm"
              />
            </div>
            <div>
              <label htmlFor="project-password" className="block text-sm font-medium text-zinc-700">
                Password
              </label>
              <input
                id="project-password"
                name="password"
                type="password"
                required
                disabled={loading}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="mt-1 block w-full rounded-xl border border-zinc-300 bg-white px-3.5 py-2.5 text-zinc-900 shadow-sm placeholder:text-zinc-400 focus:border-zinc-900 focus:outline-none focus:ring-1 focus:ring-zinc-900 disabled:opacity-50 sm:text-sm"
              />
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={loading}
              className="group relative flex w-full justify-center rounded-xl bg-zinc-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-zinc-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 disabled:opacity-50"
            >
              {loading ? (
                <svg
                  className="h-5 w-5 animate-spin text-white"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
              ) : isSignUp ? (
                "Create Project & Log In"
              ) : (
                "Sign In"
              )}
            </button>
          </div>
        </form>

        <div className="text-center">
          <button
            type="button"
            disabled={loading}
            onClick={() => {
              setIsSignUp(!isSignUp);
              setError(null);
            }}
            className="text-sm font-medium text-zinc-600 hover:text-zinc-900 hover:underline"
          >
            {isSignUp
              ? "Already have a project? Sign in instead"
              : "Need a new workspace? Create a project"}
          </button>
        </div>
      </div>
    </div>
  );
}
