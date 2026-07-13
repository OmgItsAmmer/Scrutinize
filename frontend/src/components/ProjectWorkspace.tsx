import { useEffect } from "react";
import { useApp } from "../context/AppContext";
import { ConversationChatView } from "./ConversationChatView";
import { LibraryView } from "./LibraryView";
import { ProjectSettingsView } from "./SettingsView";
import { UploadView } from "./UploadView";
import { IconLibrary, IconSearch, IconSettings, IconUpload } from "./icons";

type ProjectChoice = "chats" | "sources" | "library" | "settings";

export function ProjectWorkspace() {
  const { state, refreshLibrary, setProjectChoice } = useApp();
  const choice = state.projectChoice as ProjectChoice;

  useEffect(() => {
    if (choice === "library") void refreshLibrary();
  }, [choice, refreshLibrary, state.project?.projectId]);

  const choices = [
    { id: "chats" as const, label: "Chats", icon: IconSearch },
    { id: "sources" as const, label: "Sources", icon: IconUpload },
    { id: "library" as const, label: "Library", icon: IconLibrary },
    { id: "settings" as const, label: "Settings", icon: IconSettings },
  ];

  return (
    <section className="flex h-full min-h-0 flex-col">
      <header className="shrink-0 px-3 py-2 sm:px-4">
        <div className="flex min-h-11 items-center justify-center">
          <div
            role="tablist"
            aria-label="Project workspace"
            className="flex items-center gap-1 rounded-xl p-1"
          >
            {choices.map((item) => {
              const Icon = item.icon;
              const selected = choice === item.id;
              return (
                <button
                  key={item.id}
                  role="tab"
                  aria-selected={selected}
                  type="button"
                  onClick={() => setProjectChoice(item.id)}
                  className={`inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold transition-all duration-200 ${
                    selected
                      ? "bg-[var(--app-primary)] text-[var(--app-primary-text)] shadow-sm"
                      : "text-[var(--app-text-muted)] hover:bg-black/5 hover:text-[var(--app-text)]"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>
      </header>
      <div className="min-h-0 flex-1">
        {choice === "chats" && <ConversationChatView scope="project" />}
        {choice === "sources" && <UploadView />}
        {choice === "library" && <LibraryView />}
        {choice === "settings" && <ProjectSettingsView />}
      </div>
    </section>
  );
}
