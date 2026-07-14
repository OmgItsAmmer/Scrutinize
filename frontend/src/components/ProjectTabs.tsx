import { IconLibrary, IconSearch, IconSettings, IconUpload } from "./icons";

export type ProjectChoice = "chats" | "sources" | "library" | "settings";

interface ProjectTabsProps {
  choice: ProjectChoice;
  onChoiceChange: (choice: ProjectChoice) => void;
}

export function ProjectTabs({ choice, onChoiceChange }: ProjectTabsProps) {
  const choices = [
    { id: "chats" as const, label: "Chats", icon: IconSearch },
    { id: "sources" as const, label: "Sources", icon: IconUpload },
    { id: "library" as const, label: "Library", icon: IconLibrary },
    { id: "settings" as const, label: "Settings", icon: IconSettings },
  ];

  return (
    <div className="relative z-20 flex shrink-0 justify-center px-3 py-4 sm:px-4">
      <div
        role="tablist"
        aria-label="Project workspace"
        className="flex items-center gap-1.5 rounded-2xl p-1.5 bg-white/60 border border-white/80 backdrop-blur-2xl shadow-xl shadow-black/5 transition-all duration-300 hover:shadow-2xl hover:shadow-black/10"
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
              onClick={() => onChoiceChange(item.id)}
              className={`inline-flex h-9 items-center gap-1.5 rounded-xl px-4 text-xs font-semibold transition-all duration-300 ${
                selected
                  ? "bg-zinc-950 text-white shadow-md shadow-zinc-950/10 scale-105"
                  : "text-zinc-600 hover:bg-zinc-950/5 hover:text-zinc-900"
              }`}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
