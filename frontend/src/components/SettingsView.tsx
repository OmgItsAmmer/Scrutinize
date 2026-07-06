import { useState, useEffect } from "react";
import { useApp } from "../context/AppContext";
import { changeProjectPassword } from "../api/client";
import { IconCopy, IconEye, IconEyeOff } from "./icons";

export function SettingsView() {
  const { state, updateSettings } = useApp();
  const [showKeys, setShowKeys] = useState(false);
  const [copiedKey, setCopiedKey] = useState<"api" | "client" | null>(null);

  // States for prompt overrides
  const [gatePrompt, setGatePrompt] = useState("");
  const [rewriterPrompt, setRewriterPrompt] = useState("");
  const [genericPrompt, setGenericPrompt] = useState("");
  const [synthesisPrompt, setSynthesisPrompt] = useState("");
  const [decisionPrompt, setDecisionPrompt] = useState("");

  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");
  const [errorText, setErrorText] = useState("");

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordStatus, setPasswordStatus] = useState<"idle" | "success" | "error">("idle");
  const [passwordError, setPasswordError] = useState("");

  // Sync prompts state when settings load
  useEffect(() => {
    if (state.project?.settings) {
      const overrides = state.project.settings.system_prompt_overrides || {};
      setGatePrompt(overrides.gate || "");
      setRewriterPrompt(overrides.rewriter || "");
      setGenericPrompt(overrides.generic || "");
      setSynthesisPrompt(overrides.synthesis || "");
      setDecisionPrompt(overrides.decision || "");
    }
  }, [state.project?.settings]);

  const handleCopy = (text: string, type: "api" | "client") => {
    navigator.clipboard.writeText(text);
    setCopiedKey(type);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordStatus("idle");
    setPasswordError("");

    if (newPassword.length < 6) {
      setPasswordStatus("error");
      setPasswordError("New password must be at least 6 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordStatus("error");
      setPasswordError("New passwords do not match.");
      return;
    }

    setPasswordSaving(true);
    try {
      await changeProjectPassword(
        newPassword,
        currentPassword.trim() ? currentPassword : undefined,
      );
      setPasswordStatus("success");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setTimeout(() => setPasswordStatus("idle"), 3000);
    } catch (err: any) {
      setPasswordStatus("error");
      setPasswordError(err?.message || "Failed to update password.");
    } finally {
      setPasswordSaving(false);
    }
  };

  const handleSavePrompts = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveStatus("idle");
    setErrorText("");

    try {
      await updateSettings({
        system_prompt_overrides: {
          gate: gatePrompt.trim() || undefined,
          rewriter: rewriterPrompt.trim() || undefined,
          generic: genericPrompt.trim() || undefined,
          synthesis: synthesisPrompt.trim() || undefined,
          decision: decisionPrompt.trim() || undefined,
        },
      });
      setSaveStatus("success");
      setTimeout(() => setSaveStatus("idle"), 3000);
    } catch (err: any) {
      setSaveStatus("error");
      setErrorText(err?.message || "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  if (!state.project) return null;

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-zinc-50 p-6 lg:p-8">
      <div className="mx-auto w-full max-w-2xl space-y-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900">Project Settings</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Manage your project credentials, API keys, and customize agent prompts.
          </p>
        </div>

        {/* Password Card */}
        <form onSubmit={handleChangePassword} className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm space-y-6">
          <div>
            <h2 className="text-base font-semibold text-zinc-900">Login Password</h2>
            <p className="text-sm text-zinc-500">
              Change the password used to sign in to this project. Leave current password empty to
              reset using your admin API key (while logged in).
            </p>
          </div>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-zinc-900">Current password</label>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Leave empty if you forgot it"
                className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-sm text-zinc-800 shadow-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-zinc-900">New password</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={6}
                className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-sm text-zinc-800 shadow-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-zinc-900">Confirm new password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={6}
                className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-sm text-zinc-800 shadow-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-zinc-100">
            <div>
              {passwordStatus === "success" && (
                <p className="text-sm font-medium text-emerald-600">Password updated.</p>
              )}
              {passwordStatus === "error" && (
                <p className="text-sm font-medium text-rose-600">{passwordError}</p>
              )}
            </div>
            <button
              type="submit"
              disabled={passwordSaving}
              className="flex h-10 items-center justify-center rounded-xl bg-zinc-900 px-6 text-sm font-semibold text-white shadow-sm transition hover:bg-zinc-800 disabled:opacity-50"
            >
              {passwordSaving ? "Updating..." : "Update Password"}
            </button>
          </div>
        </form>

        {/* API Keys Card */}
        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-zinc-900">API Keys</h2>
              <p className="text-sm text-zinc-500">
                Use these keys to authenticate your application.
              </p>
            </div>
            <button
              onClick={() => setShowKeys(!showKeys)}
              className="flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 shadow-sm transition-colors hover:bg-zinc-50 hover:text-zinc-900"
            >
              {showKeys ? <IconEyeOff className="h-4 w-4" /> : <IconEye className="h-4 w-4" />}
              {showKeys ? "Hide Keys" : "Reveal Keys"}
            </button>
          </div>

          <div className="space-y-6">
            {/* Admin API Key */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-900">Admin API Key</label>
              <p className="text-xs text-zinc-500">
                Used for administrative actions (e.g. uploading or deleting media). Keep this secret!
              </p>
              <div className="flex items-center gap-2">
                <div className="flex-1 rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm font-mono text-zinc-800 break-all">
                  {showKeys ? state.project.apiKey : "•".repeat(40)}
                </div>
                <button
                  onClick={() => handleCopy(state.project!.apiKey, "api")}
                  className="flex h-10 items-center justify-center gap-2 rounded-xl border border-zinc-200 bg-white px-3 text-sm font-medium text-zinc-700 shadow-sm transition hover:bg-zinc-50 hover:text-zinc-900 focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:ring-offset-1"
                >
                  <IconCopy className="h-4 w-4" />
                  {copiedKey === "api" ? "Copied!" : "Copy"}
                </button>
              </div>
            </div>

            {/* Client Key */}
            <div className="space-y-2 pt-4 border-t border-zinc-100">
              <label className="text-sm font-medium text-zinc-900">Public Client Key</label>
              <p className="text-xs text-zinc-500">
                Used for reading data (e.g. searching/chatting). Safe to embed in frontend clients.
              </p>
              <div className="flex items-center gap-2">
                <div className="flex-1 rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm font-mono text-zinc-800 break-all">
                  {showKeys ? state.project.clientKey : "•".repeat(40)}
                </div>
                <button
                  onClick={() => handleCopy(state.project!.clientKey, "client")}
                  className="flex h-10 items-center justify-center gap-2 rounded-xl border border-zinc-200 bg-white px-3 text-sm font-medium text-zinc-700 shadow-sm transition hover:bg-zinc-50 hover:text-zinc-900 focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:ring-offset-1"
                >
                  <IconCopy className="h-4 w-4" />
                  {copiedKey === "client" ? "Copied!" : "Copy"}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* LLM Prompts Card */}
        <form onSubmit={handleSavePrompts} className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm space-y-6">
          <div>
            <h2 className="text-base font-semibold text-zinc-900">Agent Prompts</h2>
            <p className="text-sm text-zinc-500">
              Customize the system prompts for each agent in the Scrutinize pipeline. Leave empty to use the system defaults.
            </p>
          </div>

          <div className="space-y-4">
            {/* Gate */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-zinc-900">1. RAG Gate Prompt</label>
              <p className="text-xs text-zinc-500">Routes the user query to generic conversation or RAG search.</p>
              <textarea
                value={gatePrompt}
                onChange={(e) => setGatePrompt(e.target.value)}
                placeholder="Default RAG gate prompt..."
                rows={3}
                className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-sm text-zinc-800 shadow-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
              />
            </div>

            {/* Rewriter */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-zinc-900">2. Query Rewriter Prompt</label>
              <p className="text-xs text-zinc-500">Rewrites user queries for optimal keyword retrieval.</p>
              <textarea
                value={rewriterPrompt}
                onChange={(e) => setRewriterPrompt(e.target.value)}
                placeholder="Default query rewriter prompt..."
                rows={3}
                className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-sm text-zinc-800 shadow-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
              />
            </div>

            {/* Generic Agent */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-zinc-900">3. Generic Agent Prompt</label>
              <p className="text-xs text-zinc-500">Handles chit-chat and general knowledge queries directly without RAG search.</p>
              <textarea
                value={genericPrompt}
                onChange={(e) => setGenericPrompt(e.target.value)}
                placeholder="Default generic agent prompt..."
                rows={3}
                className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-sm text-zinc-800 shadow-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
              />
            </div>

            {/* Synthesis */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-zinc-900">4. Answer Synthesis Prompt</label>
              <p className="text-xs text-zinc-500">Generates draft answers grounded strictly in retrieved documents.</p>
              <textarea
                value={synthesisPrompt}
                onChange={(e) => setSynthesisPrompt(e.target.value)}
                placeholder="Default answer synthesis prompt..."
                rows={3}
                className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-sm text-zinc-800 shadow-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
              />
            </div>

            {/* Decision */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-zinc-900">5. Decision Agent Prompt</label>
              <p className="text-xs text-zinc-500">Scores draft answer quality and controls the query rewriting/retrieval retry loop.</p>
              <textarea
                value={decisionPrompt}
                onChange={(e) => setDecisionPrompt(e.target.value)}
                placeholder="Default decision agent prompt..."
                rows={3}
                className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-sm text-zinc-800 shadow-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-zinc-100">
            <div>
              {saveStatus === "success" && (
                <p className="text-sm font-medium text-emerald-600">Settings saved successfully!</p>
              )}
              {saveStatus === "error" && (
                <p className="text-sm font-medium text-rose-600">{errorText}</p>
              )}
            </div>
            <button
              type="submit"
              disabled={saving}
              className="flex h-10 items-center justify-center rounded-xl bg-zinc-900 px-6 text-sm font-semibold text-white shadow-sm transition hover:bg-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:ring-offset-1 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Prompts"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
