import { useState } from "react";
import { useApp } from "../context/AppContext";
import { IconCopy, IconEye, IconEyeOff } from "./icons";

export function SettingsView() {
  const { state } = useApp();
  const [showKeys, setShowKeys] = useState(false);
  const [copiedKey, setCopiedKey] = useState<"api" | "client" | null>(null);

  const handleCopy = (text: string, type: "api" | "client") => {
    navigator.clipboard.writeText(text);
    setCopiedKey(type);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  if (!state.project) return null;

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-zinc-50 p-6 lg:p-8">
      <div className="mx-auto w-full max-w-2xl">
        <div className="mb-8">
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900">Project Settings</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Manage your project credentials and API keys.
          </p>
        </div>

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
      </div>
    </div>
  );
}
