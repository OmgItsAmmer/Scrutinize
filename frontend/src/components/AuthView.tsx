import React, { useState } from "react";
import { useApp } from "../context/AppContext";
import { loginProject, resetProjectPassword, signupProject } from "../api/client";

export function AuthView() {
  const { login } = useApp();
  const [isSignUp, setIsSignUp] = useState(false);
  const [isForgotPassword, setIsForgotPassword] = useState(false);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  function resetFormState() {
    setError(null);
    setSuccess(null);
    setPassword("");
    setApiKey("");
    setNewPassword("");
    setConfirmPassword("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !password) {
      setError("Please fill in all fields.");
      return;
    }
    setError(null);
    setSuccess(null);
    setLoading(true);

    try {
      if (isSignUp) {
        const response = await signupProject(name.trim(), password);
        login(name.trim(), response.api_key, response.client_key, response.project_id);
      } else {
        const response = await loginProject(name.trim(), password);
        login(name.trim(), response.api_key, response.client_key, response.project_id);
      }
    } catch (err: any) {
      setError(err.message || "Authentication failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  }

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!name.trim() || !apiKey.trim() || !newPassword) {
      setError("Please fill in all fields.");
      return;
    }
    if (newPassword.length < 6) {
      setError("New password must be at least 6 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      await resetProjectPassword(name.trim(), apiKey.trim(), newPassword);
      setSuccess("Password updated. You can sign in with your new password.");
      setIsForgotPassword(false);
      setPassword(newPassword);
      setApiKey("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: any) {
      setError(err.message || "Password reset failed.");
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
            {isForgotPassword
              ? "Reset your password"
              : isSignUp
                ? "Create a Scrutinize Project"
                : "Sign in to your Project"}
          </h2>
          <p className="mt-2 text-sm text-zinc-600">
            {isForgotPassword
              ? "Use your project name and admin API key to set a new login password."
              : "Scrutinize hosts your private documents and search index under your project namespace."}
          </p>
        </div>

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            <span className="font-semibold">Error:</span> {error}
          </div>
        )}

        {success && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
            {success}
          </div>
        )}

        {isForgotPassword ? (
          <form className="mt-8 space-y-6" onSubmit={handleResetPassword}>
            <div className="space-y-4">
              <div>
                <label htmlFor="reset-project-name" className="block text-sm font-medium text-zinc-700">
                  Project Name
                </label>
                <input
                  id="reset-project-name"
                  type="text"
                  required
                  disabled={loading}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="mt-1 block w-full rounded-xl border border-zinc-300 bg-white px-3.5 py-2.5 text-sm shadow-sm focus:border-zinc-900 focus:outline-none focus:ring-1 focus:ring-zinc-900 disabled:opacity-50"
                />
              </div>
              <div>
                <label htmlFor="reset-api-key" className="block text-sm font-medium text-zinc-700">
                  Admin API Key
                </label>
                <input
                  id="reset-api-key"
                  type="text"
                  required
                  disabled={loading}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="scrutinize_sk_..."
                  className="mt-1 block w-full rounded-xl border border-zinc-300 bg-white px-3.5 py-2.5 font-mono text-sm shadow-sm focus:border-zinc-900 focus:outline-none focus:ring-1 focus:ring-zinc-900 disabled:opacity-50"
                />
              </div>
              <div>
                <label htmlFor="reset-new-password" className="block text-sm font-medium text-zinc-700">
                  New Password
                </label>
                <input
                  id="reset-new-password"
                  type="password"
                  required
                  minLength={6}
                  disabled={loading}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="mt-1 block w-full rounded-xl border border-zinc-300 bg-white px-3.5 py-2.5 text-sm shadow-sm focus:border-zinc-900 focus:outline-none focus:ring-1 focus:ring-zinc-900 disabled:opacity-50"
                />
              </div>
              <div>
                <label htmlFor="reset-confirm-password" className="block text-sm font-medium text-zinc-700">
                  Confirm New Password
                </label>
                <input
                  id="reset-confirm-password"
                  type="password"
                  required
                  minLength={6}
                  disabled={loading}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="mt-1 block w-full rounded-xl border border-zinc-300 bg-white px-3.5 py-2.5 text-sm shadow-sm focus:border-zinc-900 focus:outline-none focus:ring-1 focus:ring-zinc-900 disabled:opacity-50"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="flex w-full justify-center rounded-xl bg-zinc-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:opacity-50"
            >
              {loading ? "Updating..." : "Reset Password"}
            </button>
          </form>
        ) : (
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
                {loading ? "Please wait..." : isSignUp ? "Create Project & Log In" : "Sign In"}
              </button>
            </div>
          </form>
        )}

        <div className="space-y-2 text-center">
          {!isSignUp && !isForgotPassword && (
            <button
              type="button"
              disabled={loading}
              onClick={() => {
                setIsForgotPassword(true);
                resetFormState();
              }}
              className="block w-full text-sm font-medium text-zinc-600 hover:text-zinc-900 hover:underline"
            >
              Forgot password?
            </button>
          )}
          <button
            type="button"
            disabled={loading}
            onClick={() => {
              if (isForgotPassword) {
                setIsForgotPassword(false);
              } else {
                setIsSignUp(!isSignUp);
              }
              resetFormState();
            }}
            className="text-sm font-medium text-zinc-600 hover:text-zinc-900 hover:underline"
          >
            {isForgotPassword
              ? "Back to sign in"
              : isSignUp
                ? "Already have a project? Sign in instead"
                : "Need a new workspace? Create a project"}
          </button>
        </div>
      </div>
    </div>
  );
}
